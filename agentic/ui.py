"""Agentic_1A — terminal I/O primitives.

The console the agent writes to, the interactive prompt it reads from, and the slash-command
autocomplete that drives it. This module owns *how* the agent talks to the terminal; what it
says lives in `agentic/i18n.py`.

⚠️ IMPORT RULE (enforced by tests/test_import_rules.py) — `console` and `_prompt_session` are
**rebound at runtime** and must be reached through the module:

    from agentic import ui          # ✅
    ui.console.print(...)           # ✅ resolved on every access

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

import sys

from rich.console import Console

from agentic import config

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

