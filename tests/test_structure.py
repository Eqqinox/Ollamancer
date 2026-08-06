"""Golden-master / structural invariants — the modularization safety net.

The other tests verify *behaviour*. This one freezes the agent's *shape*: the tool registry,
the slash-command set, the bilingual string tables, and the /parameters schema. Its whole
purpose is to fail loudly when a refactor silently loses or renames something while every
behavioural test still passes.

Two failure modes it is specifically designed to catch while agent.py is being split into
the `agentic/` package:

1. A function that quietly disappears during a move (registry counts drop).
2. A tunable that stops being *live* — /parameters reads and writes its values through the
   defining module's namespace, so a setting can still display, still persist to JSON, and
   still be silently disconnected from the code that reads it. `test_params_are_live` does a
   real round-trip (write -> read back through the schema) to prove the wiring survives.

Runs offline: importing agent has no side effects that need Ollama or the network.
"""
import pathlib
import tempfile

import agent
from agentic import ui
from agentic import tools
from agentic import safety
from agentic import config, i18n

# ── The tool registry ────────────────────────────────────────────────────────
# Frozen deliberately: adding a tool is a real change and should require updating this list.
EXPECTED_TOOLS = {
    # web
    "search_web", "search_web_deep", "fetch_url", "fetch_url_rendered",
    # files
    "read_file", "read_file_lines", "write_file", "append_file", "edit_file",
    "create_directory", "list_directory",
    # code navigation
    "search_in_files", "find_files", "find_references", "search_semantic", "load_skill",
    # git
    "git_status", "git_diff", "git_log", "git_commit",
    # verification / execution
    "lint_file", "run_tests", "run_command", "python_repl",
    # vision
    "analyze_image",
    # task / memory
    "todo_write", "todo_read", "memory_write", "memory_read",
    # background processes
    "run_background", "check_process", "kill_process", "list_processes",
    # utility
    "get_datetime",
}

EXPECTED_SLASH_COMMANDS = {
    "/help", "/exit", "/clear", "/history", "/context", "/compact", "/resume", "/private",
    "/lang", "/safe", "/sandbox", "/parameters", "/model", "/default-model",
    "/failover-model", "/architect", "/architect-models", "/review-by", "/vision-model",
    "/skills", "/skill", "/tools", "/mcp", "/pwd", "/add", "/files", "/drop", "/plan",
    "/todo", "/memory", "/forget", "/ps", "/kill", "/diff", "/undo", "/audit",
}

EXPECTED_PARAM_VARS = {
    "GEN_TEMPERATURE", "GEN_TOP_P", "GEN_TOP_K", "GEN_REPEAT_PENALTY", "GEN_NUM_PREDICT",
    "GEN_SEED", "STREAM_FINAL",
    "SAFE_NUM_CTX", "MAX_TOOL_ROUNDS", "MAX_BACKGROUND_PROCESSES", "MAX_VERIFY_NUDGES",
    "MAX_FAKE_TOOLCALL_RETRIES", "MAX_CITATION_NUDGES", "MAX_GROUNDING_NUDGES",
    "MAX_GROUNDING_CHECK_NUDGES", "MAX_CLAIM_ACTION_NUDGES", "MAX_READONLY_REFUSALS",
    "SEMANTIC_TOP_K", "SEMANTIC_CHUNK_LINES", "AUTO_COMPACT", "COMPACT_THRESHOLD_PCT",
    "COMPACT_KEEP_TURNS",
    "SEARCH_LANGUAGE", "SEARCH_RESULT_CAP", "DEEP_SEARCH_FETCH_COUNT",
    "DEEP_SEARCH_CHAR_BUDGET", "DEEP_SEARCH_TIMEOUT", "DEEP_SEARCH_THIN_THRESHOLD",
    "MAX_DEEP_SEARCHES", "RSS_ENABLED",
}


def test_tool_registry():
    """TOOLS and TOOL_MAP agree with each other and with the documented 34."""
    names = {fn.__name__ for fn in tools.TOOLS}
    assert names == EXPECTED_TOOLS, (
        f"tool set changed\n  missing: {sorted(EXPECTED_TOOLS - names)}"
        f"\n  unexpected: {sorted(names - EXPECTED_TOOLS)}")
    assert len(tools.TOOLS) == 34, f"expected 34 tools, got {len(tools.TOOLS)}"
    assert set(tools.TOOL_MAP) == names, "TOOL_MAP is out of sync with TOOLS"
    # Every entry must be callable — catches a name that survived as a stale string/None.
    for name, fn in tools.TOOL_MAP.items():
        assert callable(fn), f"TOOL_MAP[{name!r}] is not callable"


def test_tool_subsets_are_real_tools():
    """The safety/architect subsets must only name tools that actually exist.

    A typo here fails open: a risky tool that isn't in _RISKY_TOOLS silently skips the
    safe-mode approval prompt.
    """
    unknown_risky = safety._RISKY_TOOLS - set(tools.TOOL_MAP)
    assert not unknown_risky, f"_RISKY_TOOLS names non-existent tools: {sorted(unknown_risky)}"
    unknown_ro = tools._READ_ONLY_TOOL_NAMES - set(tools.TOOL_MAP)
    assert not unknown_ro, f"_READ_ONLY_TOOL_NAMES names non-existent tools: {sorted(unknown_ro)}"
    # The architect phase must actually be read-only.
    writers = {"write_file", "append_file", "edit_file", "create_directory",
               "run_command", "run_tests", "python_repl", "git_commit", "run_background"}
    leaked = tools._READ_ONLY_TOOL_NAMES & writers
    assert not leaked, f"write-capable tools leaked into the read-only set: {sorted(leaked)}"


