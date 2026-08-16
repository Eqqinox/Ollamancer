"""Ollamancer — per-session runtime state.

Everything here describes **this run**: which project folder is active, whether safe mode is
on, where this session's files live, what has been written so far. None of it is persisted
between sessions (that is `agentic/config.py`), and all of it is reset by `reset()`.

⚠️ IMPORT RULE (enforced by tests/test_import_rules.py) — these values are **rebound at
runtime**, so always go through the module; never import the names:

    from agentic import state       # ✅
    state.PROJECT_ROOT              # ✅ resolved on every access

    from agentic.state import PROJECT_ROOT   # ❌ frozen copy: stays None forever

Writing from another module needs no `global` declaration — `state.SAFE_MODE = True` rebinds
the attribute on this module object, which every reader sees.

The split from config is not cosmetic: it makes a session resettable in one call, which is
what `reset()` exists for. Tests that mutate globals can restore a clean slate without
knowing which names they touched.
"""

from pathlib import Path

# ── Project & session modes ──────────────────────────────────────────────────
PROJECT_ROOT: Path | None = None   # active project root; set by main()
SAFE_MODE = False                  # toggled by /safe or --safe at launch; see _RISKY_TOOLS
SANDBOX_MODE = False               # toggled by /sandbox or --sandbox at launch; see _run_shell
PRIVATE_MODE = False               # via --private at launch: ephemeral session, nothing from the
                                   # conversation is written to disk (no session JSON, no input
                                   # history, no audit log, no disk snapshots, no checkpoints,
                                   # no memory).

# ── Session paths (all initialised in main(), under <project>/.agentic/) ─────
_AUDIT_LOG: Path | None = None     # audit_YYYYMMDD.log
_SNAPSHOT_DIR: Path | None = None  # snapshots/, pre-edit file copies
_BG_LOG_DIR: Path | None = None    # bg_logs/, output of run_background processes
_SESSION_DIR: Path | None = None   # sessions/, saved transcripts for /resume
_SESSION_FILE: Path | None = None  # JSON file for THIS session (one per session, rewritten)
_SEMANTIC_DB: Path | None = None   # semantic_index.db, the local RAG index

# ── Working state ────────────────────────────────────────────────────────────
_snapshots: dict = {}       # {str(absolute_path): original_content}, powers the legacy /undo
_context_files: dict = {}   # {str(absolute_path): file_name}, files injected with /add
_todo: str = ""             # free-text checklist for the multi-step task in progress
_memory: str = ""           # free-text persistent memory, loaded from/saved to .agentic/memory.md

# ── Background processes & the persistent REPL ───────────────────────────────
_bg_processes: dict = {}    # {id_str: {"proc": Popen, "command": str, "log_path": Path,
                            #           "log_file": file, "started_at": str}}
_bg_counter = 0
_repl_state: dict = {"proc": None, "mode": None}   # the persistent python_repl subprocess
_SANDBOX_CONTAINER = None   # name of this session's active Docker container (created lazily)

# ── Git checkpoints (B1), replaces the all-or-nothing in-memory /undo ───────
# A "shadow" git repository lives in .agentic/checkpoints.git with the project folder as its
# work tree. It is completely independent of the user's own git, if any (dedicated
# GIT_DIR/GIT_WORK_TREE): it never touches their index, refs or commits, and therefore
# behaves identically in git AND non-git projects (the aider approach). One checkpoint = a
# commit of the state BEFORE a turn's first write.
_CHECKPOINT_GITDIR: Path | None = None
_CHECKPOINTS: list = []            # [{"sha": str, "ts": str, "turn": int, "label": str}]
_checkpoint_turn = 0               # incremented on every run_agent call (= one user turn)
_checkpoint_made_this_turn = False

_last_turn_tool_results: list = []   # raw tool output of the last completed turn, lets a
                                    # caller check whether URLs in an answer were really seen
_last_turn_tool_calls: list = []    # [{name, args, result, seconds, blocked}] for the same
                                    # turn, UNtruncated. Backs /details: the compact display
                                    # prints one line per call and this is where everything it
                                    # left out lives. Cleared at the start of each turn, so it
                                    # always describes the most recent one.

# ── Model & context tracking ─────────────────────────────────────────────────
_CURRENT_MODEL = ""                # the current loop's model, updated by run_agent
_LAST_PROMPT_TOKENS = 0            # last real prompt_eval_count returned by Ollama (the
                                   # prompt's true size), used to trigger compaction

# ── Caches (cleared by reset() so a fresh session never sees stale data) ─────
_num_ctx_cache: dict = {}   # model name -> negotiated num_ctx (avoids an ollama.show() per call)
_search_cache: dict = {}    # (query, category, language) -> (timestamp, results)
_rss_cache: dict = {}       # "pool" -> (timestamp, items) — every feed fetched once per TTL,
                            # so per-section matching costs no extra requests
_robots_cache: dict = {}    # origin (scheme://host) -> RobotFileParser | None (None = not found, allow)


def reset() -> None:
    """Restore every value above to its startup default.

    Used by tests to get a clean slate without having to know which globals a previous test
    mutated. Deliberately does NOT touch `config` — settings survive; only this run does not.

    Note it resets values in place where the object identity could matter (the dicts are
    cleared rather than replaced), so any module that captured a reference to `_snapshots`
    or `_bg_processes` still sees the same, now-empty, object.
    """
    global PROJECT_ROOT, SAFE_MODE, SANDBOX_MODE, PRIVATE_MODE
    global _AUDIT_LOG, _SNAPSHOT_DIR, _BG_LOG_DIR, _SESSION_DIR, _SESSION_FILE, _SEMANTIC_DB
    global _todo, _memory, _bg_counter, _SANDBOX_CONTAINER
    global _CHECKPOINT_GITDIR, _checkpoint_turn, _checkpoint_made_this_turn
    global _CURRENT_MODEL, _LAST_PROMPT_TOKENS

    PROJECT_ROOT = None
    SAFE_MODE = SANDBOX_MODE = PRIVATE_MODE = False

    _AUDIT_LOG = _SNAPSHOT_DIR = _BG_LOG_DIR = None
    _SESSION_DIR = _SESSION_FILE = _SEMANTIC_DB = None

    _todo = ""
    _memory = ""
    _bg_counter = 0
    _SANDBOX_CONTAINER = None

    _CHECKPOINT_GITDIR = None
    _checkpoint_turn = 0
    _checkpoint_made_this_turn = False

    _CURRENT_MODEL = ""
    _LAST_PROMPT_TOKENS = 0

    for container in (_snapshots, _context_files, _bg_processes,
                      _num_ctx_cache, _search_cache, _robots_cache, _rss_cache):
        container.clear()
    _last_turn_tool_results.clear()
    _last_turn_tool_calls.clear()
    _CHECKPOINTS.clear()
    _repl_state.update({"proc": None, "mode": None})
