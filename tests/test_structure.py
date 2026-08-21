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
import collections
import pathlib
import re
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
    "search_in_files", "find_files", "find_references", "search_semantic", "repo_map",
    "load_skill",
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
    "/help", "/exit", "/clear", "/history", "/context", "/details", "/compact", "/resume", "/private",
    "/lang", "/safe", "/sandbox", "/parameters", "/model", "/default-model",
    "/failover-model", "/architect", "/architect-models", "/review-by", "/vision-model",
    "/skills", "/skill", "/tools", "/mcp", "/pwd", "/add", "/files", "/drop", "/plan",
    "/todo", "/memory", "/forget", "/ps", "/kill", "/diff", "/undo", "/audit",
}

EXPECTED_PARAM_VARS = {
    "THINK_MODE",
    "GEN_TEMPERATURE", "GEN_TOP_P", "GEN_TOP_K", "GEN_REPEAT_PENALTY", "GEN_NUM_PREDICT",
    "GEN_SEED", "TOOL_DISPLAY", "STREAM_FINAL",
    "SAFE_NUM_CTX", "MAX_TOOL_ROUNDS", "TURN_BUDGET_SECONDS", "MAX_BACKGROUND_PROCESSES",
    "MAX_VERIFY_NUDGES",
    "MAX_FAKE_TOOLCALL_RETRIES", "MAX_CITATION_NUDGES", "MAX_GROUNDING_NUDGES",
    "MAX_GROUNDING_CHECK_NUDGES", "MAX_CLAIM_ACTION_NUDGES", "MAX_READONLY_REFUSALS",
    "SEMANTIC_TOP_K", "SEMANTIC_CHUNK_LINES", "AUTO_COMPACT", "COMPACT_THRESHOLD_PCT",
    "COMPACT_KEEP_TURNS",
    "SEARCH_LANGUAGE", "SEARCH_RESULT_CAP", "DEEP_SEARCH_FETCH_COUNT",
    "DEEP_SEARCH_CHAR_BUDGET", "DEEP_SEARCH_TIMEOUT", "DEEP_SEARCH_THIN_THRESHOLD",
    "MAX_SECTIONS", "MAX_DEEP_SEARCHES", "RSS_ENABLED",
}


def test_tool_registry():
    """TOOLS and TOOL_MAP agree with each other and with the documented 35."""
    names = {fn.__name__ for fn in tools.TOOLS}
    assert names == EXPECTED_TOOLS, (
        f"tool set changed\n  missing: {sorted(EXPECTED_TOOLS - names)}"
        f"\n  unexpected: {sorted(names - EXPECTED_TOOLS)}")
    assert len(tools.TOOLS) == 35, f"expected 35 tools, got {len(tools.TOOLS)}"
    assert set(tools.TOOL_MAP) == names, "TOOL_MAP is out of sync with TOOLS"
    # Every entry must be callable: catches a name that survived as a stale string/None.
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
    assert len(ui._SLASH_COMMANDS) == 37
    for cmd, en, fr in ui._SLASH_COMMANDS:
        assert cmd.startswith("/"), f"{cmd!r} is not a slash command"
        assert en and fr, f"{cmd} is missing an EN or FR description"


