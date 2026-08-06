"""Agentic_1A — terminal I/O primitives.

The console the agent writes to, the interactive prompt it reads from, and the slash-command
autocomplete that drives it. This module owns *how* the agent talks to the terminal; what it
says lives in `agentic/i18n.py`.

⚠️ IMPORT RULE (enforced by tests/test_import_rules.py) — `console` and `_prompt_session` are
**rebound at runtime** and must be reached through the module:

    from agentic import ui          # ✅
    console.print(...)           # ✅ resolved on every access

    from agentic.ui import console  # ❌ frozen copy

Both really do change mid-run, which is why the rule matters here as much as it does for
config and state:

  * `console` is replaced with one writing to **stderr** in headless mode (`--run`/`--recipe`),
    so that stdout carries only the final answer and stays pipeable.
  * `_prompt_session` is rebuilt with an **in-memory** history under `--private`, so typed
    lines never reach ~/.agentic_1a_history.

A by-name import would have silently kept the original console and leaked the banner into
stdout, or kept writing a private session's input to disk.

`_SLASH_COMMANDS` is a plain data table, never rebound, so it is safe to import by name.
"""

# Escape-key detection during generation (Unix only) — lets you stop the model and return
# to the prompt without killing the session. Silent no-op where unavailable.
try:
    import select as _select
    import termios
    import tty
    _TERMIOS_OK = True
except Exception:
    _TERMIOS_OK = False

import subprocess
import sys
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from agentic import config, state
from agentic.i18n import t

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.completion import Completer, Completion
    _PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    _PROMPT_TOOLKIT_AVAILABLE = False  # falls back to input()/readline — see _prompt()

console = Console()

# Slash-command autocomplete: (command, EN description, FR description). Typing "/"
# lists every command; each extra character filters the list. Source of
# truth for the completion menu — keep in sync with main()'s dispatch and HELP_TEXT.
_SLASH_COMMANDS = [
    ("/help", "Show all commands", "Afficher toutes les commandes"),
    ("/exit", "Quit", "Quitter"),
    ("/clear", "Clear history & context", "Effacer l'historique & le contexte"),
    ("/history", "Show the last messages", "Afficher les derniers messages"),
    ("/context", "Show context usage (tokens vs cap)", "Afficher l'usage du contexte"),
    ("/compact", "Compact the conversation now", "Compacter la conversation maintenant"),
    ("/resume", "List/reload a saved session", "Lister/recharger une session sauvegardée"),
    ("/private", "Is this session logged? (--private = no)", "Session journalisée ? (--private = non)"),
    ("/lang", "Change interface language (en/fr)", "Changer la langue (en/fr)"),
    ("/safe", "Toggle safe mode (approve risky tools)", "Basculer le mode sûr"),
    ("/sandbox", "Toggle Docker sandbox", "Basculer le sandbox Docker"),
    ("/parameters", "Open the settings menu", "Ouvrir le menu de réglages"),
    ("/model", "Switch model this session", "Changer de modèle (cette session)"),
    ("/default-model", "Set the persistent default model", "Définir le modèle par défaut persistant"),
    ("/failover-model", "Set the plumbing-bug backup model", "Définir le modèle de secours"),
    ("/architect", "Dual-model plan+execute a task", "Bi-modèle : planifier + exécuter une tâche"),
    ("/architect-models", "Configure the architect/editor pair", "Configurer la paire architecte/éditeur"),
    ("/review-by", "Second model reviews the diff", "Un second modèle relit le diff"),
    ("/vision-model", "Set the multimodal (image) model", "Définir le modèle vision"),
    ("/skills", "List available skills (reusable workflows)", "Lister les skills (workflows réutilisables)"),
    ("/skill", "Load a skill into context", "Charger un skill dans le contexte"),
    ("/tools", "List available tools", "Lister les outils disponibles"),
    ("/mcp", "List connected MCP servers", "Lister les serveurs MCP connectés"),
    ("/pwd", "Show the project root", "Afficher la racine du projet"),
    ("/add", "Inject file(s) into context", "Injecter des fichiers dans le contexte"),
    ("/files", "List injected files", "Lister les fichiers injectés"),
    ("/drop", "Remove a file from context", "Retirer un fichier du contexte"),
    ("/plan", "Plan a task without acting", "Planifier une tâche sans agir"),
    ("/todo", "Show the task checklist", "Afficher la checklist de tâche"),
    ("/memory", "Show persistent memory", "Afficher la mémoire persistante"),
    ("/forget", "Clear persistent memory", "Effacer la mémoire persistante"),
    ("/ps", "List background processes", "Lister les processus en arrière-plan"),
    ("/kill", "Stop a background process", "Arrêter un processus en arrière-plan"),
    ("/diff", "View this session's changes", "Voir les changements de la session"),
    ("/undo", "List/restore git checkpoints", "Lister/restaurer les checkpoints git"),
    ("/audit", "Show the audit log", "Afficher le journal d'audit"),
]

