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

import curses
import json
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




# ── /parameters: the live settings menu ──────────────────────────────────────
# A full-screen curses menu over the 30 tunables in agentic/config.py. Each row names
# its variable as a string and reads/writes it with getattr/setattr on the config
# module — so the menu, the persisted JSON, and the value the agent actually reads are
# guaranteed to be the same object. (While the schema and the variables shared a module
# this used globals(); that stopped working the moment config moved out, silently, which
# is what tests/test_structure.py::test_params_are_live now guards.)

_PARAM_SCHEMA = [
    ("Model Generation", [
        {"var": "GEN_TEMPERATURE", "label": "Temperature", "kind": "float",
         "min": 0.0, "max": 2.0, "step": 0.05, "default": 0.8,
         "help": "Randomness of the output. Lower = focused and deterministic. "
                 "Higher = more creative and unpredictable. 0 always picks the single most likely next word."},
        {"var": "GEN_TOP_P", "label": "Top P", "kind": "float",
         "min": 0.0, "max": 1.0, "step": 0.05, "default": 0.9,
         "help": "Nucleus sampling — only considers the smallest set of tokens whose combined "
                 "probability reaches this value. Lower = narrower, safer word choices."},
        {"var": "GEN_TOP_K", "label": "Top K", "kind": "int",
         "min": 0, "max": 100, "step": 1, "default": 40,
         "help": "Only considers the K most likely next tokens at each step. Lower = more focused. "
                 "0 disables this filter (Top P alone decides)."},
        {"var": "GEN_REPEAT_PENALTY", "label": "Repeat Penalty", "kind": "float",
         "min": 1.0, "max": 2.0, "step": 0.05, "default": 1.1,
         "help": "Penalizes tokens already used, to reduce repetition. 1.0 = no penalty. "
                 "Too high can make text feel unnatural or avoid necessary repeated words."},
        {"var": "GEN_NUM_PREDICT", "label": "Max Output Tokens", "kind": "int",
         "min": -1, "max": 8192, "step": 128, "default": -1, "special_min_label": "unlimited",
         "help": "Maximum tokens the model can generate in one reply. "
                 "-1 (unlimited) = stops naturally or when context runs out."},
        {"var": "GEN_SEED", "label": "Seed", "kind": "int",
         "min": -1, "max": 999999, "step": 1, "default": -1, "special_min_label": "random",
         "help": "Fixed seed for reproducible outputs (same input -> same output). "
                 "-1 (random) = a different seed every request."},
        {"var": "STREAM_FINAL", "label": "Stream Final Answer", "kind": "enum",
         "options": ["on", "off"], "default": "on",
         "help": "Stream the model's answer live as it generates instead of showing it all at "
                 "once. Tool-call rounds are still buffered. Set to \"off\" to fall back to the "
                 "classic buffered call if a model's tool calling regresses while streaming "
                 "(historical Ollama bug #12557)."},
    ]),
    ("Context & Safety Limits", [
        {"var": "SAFE_NUM_CTX", "label": "Context Window Cap", "kind": "int",
         "min": 4096, "max": 131072, "step": 4096, "default": 65536,
         "help": "Maximum context window requested from Ollama, capped for RAM safety. "
                 "Lower = less RAM used, but the model \"forgets\" more of a long conversation. "
                 "Default is 64K; raise toward 128K only if you have RAM headroom."},
        {"var": "MAX_TOOL_ROUNDS", "label": "Max Tool-Call Rounds", "kind": "int",
         "min": 5, "max": 50, "step": 5, "default": 25,
         "help": "Safety limit: how many tool-call rounds the agent can run in a single turn "
                 "before stopping automatically, to prevent an infinite loop."},
        {"var": "MAX_BACKGROUND_PROCESSES", "label": "Max Background Processes", "kind": "int",
         "min": 1, "max": 10, "step": 1, "default": 5,
         "help": "How many run_background processes can be active at once before new ones are blocked."},
        {"var": "MAX_VERIFY_NUDGES", "label": "Max Self-Verification Nudges", "kind": "int",
         "min": 0, "max": 5, "step": 1, "default": 2,
         "help": "How many times the agent auto-nudges itself to verify its own edit "
                 "(lint/tests) before giving up and answering anyway."},
        {"var": "MAX_FAKE_TOOLCALL_RETRIES", "label": "Max Fake-Tool-Call Retries", "kind": "int",
         "min": 0, "max": 5, "step": 1, "default": 2,
         "help": "How many times the agent asks a model to retry for real when it writes "
                 "a tool call as plain text (e.g. \"<function=...>\") instead of actually "
                 "invoking it, before giving up with an explicit error."},
        {"var": "MAX_CITATION_NUDGES", "label": "Max Citation Nudges", "kind": "int",
         "min": 0, "max": 3, "step": 1, "default": 1,
         "help": "How many times the agent nudges the model to add [Source: URL] "
                 "citations when it used search/fetch results but the final answer "
                 "cited none. A soft quality nudge, not a hard requirement — set to 0 "
                 "to disable."},
        {"var": "MAX_GROUNDING_NUDGES", "label": "Max Grounding Nudges", "kind": "int",
         "min": 0, "max": 3, "step": 1, "default": 1,
         "help": "How many times the agent nudges the model when it describes a "
                 "hypothetical tool result (\"returns something like this\") with "
                 "invented specific values instead of actually calling the tool or "
                 "clearly labeling the example as made up. Set to 0 to disable."},
        {"var": "MAX_GROUNDING_CHECK_NUDGES", "label": "Max Unsupported-Value Nudges", "kind": "int",
         "min": 0, "max": 3, "step": 1, "default": 1,
         "help": "Deterministic post-answer check: how many times the agent nudges when the "
                 "final answer contains hard tokens (numbers, dates, URLs, quoted names) that "
                 "appear in NONE of this turn's raw tool results. A nudge, not a gate (derived "
                 "or paraphrased values may false-positive). Set to 0 to disable."},
        {"var": "MAX_CLAIM_ACTION_NUDGES", "label": "Max Claim-vs-Action Nudges", "kind": "int",
         "min": 0, "max": 3, "step": 1, "default": 1,
         "help": "How many times the agent nudges when the answer claims a fix ("
                 "\"fixed\", \"corrigé\") with no successful edit this turn, or claims "
                 "verification (\"verified\", \"tested\") with no verification tool call this "
                 "turn. Set to 0 to disable."},
        {"var": "MAX_READONLY_REFUSALS", "label": "Architect Read-Only Refusals", "kind": "int",
         "min": 1, "max": 8, "step": 1, "default": 3,
         "help": "In /architect planning, how many refused write/execute tool calls the "
                 "architect model may make before it is told once to stop calling tools and "
                 "write the plan as text. Lower = nudge sooner (helps small architect models)."},
        {"var": "SEMANTIC_TOP_K", "label": "Semantic Search Results", "kind": "int",
         "min": 1, "max": 15, "step": 1, "default": 5,
         "help": "How many closest chunks search_semantic (local RAG over the project) returns."},
        {"var": "SEMANTIC_CHUNK_LINES", "label": "Semantic Chunk Lines", "kind": "int",
         "min": 20, "max": 200, "step": 10, "default": 60,
         "help": "Line count per indexed chunk for search_semantic. Smaller = more precise "
                 "matches but a bigger index; larger = more context per hit."},
        {"var": "AUTO_COMPACT", "label": "Auto-Compact Context", "kind": "enum",
         "options": ["off", "on"], "default": "off",
         "help": "When on, once the conversation passes the threshold below, the oldest turns are "
                 "replaced by a structured summary (system prompt + recent turns kept verbatim). "
                 "OFF by default — compaction is lossy, so it never fires unless you enable it. "
                 "Use /compact for manual, on-demand compaction regardless of this setting."},
        {"var": "COMPACT_THRESHOLD_PCT", "label": "Compact At (% of Context)", "kind": "int",
         "min": 50, "max": 95, "step": 5, "default": 70,
         "help": "Auto-compact fires when the real prompt token count passes this % of the context "
                 "window. Earlier (70%) is safer than late (95%) — a model near its ceiling writes "
                 "worse summaries."},
        {"var": "COMPACT_KEEP_TURNS", "label": "Keep Recent Turns", "kind": "int",
         "min": 1, "max": 12, "step": 1, "default": 3,
         "help": "How many of the most recent user turns are kept verbatim during compaction. "
                 "Everything older is folded into the structured summary."},
    ]),
    ("Web Search", [
        {"var": "SEARCH_LANGUAGE", "label": "Search Language", "kind": "enum",
         "options": ["en-US", "fr-FR", "auto"], "default": "en-US",
         "help": "Language bias applied to every SearXNG query. \"auto\" lets the SearXNG "
                 "instance's own default decide (can drift toward whatever the instance is configured for)."},
        {"var": "SEARCH_RESULT_CAP", "label": "Search Results Kept", "kind": "int",
         "min": 3, "max": 15, "step": 1, "default": 5,
         "help": "How many raw search results search_web keeps per call. "
                 "More = broader coverage, more tokens spent."},
        {"var": "DEEP_SEARCH_FETCH_COUNT", "label": "Deep Search: Pages Fetched", "kind": "int",
         "min": 1, "max": 6, "step": 1, "default": 3,
         "help": "How many top results search_web_deep actually opens and reads in full, in parallel."},
        {"var": "DEEP_SEARCH_CHAR_BUDGET", "label": "Deep Search: Chars per Page", "kind": "int",
         "min": 500, "max": 5000, "step": 250, "default": 2000,
         "help": "How much cleaned article text is kept per fetched page in search_web_deep."},
        {"var": "DEEP_SEARCH_TIMEOUT", "label": "Deep Search: Fetch Timeout (s)", "kind": "int",
         "min": 2, "max": 15, "step": 1, "default": 5,
         "help": "How long to wait for each page fetch in search_web_deep before giving up on that source."},
        {"var": "DEEP_SEARCH_THIN_THRESHOLD", "label": "Deep Search: Thin-Content Threshold", "kind": "int",
         "min": 50, "max": 1000, "step": 50, "default": 200,
         "help": "If a fetched page's extracted text is shorter than this (likely a JS-only "
                 "shell), search_web_deep automatically retries it through a real headless "
                 "browser instead of giving up."},
        {"var": "RSS_ENABLED", "label": "News RSS Feeds", "kind": "enum",
         "options": ["on", "off"], "default": "on",
         "help": "For news-shaped queries, also pull matching headlines from major-outlet RSS "
                 "feeds (Reuters, AP, BBC, Al Jazeera, NPR, Guardian, Fox) — real publisher "
                 "dates, no JavaScript/anti-bot problem, since RSS is served for machine "
                 "consumption. Mainstream coverage only; doesn't help for independent/underground sources."},
        {"var": "MAX_DEEP_SEARCHES", "label": "Max Deep Searches per Turn", "kind": "int",
         "min": 2, "max": 15, "step": 1, "default": 6,
         "help": "How many search_web_deep calls the agent can make in one turn before being "
                 "told to stop and answer with what it has — triggers even if every result was "
                 "real content, unlike the thin-search circuit breaker, since a long chain of "
                 "real-but-unconverging deep searches can otherwise exhaust the whole time budget."},
    ]),
]