def test_completer_matches_the_dispatch():
    """Every command the CLI handles must also be offered by autocomplete.

    `_SLASH_COMMANDS` is a hand-maintained table, and its own comment asks the reader to
    keep it in step with the dispatch and HELP_TEXT: three lists, updated by hand. The
    frozen-set check above cannot catch drift between them, because it compares the table
    with a copy of itself. That is not hypothetical: `/details` shipped working and
    documented, but absent from the table, so typing `/d` offered nothing and the suite
    stayed green.

    This compares the table against the commands `cli.py` actually dispatches, which is
    the pairing a user experiences. HELP_TEXT is deliberately not included: it documents
    aliases and argument forms (`/undo last`, `/lang fr`) that are not separate dispatch
    keys, so it legitimately holds more entries.
    """
    src = (pathlib.Path(__file__).resolve().parent.parent / "agentic" / "cli.py").read_text()
    dispatched = set(re.findall(r'user_input\s*==\s*"(/[a-z-]+)"', src))
    dispatched |= set(re.findall(r'user_input\.startswith\("(/[a-z-]+)', src))
    # `user_input in ("/parameters", "/params")` is the third dispatch form. Recognising it
    # rather than granting it an exception keeps the forward check complete too.
    for group in re.findall(r'user_input\s+in\s+\(([^)]*)\)', src):
        dispatched |= set(re.findall(r'"(/[a-z-]+)"', group))
    offered = {c for c, _en, _fr in ui._SLASH_COMMANDS}

    # Convenience spellings the dispatch accepts but the menu deliberately does not
    # advertise, so autocomplete shows one canonical name per command instead of two.
    ALIASES = {"/params", "/models", "/failover", "/defaultmodel", "/architectmodels",
               "/visionmodel", "/incognito"}

    missing = dispatched - offered - ALIASES
    assert not missing, (
        f"handled by cli.py but not offered by autocomplete: {sorted(missing)}. "
        "Add them to ui._SLASH_COMMANDS, or to ALIASES here if hiding them is deliberate.")

    unknown = offered - dispatched
    assert not unknown, (
        f"offered by autocomplete but never dispatched: {sorted(unknown)}. "
        "Either wire them up in cli.py or remove them from the table.")


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
    """The /parameters schema is frozen at 34 tunables, each well-formed."""
    params = ui._all_params()
    variables = {p["var"] for p in params}
    assert variables == EXPECTED_PARAM_VARS, (
        f"tunables changed\n  missing: {sorted(EXPECTED_PARAM_VARS - variables)}"
        f"\n  unexpected: {sorted(variables - EXPECTED_PARAM_VARS)}")
    assert len(params) == 34, f"expected 34 tunables, got {len(params)}"
    for p in params:
        assert p["kind"] in ("int", "float", "enum"), f"{p['var']}: bad kind {p['kind']!r}"
        assert p.get("help"), f"{p['var']} has no help text"
        if p["kind"] == "enum":
            assert p["default"] in p["options"], f"{p['var']}: default not among options"
        else:
            assert p["min"] <= p["default"] <= p["max"], f"{p['var']}: default out of range"


def test_schema_defaults_match_config():
    """The schema's `default` must be the value config.py actually ships.

    They are two hand-maintained copies of one number, and they drifted: the menu said 1.1 for
    GEN_REPEAT_PENALTY against config.py's 1.15, and 25 for MAX_TOOL_ROUNDS against 45. Both
    superseded values are ones config.py documents as harmful — 1.1 produced a malformed tool
    call in 9 runs out of 11, and 25 truncated gpt-oss:20b mid-task with both bugs already
    found. Nothing caught it because `default` is only read on two paths that no test
    exercised: the `r` (reset) key writes it into config, and the menu footer prints it as
    "default: X". So the menu quietly offered to undo two measured fixes, and told you the
    wrong number while doing it.

    test_param_schema above checks `min <= default <= max`, which both stale values satisfied
    — a range check cannot see that a number is the *wrong* number. This compares against the
    live module instead, which is the only source that can be right.

    Reads config directly rather than through _load_params(): this must pin what the code
    ships, not what a developer happens to have saved in ~/.agentic_1a_params.json.
    """
    for p in ui._all_params():
        live = getattr(config, p["var"])
        assert p["default"] == live, (
            f"{p['var']}: /parameters offers default {p['default']!r} but config.py ships "
            f"{live!r} — pressing 'r' on that row would overwrite the shipped value, and the "
            f"menu footer already displays the wrong one")


def test_params_are_live():
    """Every tunable must round-trip: adjusting it changes the value the agent actually reads.

    This is the modularization tripwire. /parameters resolves variables through the defining
    module's namespace; if the tunables move to another module and that lookup isn't moved
    with them, the menu keeps working and keeps saving while the running agent never sees the
    new value. Reading and writing through the schema is the only way to prove the link.
    """
    # _param_adjust persists through _save_params(), which writes config.PARAMS_FILE, the
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


