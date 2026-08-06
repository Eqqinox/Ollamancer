"""Enforces the one import rule the modularization depends on.

`config` and `state` hold values that are **rebound at runtime** — by the /parameters menu,
by `/lang`, by `--private`, by `--safe`, by the architect/editor swap, and by the tests
themselves. In Python, `from .config import STREAM_FINAL` copies the value into the importing
module at import time; later rebinding of `config.STREAM_FINAL` is then invisible to it.

The failure is silent and total: the code reads a stale constant forever, no exception is
raised, and behavioural tests that set the value the same wrong way still pass. So the rule is
mechanical and checked mechanically:

    from . import config          #  OK — binds the module, sees every later change
    import agentic.config         #  OK
    config.STREAM_FINAL           #  OK — resolved at each access
    from .config import STREAM_FINAL   # BANNED — frozen copy

Anything genuinely immutable and hot (regex patterns, lookup tables) can be imported by name
from any *other* module; this rule covers only `config` and `state`.

The test passes trivially until the `agentic/` package exists, so it can land before the split.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "agentic"

# Modules whose contents must ALWAYS be reached through the module object: everything in
# them is rebound at runtime, so no by-name import is ever correct.
LIVE_MODULES = {"config", "state"}

# `ui` is mixed: most of it is stable (the _SLASH_COMMANDS table, the _prompt helper), but
# two names really are rebound mid-run and must never be imported by name.
#   console         -> swapped for a stderr console in headless mode
#   _prompt_session -> rebuilt with an in-memory history under --private
REBOUND_NAMES = {"ui": {"console", "_prompt_session"}}

# Binding a local with one of these names hides the module inside that function/scope.
# `ui` is included because `ui.console` is used ~230 times; a stray `ui = ...` would be fatal.
SHADOW_MODULES = LIVE_MODULES | {"ui"}


def _offending_imports(path: pathlib.Path) -> list[str]:
    """Return `from ... import NAME` statements that copy live values out of config/state."""
    tree = ast.parse(path.read_text(), filename=str(path))
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = (node.module or "").split(".")[-1]
        if module not in LIVE_MODULES:
            continue
        # `from . import config` has module=None/parent and names=[config] — that's the good form.
        imported = {alias.name for alias in node.names}
        if imported & LIVE_MODULES and module not in LIVE_MODULES:
            continue
        names = ", ".join(sorted(imported))
        problems.append(f"{path.relative_to(ROOT)}:{node.lineno}: from ...{module} import {names}")
    return problems


def test_no_by_name_imports_from_live_modules():
    if not PACKAGE.is_dir():
        return  # the package does not exist yet — nothing to enforce
    problems = []
    for py in sorted(PACKAGE.rglob("*.py")):
        problems.extend(_offending_imports(py))
    assert not problems, (
        "live values must be read through the module object, never imported by name "
        "(a `from x import NAME` copy never sees a later rebinding):\n  "
        + "\n  ".join(problems)
        + "\n\nUse `from . import config` and read `config.NAME` at the point of use."
    )


def test_no_by_name_imports_of_rebound_names():
    """Names that are rebound at runtime must not be imported by name, even from a module
    that is otherwise safe to import from.

    `from agentic.ui import console` looks harmless and is not: headless mode replaces
    ui.console with one writing to stderr, and a by-name copy would keep printing the banner
    to stdout, corrupting the only thing --run is supposed to emit.
    """
    files = [ROOT / "agent.py", ROOT / "imessage_bridge.py"]
    files += sorted((ROOT / "tests").glob("*.py"))
    if PACKAGE.is_dir():
        files += sorted(PACKAGE.rglob("*.py"))
    problems = []
    for py in files:
        if not py.exists():
            continue
        for node in ast.walk(ast.parse(py.read_text(), filename=str(py))):
            if not isinstance(node, ast.ImportFrom):
                continue
            mod = (node.module or "").split(".")[-1]
            banned = REBOUND_NAMES.get(mod, set())
            hit = {a.name for a in node.names} & banned
            if hit:
                problems.append(f"{py.relative_to(ROOT)}:{node.lineno}: "
                                f"from ...{mod} import {', '.join(sorted(hit))}")
    assert not problems, (
        "these names are rebound at runtime and must be read through the module:\n  "
        + "\n  ".join(problems) + "\n\nUse `from agentic import ui` and read `ui.console`."
    )


def test_no_globals_mutation_of_live_values():
    """`globals()[var] = value` cannot cross a module boundary.

    /parameters originally adjusted tunables with `globals()[p["var"]] = ...`, which worked
    only while the schema and the variables lived in the same module. Once the tunables move
    to `config`, that write lands in the wrong namespace — the menu appears to work and the
    agent never sees the value. It must become `setattr(config, var, value)`.
    """
    if not PACKAGE.is_dir():
        return
    problems = []
    for py in sorted(PACKAGE.rglob("*.py")):
        if py.stem in LIVE_MODULES:
            continue  # a live module writing its own globals() is fine
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            # Matches subscript assignment/read on a globals() call: globals()[...]
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call):
                fn = node.value.func
                if isinstance(fn, ast.Name) and fn.id == "globals":
                    problems.append(f"{py.relative_to(ROOT)}:{node.lineno}: globals()[...]")
    assert not problems, (
        "globals()[...] cannot reach values that live in another module:\n  "
        + "\n  ".join(problems)
        + "\n\nUse getattr/setattr on the owning module (e.g. setattr(config, var, value))."
    )


def test_no_local_shadows_a_live_module():
    """No function may bind a local named `config` or `state`.

    Python decides scope per function: a single `config = ...` anywhere in a function makes
    every `config.X` in that function a local reference, so the *module* becomes unreachable
    and the function dies with UnboundLocalError. `_init_mcp` had exactly this — it already
    used `config` as the name of the parsed MCP JSON — and no behavioural test covered MCP
    startup, so the suite stayed green while the agent could not start with MCP configured.
    """
    targets = set(SHADOW_MODULES)
    # tests count too: test_a7 shadowed `state` with its own counter dict and failed the
    # same way _init_mcp did, so the scan covers every file that imports the live modules.
    files = [ROOT / "agent.py", ROOT / "imessage_bridge.py"]
    files += sorted((ROOT / "tests").glob("*.py"))
    if PACKAGE.is_dir():
        files += sorted(PACKAGE.rglob("*.py"))

    problems = []
    for py in files:
        if not py.exists():
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        # module level: a top-level `state = ...` clobbers the imported module outright
        for n in tree.body:
            tgts = n.targets if isinstance(n, ast.Assign) else (
                [n.target] if isinstance(n, (ast.AugAssign, ast.AnnAssign)) else [])
            for t_ in tgts:
                if isinstance(t_, ast.Name) and t_.id in targets:
                    problems.append(f"{py.relative_to(ROOT)}:{n.lineno}: module-level "
                                    f"{t_.id!r} overwrites the imported module")
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            bound = set()
            for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs:
                if a.arg in targets:
                    bound.add(a.arg)
            for n in ast.walk(fn):
                tgts = []
                if isinstance(n, ast.Assign):
                    tgts = n.targets
                elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For)):
                    tgts = [n.target]
                elif isinstance(n, ast.withitem) and n.optional_vars:
                    tgts = [n.optional_vars]
                for t in tgts:
                    # only a bare Name binds; `config.X = ...` is an Attribute and is fine
                    if isinstance(t, ast.Name) and t.id in targets:
                        bound.add(t.id)
            for name in sorted(bound):
                problems.append(f"{py.relative_to(ROOT)}:{fn.lineno}: {fn.name}() binds a local "
                                f"named {name!r}, shadowing the module")
    assert not problems, (
        "a local with the same name as a live module makes that module unreachable inside the "
        "function (UnboundLocalError at runtime):\n  " + "\n  ".join(problems)
        + "\n\nRename the local (e.g. mcp_config)."
    )


if __name__ == "__main__":
    test_no_by_name_imports_from_live_modules()
    test_no_globals_mutation_of_live_values()
    test_no_by_name_imports_of_rebound_names()
    test_no_local_shadows_a_live_module()
    print("test_import_rules: ALL PASS")