def _param_format(p: dict) -> str:
    val = getattr(config, p["var"])
    if p["kind"] == "enum":
        return str(val)
    if p.get("special_min_label") and val == p["min"]:
        return f"{val} ({p['special_min_label']})"
    if p["kind"] == "float":
        return f"{val:.2f}"
    return str(val)


def _param_adjust(p: dict, direction: int) -> None:
    """direction: -1 (left) or +1 (right)."""
    var = p["var"]
    if p["kind"] == "enum":
        opts = p["options"]
        idx = (opts.index(getattr(config, var)) + direction) % len(opts)
        setattr(config, var, opts[idx])
    else:
        step = p["step"]
        new_val = getattr(config, var) + direction * step
        new_val = max(p["min"], min(p["max"], new_val))
        if p["kind"] == "float":
            new_val = round(new_val, 2)
        setattr(config, var, new_val)
    _save_params()


def _flatten_schema():
    """Return a flat list of rows: ('header', text) or ('param', dict)."""
    rows = []
    for section, params in _PARAM_SCHEMA:
        rows.append(("header", section))
        for p in params:
            rows.append(("param", p))
    return rows


def _all_params() -> list:
    """All the parameter dicts (without the section headers)."""
    return [p for kind, p in _flatten_schema() if kind == "param"]