if _PROMPT_TOOLKIT_AVAILABLE:
    class _SlashCompleter(Completer):
        """Live completion for slash commands: typing '/' lists every command, and each extra
        character narrows the list. Only fires while typing the command word itself (no space
        yet), so ordinary prose input is never interrupted. Descriptions follow the current
        interface language."""
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            lang = getattr(config, "LANG", "en")
            for cmd, en, fr in _SLASH_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text),
                                     display=cmd, display_meta=(fr if lang == "fr" else en))


# Interactive input: prompt_toolkit handles bracketed paste itself
# instead of depending on the system readline library — on
# macOS the system/Homebrew Python is very often linked against libedit rather than
# GNU readline, whose paste support is weak/inconsistent (pasted text
# containing newlines submits prematurely at every
# `\n`, before the user presses Enter). Silent fallback to
# input()/readline if prompt_toolkit is not installed — behaviour
# identical to before, just without the fix.
_prompt_session = None
if _PROMPT_TOOLKIT_AVAILABLE:
    try:
        _prompt_session = PromptSession(
            history=FileHistory(str(config.HISTORY_FILE)),
            completer=_SlashCompleter(),
            complete_while_typing=True,   # the menu appears/filters as you type
        )
    except Exception:
        _prompt_session = None  # e.g. HISTORY_FILE unreadable — fall back to input()


def _prompt(label: str) -> str:
    """Single entry point for all interactive user input."""
    if _prompt_session is not None:
        return _prompt_session.prompt(label)
    return input(label)


def use_stderr_console() -> None:
    """Route all agent chrome to stderr — used by headless mode.

    In `--run`/`--recipe`, stdout must carry only the final answer so the result can be piped
    or captured. Everything else (banner, tool panels, spinners) goes to stderr.
    """
    global console
    console = Console(file=sys.stderr)


def use_ephemeral_history() -> None:
    """Rebuild the prompt session with an in-memory history — used by `--private`.

    Typed lines must not reach ~/.agentic_1a_history in a private session. Silently does
    nothing if prompt_toolkit is unavailable or no session was created.
    """
    global _prompt_session
    if _PROMPT_TOOLKIT_AVAILABLE and _prompt_session is not None:
        try:
            _prompt_session = PromptSession(history=InMemoryHistory(),
                                            completer=_SlashCompleter(), complete_while_typing=True)
        except Exception:
            pass  # keep the existing session rather than losing the prompt entirely


# ── Escape-to-stop, the live RAM spinner, and streamed rendering ─────────────
# Historically every call was stream=False because of the Ollama streaming+tools bug
# (#12557). Streaming only the FINAL answer — buffering any round that produces
# tool_calls — restores a real-time feel on the long final generation without touching
# tool-calling reliability. Any streaming failure degrades to the buffered path.
#
# The spinner and the live render are two phases of one display: spinner (with the
# live RAM readout) until the first text token arrives, then live markdown. On a tool
# round no text ever arrives, so the spinner stays up the whole time — which is what
# keeps "thinking" visible during tool use.


