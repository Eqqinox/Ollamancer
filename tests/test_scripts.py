"""Run every standalone test script as its own pytest case.

Each of the `tests/test_*.py` scripts is executed in a **separate interpreter**, which is
what they were written to expect: they assert at import time and most of them mutate
module globals. See `conftest.py` for why importing them into a shared process is not an
option.

The gain over calling `run_all.sh` is reporting rather than isolation. pytest names each
script, shows its actual stdout and stderr on failure instead of a bare exit code, and
gives CI something machine-readable. `run_all.sh` still works and does the same thing;
neither is a wrapper around the other.

    pytest tests/                     # everything
    pytest tests/ -k skills           # one script
    pytest tests/ -x                  # stop at the first failure
"""

import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent

SCRIPTS = sorted(
    p for p in TESTS_DIR.glob("test_*.py") if p.name != Path(__file__).name
)

# A generous ceiling. Nothing here touches the network or Ollama, so a script that runs
# this long has hung rather than slowed down, and a hung suite in CI is worse than a
# failed one.
TIMEOUT_S = 120


@pytest.mark.parametrize("script", SCRIPTS, ids=[p.stem for p in SCRIPTS])
def test_script(script: Path):
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env={**_clean_env(), "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        stdin=subprocess.DEVNULL,   # a test that reaches the real prompt must fail, not hang
    )
    if proc.returncode != 0:
        pytest.fail(
            f"{script.name} exited {proc.returncode}\n\n"
            f"--- stdout ---\n{proc.stdout.strip() or '(empty)'}\n\n"
            f"--- stderr ---\n{proc.stderr.strip() or '(empty)'}",
            pytrace=False,
        )


def _clean_env() -> dict:
    """The parent environment, minus anything that would change what is under test."""
    import os

    env = dict(os.environ)
    env.pop("AGENTIC_LANG", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def test_every_script_is_collected():
    """Guard against a new script being silently skipped.

    `conftest.collect_ignore` and the `SCRIPTS` list are built by two different globs. If
    they ever disagree, a test file would be both ignored by pytest and absent from this
    runner, and would quietly stop being run at all while the suite stayed green.
    """
    from conftest import collect_ignore

    ignored = set(collect_ignore)
    running = {p.name for p in SCRIPTS}
    assert ignored == running, (
        "collect_ignore and the script list disagree; "
        f"only ignored: {sorted(ignored - running)}, only run: {sorted(running - ignored)}"
    )