def _save_params() -> None:
    """Save the current value of every /parameters setting to PARAMS_FILE
    (user level, not per project — these are taste/hardware settings, not
    project settings)."""
    try:
        data = {p["var"]: getattr(config, p["var"]) for p in _all_params()}
        config.PARAMS_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass  # non-blocking: a failed save must never break the session


def _load_params() -> None:
    """Reload the saved values at startup. Silently ignores unknown/obsolete keys
    (e.g. a setting renamed or removed since) instead of crashing on an old
    file."""
    if not config.PARAMS_FILE.exists():
        return
    try:
        data = json.loads(config.PARAMS_FILE.read_text())
    except Exception:
        return
    known_vars = {p["var"] for p in _all_params()}
    for var, value in data.items():
        if var in known_vars:
            setattr(config, var, value)


def _parameters_curses_main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    has_color = curses.has_colors()
    if has_color:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)    # section headers
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # selected row
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # help text

    rows = _flatten_schema()
    selectable = [i for i, (kind, _) in enumerate(rows) if kind == "param"]
    sel_pos = 0  # index into `selectable`

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(0, 2, "Agentic_1A — /parameters  (↑/↓ move, ←/→ adjust, r reset, q/Enter exit)",
                      curses.A_BOLD)
        y = 2
        cur_row_idx = selectable[sel_pos]
        for i, (kind, content) in enumerate(rows):
            if y >= h - 4:
                break
            if kind == "header":
                attr = curses.color_pair(1) | curses.A_BOLD if has_color else curses.A_BOLD
                stdscr.addstr(y, 2, content, attr)
                y += 1
            else:
                is_sel = (i == cur_row_idx)
                label = content["label"]
                value = _param_format(content)
                line = f"  {label:<32}{value:>15}"
                if is_sel:
                    attr = curses.color_pair(2) if has_color else curses.A_REVERSE
                    stdscr.addstr(y, 2, line.ljust(w - 4), attr)
                else:
                    stdscr.addstr(y, 2, line)
                y += 1

        # help bar at the bottom, for the selected parameter
        _, sel_param = rows[cur_row_idx]
        help_text = sel_param["help"]
        default = sel_param["default"]
        default_str = f"default: {default}" if sel_param["kind"] != "enum" else f"default: {default}"
        footer_attr = curses.color_pair(3) if has_color else curses.A_DIM
        stdscr.addstr(h - 3, 2, "─" * min(w - 4, 100))
        for j, chunk_line in enumerate(_wrap_text(help_text, w - 4)[:2]):
            stdscr.addstr(h - 2 + j if h - 2 + j < h else h - 1, 2, chunk_line, footer_attr)
        stdscr.addstr(h - 1, max(w - len(default_str) - 3, 2), default_str, footer_attr)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord('k')):
            sel_pos = (sel_pos - 1) % len(selectable)
        elif key in (curses.KEY_DOWN, ord('j')):
            sel_pos = (sel_pos + 1) % len(selectable)
        elif key in (curses.KEY_LEFT, ord('h')):
            _param_adjust(sel_param, -1)
        elif key in (curses.KEY_RIGHT, ord('l')):
            _param_adjust(sel_param, +1)
        elif key == ord('r'):
            setattr(config, sel_param["var"], sel_param["default"])
        elif key in (ord('q'), 27, ord('\n'), curses.KEY_ENTER):
            break


def _wrap_text(text: str, width: int) -> list:
    words = text.split()
    lines, cur = [], ""
    for word in words:
        if len(cur) + len(word) + 1 > max(width, 10):
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def run_parameters_menu() -> None:
    """Lance le menu interactif /parameters (plein écran, curses)."""
    try:
        curses.wrapper(_parameters_curses_main)
    except curses.error as e:
        console.print(f"[red]Could not open the parameters menu (terminal too small or unsupported): {e}[/red]\n")
        return
    console.print(f"[dim]Parameters updated — saved automatically to {config.PARAMS_FILE}.[/dim]\n")