# ── Streaming the final answer (B2) ─────────────────────────────────────────────
# Historically every call was stream=False because of the Ollama
# streaming+tools bug (#12557). Re-evaluated: streaming only the final render (buffering
# if tool_calls appear) restores a "real time" feel on the long final
# generation, without changing tool-calling reliability. STREAM_FINAL toggle
# (default "on", can be disabled in /parameters if a model regresses on tools).
class _StreamedMessage:
    def __init__(self, content, tool_calls, thinking):
        self.content = content
        self.tool_calls = tool_calls
        self.thinking = thinking


class _StreamedResp:
    def __init__(self, message, prompt_eval_count=0):
        self.message = message
        self.prompt_eval_count = prompt_eval_count


class _UserAbort(Exception):
    """Raised when the user presses Escape (or Ctrl+C) during generation to stop the model and
    return to the prompt, without ending the session."""


class _EscapeWatcher:
    """Context manager: put the terminal in cbreak mode so a single Escape keypress can be
    detected between stream chunks (stops the model). Ctrl+C keeps working (ISIG stays on in
    cbreak). Completely no-op when stdin isn't a TTY (tests, headless, pipes) or termios is
    unavailable — so it never interferes with non-interactive runs."""
    def __init__(self):
        self._fd = None
        self._old = None

    def __enter__(self):
        if _TERMIOS_OK:
            try:
                if sys.stdin.isatty():
                    self._fd = sys.stdin.fileno()
                    self._old = termios.tcgetattr(self._fd)
                    tty.setcbreak(self._fd)
            except Exception:
                self._fd = None
        return self

    def pressed(self) -> bool:
        """True only for a bare Escape key. An Escape that starts a sequence (arrow keys send
        ESC [ A …) is drained and ignored, so navigation keys never abort by accident."""
        if self._fd is None:
            return False
        try:
            dr, _, _ = _select.select([sys.stdin], [], [], 0)
            if not dr:
                return False
            ch = sys.stdin.read(1)
            if ch != "\x1b":
                return False
            follow, _, _ = _select.select([sys.stdin], [], [], 0.02)
            if follow:
                try:
                    sys.stdin.read(2)   # drains the sequence (arrow key, etc.) — not an abort
                except Exception:
                    pass
                return False
            return True
        except Exception:
            return False

    def __exit__(self, *exc):
        if self._fd is not None and self._old is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
            except Exception:
                pass
        return False


def _consume_stream(stream, on_text=None, abort_check=None) -> _StreamedResp:
    """Fold an Ollama streaming generator into a single response-like object identical in
    shape to the non-stream path (resp.message.content / .tool_calls / .thinking). Calls
    on_text(accumulated_text) as plain text arrives — but stops feeding it once any
    tool_calls appear (that round is a tool round, not a final answer). Pure/testable:
    exceptions raised mid-stream (e.g. Ollama plumbing bugs) propagate to the caller."""
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls: list = []
    prompt_eval_count = 0
    for chunk in stream:
        if abort_check is not None and abort_check():
            try:
                stream.close()   # closes the HTTP stream -> signals the disconnect to Ollama
            except Exception:
                pass
            raise _UserAbort()
        pec = getattr(chunk, "prompt_eval_count", None)
        if pec:
            prompt_eval_count = pec  # the final chunk (done=True) carries the prompt's true token count
        m = getattr(chunk, "message", None)
        if m is None:
            continue
        tc = getattr(m, "tool_calls", None)
        if tc:
            tool_calls.extend(tc)
        th = getattr(m, "thinking", None)
        if th:
            thinking_parts.append(th)
        piece = getattr(m, "content", None) or ""
        if piece:
            content_parts.append(piece)
            if on_text is not None and not tool_calls:
                on_text("".join(content_parts))
    msg = _StreamedMessage("".join(content_parts), tool_calls or None,
                           "".join(thinking_parts) or None)
    return _StreamedResp(msg, prompt_eval_count=prompt_eval_count)