# ── Docs-vs-repo counts ─────────────────────────────────────────────────────
# Added 2026-08-15 after an audit found FOUR hand-maintained numbers had drifted at once: the
# test count (36 advertised against 40 actual, having already been corrected once before), the
# coverage header in tests/README.md (24 against 41), the line count in Ollamancer.md (~6,700
# against 7,727) and the module count in that same sentence ("fourteen", which counted the 12
# agentic/ modules plus two root files — a basis excluding the nine tool modules the line count
# in the same breath included).
#
# None is interesting alone. Together they are: a project whose front page says "the docs never
# claim something works from reading the code alone" was carrying six numbers nothing checked.
# Each is something the repo can count about itself, so from here it does.
#
# Split into one test per concern deliberately. As a single function it reported whichever
# drift it hit first and stopped, so a tool-count change masked a line-count change.

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(rel):
    return (_ROOT / rel).read_text()


def _claims(rel, pattern):
    """Every number a doc advertises for `pattern`, as ints."""
    return [int(m) for m in re.findall(pattern, _read(rel))]


def _real_test_files():
    """test_scripts.py is the pytest runner for the others, not a test; run_all.sh skips it."""
    return [p for p in (_ROOT / "tests").glob("test_*.py") if p.stem != "test_scripts"]


def test_docs_count_tools_settings_and_skills():
    """Tools, /parameters settings and bundled skills, as advertised on the front pages."""
    n_tools = len(tools.TOOL_MAP)
    for doc in ("README.md", "Ollamancer.md"):
        for found in _claims(doc, r"(\d+) native tools"):
            assert found == n_tools, f"{doc} advertises {found} native tools; registry has {n_tools}"

    n_params = len(ui._all_params())
    for doc in ("README.md", "Ollamancer.md"):
        for found in _claims(doc, r"(\d+) live-tunable settings"):
            assert found == n_params, (
                f"{doc} advertises {found} live-tunable settings; /parameters has {n_params}")

    n_skills = len(list((_ROOT / "skills").glob("*/SKILL.md")))
    for doc in ("README.md", "Ollamancer.md", "Agentic_Manual.md"):
        for found in _claims(doc, r"(\d+)-skill library"):
            assert found == n_skills, f"{doc} advertises a {found}-skill library; skills/ has {n_skills}"


def test_manual_counts_parameters_per_section():
    """The manual counts the same settings in its own words, and per section.

    Both spellings were stale within an hour of the first version of this check being written,
    which is the argument for verifying each phrasing rather than one canonical one.
    """
    n_params = len(ui._all_params())
    for found in _claims("Agentic_Manual.md", r"\*\*(\d+) parameters, 3 sections:\*\*"):
        assert found == n_params, f"Agentic_Manual.md says {found} parameters; there are {n_params}"

    per_section = collections.Counter()
    section = None
    for kind, entry in ui._flatten_schema():
        if kind == "header":
            section = entry
        else:
            per_section[section] += 1
    for label, count in re.findall(r"- \*\*([A-Za-z &]+) \((\d+)\)\*\*:", _read("Agentic_Manual.md")):
        if label in per_section:
            assert int(count) == per_section[label], (
                f"Agentic_Manual.md says {label} has {count} settings; it has {per_section[label]}")


def test_docs_count_tests_and_the_coverage_table_is_complete():
    """The advertised test count, in all six places it appears, plus the coverage table.

    A table that does not list every test file is decorative, and a count that disagrees with
    the runner sends someone hunting for a test that does not exist.
    """
    n_tests = len(_real_test_files())
    for doc, pattern in (("README.md", r"(\d+) deterministic tests"),
                         ("README.md", r"test suite \((\d+) tests\)"),
                         ("Ollamancer.md", r"test suite \((\d+) tests\)"),
                         ("tests/README.md", r"(\d+) scripts plus a collection guard"),
                         ("tests/README.md", r"tests: (\d+) passed"),
                         ("tests/README.md", r"## Coverage \((\d+) files\)")):
        for found in _claims(doc, pattern):
            assert found == n_tests, f"{doc} advertises {found} tests; tests/ holds {n_tests}"

    listed = set(re.findall(r"^\| `(test_[a-z0-9_]+)`", _read("tests/README.md"), re.M))
    actual = {p.stem for p in _real_test_files()}
    assert listed == actual, (
        f"tests/README.md coverage table out of step: "
        f"missing {sorted(actual - listed)}, stale {sorted(listed - actual)}")


