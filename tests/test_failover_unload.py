"""A plumbing failover must unload the model it is failing away from.

`models.py` states the invariant: two resident models do not fit in 24 GB. `cmd_architect`
and `cmd_review_by` honour it at four call sites. The three failover branches did not — each
did a bare `model = target` — and the omission survived precisely because it was written three
times instead of once.

It was also unreachable by default: `PLUMBING_FAILOVER_MODEL` ships as `""`, so
`_plumbing_failover_target()` returns nothing and the branch never executes. The first real
failover after a backup model was configured stalled a turn for ten minutes, paging two
co-resident models (13.2 GB + 4.2 GB) on a 24 GB machine.

Both halves are pinned here: that the switch unloads, and that all three branches go through
the one helper rather than growing a fourth copy of the same three lines.

Offline: nothing is loaded or unloaded for real — `models._unload_model` is a spy.

    PYTHONPATH="$PWD" python tests/test_failover_unload.py
"""

import re
from pathlib import Path

from agentic import loop, models

_real_unload = models._unload_model
_real_console = loop.ui.console
_real_audit = loop.safety._audit

unloaded: list = []
audited: list = []


class _Sink:
    def print(self, *a, **k): pass
    def __getattr__(self, _): return lambda *a, **k: None


try:
    models._unload_model = lambda m: unloaded.append(m)
    loop.ui.console = _Sink()
    loop.safety._audit = lambda kind, payload: audited.append((kind, payload))

    # ── 1. The switch returns the target AND unloads the model it left ───────
    got = loop._failover_to("qwen-heretic:latest", "qwen3.5:4b", "json_truncation", 7)
    assert got == "qwen3.5:4b", f"failover must return the new model, got {got}"
    assert unloaded == ["qwen-heretic:latest"], \
        f"the failed model must be unloaded, not left resident — got {unloaded}"

    # ── 2. It unloads the OLD one, never the new one ─────────────────────────
    # Getting this backwards would be worse than not unloading at all: the turn would
    # continue against a model that was just evicted.
    assert "qwen3.5:4b" not in unloaded, "unloaded the model we are switching TO"

    # ── 3. The audit record still names both sides and the trigger ───────────
    kinds = [k for k, _ in audited]
    assert kinds == ["MODEL_FAILOVER"], kinds
    payload = audited[0][1]
    assert payload["from"] == "qwen-heretic:latest" and payload["to"] == "qwen3.5:4b"
    assert payload["trigger"] == "json_truncation" and payload["round"] == 7

    # ── 4. Every failover branch goes through the helper ────────────────────
    # The bug existed because the same three lines were written three times. If a fourth
    # signature is added later with its own inline `model = target`, this fails.
    src = Path(loop.__file__).read_text()
    body = src[src.index("def run_agent"):]
    inline = re.findall(r"^\s*model = target\s*$", body, re.M)
    assert not inline, f"{len(inline)} failover branch(es) still switch models inline, skipping the unload"
    assert len(re.findall(r"model = _failover_to\(", body)) == 3, \
        "expected exactly three failover branches routed through _failover_to"

    # ── 5. The helper actually calls the unloader ───────────────────────────
    # Guards against someone 'tidying' the helper back into a bare return.
    helper = src[src.index("def _failover_to("):]
    helper = helper[:helper.index("\ndef ", 1)]
    assert "_unload_model" in helper, "the helper no longer unloads anything"
finally:
    models._unload_model = _real_unload
    loop.ui.console = _real_console
    loop.safety._audit = _real_audit

print("test_failover_unload: all assertions passed")
