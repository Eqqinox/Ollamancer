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

# Modules whose contents must always be reached through the module object.
LIVE_MODULES = {"config", "state"}


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


if __name__ == "__main__":
    test_no_by_name_imports_from_live_modules()
    test_no_globals_mutation_of_live_values()
    print("test_import_rules: ALL PASS")