def test_version_is_single_sourced():
    """config.VERSION, pyproject.toml and the docs must agree, and nothing may hard-code it.

    Added 2026-08-15 because bumping pyproject.toml to 3.1.0 left the running agent still
    introducing itself as "Ollamancer v3.0" — the version was typed into three separate
    strings (the startup banner and both /help headers) and none of them moved. The user saw
    it on the very next launch, which is the most visible possible place for this class of
    drift and the one the .md-only checks above could never catch.
    """
    pyproject = _read("pyproject.toml")
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert config.VERSION == declared, (
        f"config.VERSION is {config.VERSION}, pyproject.toml says {declared}")

    # The short form the docs advertise, e.g. "v3.1" for 3.1.0.
    short = ".".join(declared.split(".")[:2])
    for doc, pattern in (("README.md", r"Status: \*\*v([\d.]+)\*\*"),
                         ("Ollamancer.md", r"Version \*\*v([\d.]+)\*\*"),
                         ("Agentic_Manual.md", r"Local terminal AI agent · v([\d.]+)")):
        for found in re.findall(pattern, _read(doc)):
            assert found == short, f"{doc} advertises v{found}; pyproject says {declared}"

    # Nothing may hard-code it: every user-visible mention must read config.VERSION.
    for mod in ("agentic/cli.py", "agentic/i18n.py"):
        src = _read(mod)
        hard = re.findall(r"Ollamancer v(\d+\.\d+)", src)
        assert not hard, (
            f"{mod} hard-codes the version {hard}; use config.VERSION or the "
            "{version} placeholder so a bump cannot leave it behind")

    # And the placeholder must actually be substituted, in both languages.
    for lang in ("en", "fr"):
        saved = config.LANG
        try:
            config.LANG = lang
            rendered = i18n.get_help_text()
        finally:
            config.LANG = saved
        assert "{version}" not in rendered, f"/help leaks the raw placeholder in {lang}"
        assert f"Ollamancer v{config.VERSION}" in rendered, \
            f"/help does not show the current version in {lang}"


def test_docs_count_modules_and_lines():
    """Module and line counts, which must share a counting basis to mean anything.

    They did not: "~6,700 lines across fourteen focused modules" counted the tool modules in
    the line total and excluded them from the module total, so no single basis made both true.
    The basis is now stated in the doc and checked here.

    The line count carries a 10% tolerance because it moves with every commit and precision
    would just fail on unrelated work. It still catches real drift: the ~6,700 this replaced
    was 13% low.
    """
    pkg = [p for p in (_ROOT / "agentic").glob("*.py") if p.name != "__init__.py"]
    tool_mods = [p for p in (_ROOT / "agentic/tools").glob("*.py") if p.name != "__init__.py"]
    n_modules = len(pkg) + len(tool_mods)
    n_lines = sum(len(p.read_text().splitlines()) for p in pkg + tool_mods)

    for found in _claims("Ollamancer.md", r"across (\d+) focused modules"):
        assert found == n_modules, (
            f"Ollamancer.md says {found} focused modules; agentic/ has {len(pkg)} plus "
            f"{len(tool_mods)} tool modules = {n_modules}")

    for a, b in re.findall(r"(\d+) in `agentic/` plus (\d+) tool modules", _read("Ollamancer.md")):
        assert (int(a), int(b)) == (len(pkg), len(tool_mods)), (
            f"Ollamancer.md splits the module count as {a}+{b}; actual is {len(pkg)}+{len(tool_mods)}")

    for found in re.findall(r"~([\d,]+) lines of readable Python", _read("Ollamancer.md")):
        claimed = int(found.replace(",", ""))
        assert abs(claimed - n_lines) / n_lines < 0.10, (
            f"Ollamancer.md says ~{found} lines of Python; agentic/ is {n_lines}. "
            f"Round to the nearest hundred and update the doc.")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("test_structure: ALL PASS")
