"""pytest configuration for the Agentic_1A suite.

Two jobs, and the first one is the reason this file is careful rather than boilerplate.

**1. Keep pytest away from the legacy scripts.**
`tests/test_*.py` are standalone assertion scripts, not pytest modules: the assertions
run at import time, and roughly two thirds of them mutate module globals
(`config.STREAM_FINAL`, `state.PROJECT_ROOT`, `ollama.chat`, ...). Left to itself pytest
would import all of them into one interpreter and they would corrupt each other, with
whichever test happened to be collected last deciding the result. So they are excluded
from collection here and executed instead by `test_scripts.py`, one subprocess each.
That is not a workaround: the isolation is the contract those tests were written under.

**2. Refuse to let the suite touch the user's real configuration.**
A session fixture checksums every `~/.agentic_1a_*` file before and after the run and
fails if any changed. This mirrors the same guard in `run_all.sh` and exists because it
already happened: a `/parameters` round-trip in `test_structure` once rewrote the live
`~/.agentic_1a_params.json`, moving every setting one step (`GEN_NUM_PREDICT` from -1 to
127, which silently truncates every answer). The suite was green and the install was
broken. A test that can reach real state will eventually corrupt it, so the check lives
outside the tests.

New tests should be written as ordinary pytest functions in files named
`check_*.py`, or as functions inside `test_scripts.py`. They get `clean_state` for free.
"""

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Every legacy script, excluded from collection and run as a subprocess instead.
# test_scripts.py is the runner, so it must stay collectable.
collect_ignore = [
    p.name for p in sorted(Path(__file__).parent.glob("test_*.py"))
    if p.name != "test_scripts.py"
]

_CONFIG_FILES = [
    "~/.agentic_1a_params.json",
    "~/.agentic_1a_history",
    "~/.agentic_1a_models.json",
    "~/.agentic_1a_default_model.txt",
    "~/.agentic_1a_mcp.json",
]


def _config_fingerprint() -> dict[str, str]:
    out = {}
    for name in _CONFIG_FILES:
        p = Path(name).expanduser()
        if p.exists():
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="session", autouse=True)
def real_config_untouched():
    """Fail the run if anything wrote to the user's real configuration."""
    before = _config_fingerprint()
    yield
    after = _config_fingerprint()
    if before != after:
        changed = sorted(
            k for k in set(before) | set(after) if before.get(k) != after.get(k)
        )
        pytest.fail(
            "the test suite modified the real user configuration: "
            + ", ".join(changed)
            + ". Tests must redirect config.PARAMS_FILE and friends to a tmp_path.",
            pytrace=False,
        )


@pytest.fixture(autouse=True)
def clean_state():
    """Reset per-session runtime state around every test.

    `state.reset()` restores every per-session global to its startup default and clears
    the caches in place, without touching `config`, so settings survive and only the
    session does not. Anything a test monkeypatches that is *not* state, such as
    `ollama.chat`, still has to be restored by the test itself, which is what pytest's
    own `monkeypatch` fixture is for.
    """
    from agentic import state

    state.reset()
    yield
    state.reset()