def test_slash_commands():
    """The command set is frozen, and autocomplete descriptions stay bilingual."""
    cmds = {c for c, _en, _fr in ui._SLASH_COMMANDS}
    assert cmds == EXPECTED_SLASH_COMMANDS, (
        f"slash commands changed\n  missing: {sorted(EXPECTED_SLASH_COMMANDS - cmds)}"
        f"\n  unexpected: {sorted(cmds - EXPECTED_SLASH_COMMANDS)}")
    assert len(ui._SLASH_COMMANDS) == 36
    for cmd, en, fr in ui._SLASH_COMMANDS:
        assert cmd.startswith("/"), f"{cmd!r} is not a slash command"
        assert en and fr, f"{cmd} is missing an EN or FR description"


def test_interface_is_bilingual():
    """EN/FR parity across every user-facing string table — the UI is bilingual by design."""
    assert set(i18n.STR) == {"en", "fr"}
    missing_fr = set(i18n.STR["en"]) - set(i18n.STR["fr"])
    missing_en = set(i18n.STR["fr"]) - set(i18n.STR["en"])
    assert not missing_fr, f"STR keys missing a French translation: {sorted(missing_fr)}"
    assert not missing_en, f"STR keys missing an English translation: {sorted(missing_en)}"
    assert set(i18n.SYSTEM_PROMPT) == {"en", "fr"}, "the system prompt must exist in both languages"
    assert set(i18n.HELP_TEXT) == {"en", "fr"}, "/help must exist in both languages"
    assert config.SUPPORTED_LANGS == {"en": "English", "fr": "Français"}


def test_param_schema():
    """The /parameters schema is frozen at 30 tunables, each well-formed."""
    params = ui._all_params()
    variables = {p["var"] for p in params}
    assert variables == EXPECTED_PARAM_VARS, (
        f"tunables changed\n  missing: {sorted(EXPECTED_PARAM_VARS - variables)}"
        f"\n  unexpected: {sorted(variables - EXPECTED_PARAM_VARS)}")
    assert len(params) == 30, f"expected 30 tunables, got {len(params)}"
    for p in params:
        assert p["kind"] in ("int", "float", "enum"), f"{p['var']}: bad kind {p['kind']!r}"
        assert p.get("help"), f"{p['var']} has no help text"
        if p["kind"] == "enum":
            assert p["default"] in p["options"], f"{p['var']}: default not among options"
        else:
            assert p["min"] <= p["default"] <= p["max"], f"{p['var']}: default out of range"


def test_params_are_live():
    """Every tunable must round-trip: adjusting it changes the value the agent actually reads.

    This is the modularization tripwire. /parameters resolves variables through the defining
    module's namespace; if the tunables move to another module and that lookup isn't moved
    with them, the menu keeps working and keeps saving while the running agent never sees the
    new value. Reading and writing through the schema is the only way to prove the link.
    """
    # _param_adjust persists through _save_params(), which writes config.PARAMS_FILE — the
    # REAL ~/.agentic_1a_params.json. Redirect it first: an earlier version of this test
    # rewrote the user's live settings (every value bumped one step, including
    # GEN_NUM_PREDICT -1 -> 127, which silently truncates every answer).
    real_params_file = config.PARAMS_FILE
    config.PARAMS_FILE = pathlib.Path(tempfile.mkdtemp()) / "params.json"

    saved = {}
    try:
        for p in ui._all_params():
            var = p["var"]
            # Readable through the same path the menu formats from.
            before = ui._param_format(p)
            saved[var] = getattr(config, var)
            assert before is not None

            # Nudge it and confirm the change is observable, then nudge it back.
            ui._param_adjust(p, +1)
            bumped = getattr(config, var)
            if p["kind"] == "enum":
                assert bumped in p["options"], f"{var}: adjust produced {bumped!r}"
            else:
                assert p["min"] <= bumped <= p["max"], f"{var}: adjust escaped its range"
            if saved[var] != (p["max"] if p["kind"] != "enum" else None):
                assert bumped != saved[var] or saved[var] == p.get("max"), (
                    f"{var}: _param_adjust did not change the live value — the /parameters "
                    f"menu is disconnected from the variable the agent reads")
    finally:
        for var, value in saved.items():
            setattr(config, var, value)
        config.PARAMS_FILE = real_params_file


def test_no_duplicate_tool_docstrings():
    """Every tool needs its own description — the SDK builds the model's schema from it.

    A copy-pasted docstring is a real reliability bug: the model picks tools by description.
    """
    for fn in tools.TOOLS:
        assert fn.__doc__ and fn.__doc__.strip(), f"{fn.__name__} has no docstring"
    docs = [fn.__doc__.strip()[:120] for fn in tools.TOOLS]
    assert len(set(docs)) == len(docs), "two tools share an identical description"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("test_structure: ALL PASS")
