"""The live token readout beside the RAM gauge, and the one formula behind it.

`/context` and the spinner ask almost the same question and would have been two copies of the
same arithmetic — the shape that has drifted in this repo before (six hand-maintained numbers,
audited 2026-08-15). They share `loop._context_usage()` instead, and the flag that separates
them is the point of this file.

The distinction is not cosmetic. `state._LAST_PROMPT_TOKENS` is exact for the prompt that was
last *sent*, which is what `/context` wants between turns. Mid-turn it is stale the moment a
tool result is appended, and after a compaction it is stale **high** — a readout using it would
show the context filling up at the exact moment it was emptied, which is the opposite of what
the gauge exists to tell you. So the live path estimates what is in hand instead, and says so
with a tilde.

Offline: `get_num_ctx` is stubbed, no model is contacted.

    PYTHONPATH="$PWD" python tests/test_context_readout.py
"""

import pathlib
import re

from agentic import loop, models, state

_real_num_ctx = models.get_num_ctx
_real_schema = loop._tool_schema_tokens
_real_last = state._LAST_PROMPT_TOKENS
_real_anchor = state._LAST_PROMPT_MSG_COUNT

CAP = 49152
SCHEMA = 5800

try:
    models.get_num_ctx = lambda m: CAP
    loop._tool_schema_tokens = lambda s=None: SCHEMA

    msgs = [{"role": "user", "content": "x" * 4000}]        # 1000 tokens of content

    state._LAST_PROMPT_MSG_COUNT = 0        # tests 1-4 run with no anchor

    # ── 1. /context prefers Ollama's real count, and does not call it an estimate ──
    state._LAST_PROMPT_TOKENS = 12345
    used, cap, pct, estimated = loop._context_usage(msgs, "m")
    assert (used, cap, estimated) == (12345, CAP, False), (used, cap, estimated)
    assert pct == int(12345 / CAP * 100), pct

    # ── 2. With no real count yet (turn 1) it estimates, and admits it ───────
    state._LAST_PROMPT_TOKENS = 0
    used, _cap, _pct, estimated = loop._context_usage(msgs, "m")
    assert estimated is True, "a chars/4 guess must never be reported as a measurement"
    assert used == 1000 + SCHEMA, f"estimate must include the tool schemas, got {used}"

    # ── 3. The live readout ignores the real count even when one exists ──────
    state._LAST_PROMPT_TOKENS = 12345
    used, _cap, _pct, estimated = loop._context_usage(msgs, "m", prefer_real=False)
    assert (used, estimated) == (1000 + SCHEMA, True), (used, estimated)

    # ── 4. The compaction case, which is why prefer_real=False exists ────────
    # Messages shrank; the last real count is now higher than what will be sent. The live
    # gauge must fall, not stay pinned at a stale high-water mark.
    small = [{"role": "user", "content": "y" * 400}]        # 100 tokens
    live, _c, _p, _e = loop._context_usage(small, "m", prefer_real=False)
    assert live == 100 + SCHEMA, live
    assert live < state._LAST_PROMPT_TOKENS, (
        "after a compaction the live readout must reflect the smaller prompt actually being "
        "sent, not the larger one that preceded it")

    # ── 4b. Anchoring: price only what was appended since the last real count ─
    # Estimating the whole prompt is +23% high on a real model, because the tool schemas
    # dominate a short conversation and chars/4 over-counts punctuation-dense JSON. Anchoring
    # to Ollama's exact figure and guessing only the delta measured -0.2% and -0.1% on
    # gemma4:12b-mlx. The schema term stops being guessed at all.
    state._LAST_PROMPT_TOKENS = 4839
    state._LAST_PROMPT_MSG_COUNT = 1
    grown = msgs + [{"role": "assistant", "content": "z" * 400}]     # +100 tokens
    used, _c, _p, estimated = loop._context_usage(grown, "m", prefer_real=False)
    assert used == 4839 + 100, used
    assert estimated is True, "anchored is still part guess, so it keeps the tilde"

    # ── 4c. A compaction invalidates the anchor rather than corrupting it ─────
    # After compaction the list is shorter than the anchor, so messages[anchor:] would be
    # empty and the gauge would freeze at the pre-compaction figure — the exact stale-high
    # bug this whole flag exists to avoid. It must fall back to pricing the whole thing.
    state._LAST_PROMPT_MSG_COUNT = 99          # anchor beyond the (now shorter) conversation
    used, _c, _p, _e = loop._context_usage(small, "m", prefer_real=False)
    assert used == 100 + SCHEMA, f"must fall back to a full estimate, got {used}"
    assert used != 4839, (
        "the anchored branch would have returned the pre-compaction figure unchanged, since "
        "messages[99:] is empty — the fallback is what stops the gauge freezing there")
    state._LAST_PROMPT_MSG_COUNT = 0

    # ── 5. Tool schemas are counted; omitting them understates by ~18% of 32K ─
    bare = loop._estimate_tokens(msgs)
    withschema, *_ = loop._context_usage(msgs, "m", prefer_real=False)
    assert withschema - bare == SCHEMA, "the belt rides on every request and must be counted"

    # ── 6. The suffix marks estimates and disappears when there is nothing to say ──
    assert loop._usage_suffix(None) == "", "no usage -> no clause, not a zero"
    assert "~" in loop._usage_suffix((6800, CAP, 13, True)), "an estimate must carry its tilde"
    assert "~" not in loop._usage_suffix((12345, CAP, 25, False)), "a real count must not"
    for frag in ("6.8k", "49.2k", "13%"):
        assert frag in loop._usage_suffix((6800, CAP, 13, True)), frag

    # ── 7. Compact formatting ────────────────────────────────────────────────
    assert loop._fmt_tokens(940) == "940"
    assert loop._fmt_tokens(8420) == "8.4k"
    assert loop._fmt_tokens(49152) == "49.2k"

    # ── 8. A zero cap must not divide by zero ────────────────────────────────
    models.get_num_ctx = lambda m: 0
    assert loop._context_usage(msgs, "m", prefer_real=False)[2] == 0, "pct must be 0, not a crash"
    models.get_num_ctx = lambda m: CAP

    # ── 9. Both callers really do go through the one helper ──────────────────
    # The whole reason this function exists. If /context grows its own copy of the arithmetic
    # again, the two readouts can disagree and nothing else would notice.
    cli_src = (pathlib.Path(__file__).resolve().parent.parent / "agentic" / "cli.py").read_text()
    assert "loop._context_usage(" in cli_src, "/context must use the shared helper"
    assert not re.search(r"_LAST_PROMPT_TOKENS\s+or\s+loop\._estimate_tokens", cli_src), (
        "/context has grown a second copy of the usage arithmetic")

    loop_src = (pathlib.Path(__file__).resolve().parent.parent / "agentic" / "loop.py").read_text()
    assert "_start_ram_spinner(usage)" in loop_src, "the streaming spinner must receive the usage"
    assert loop_src.count("label += _usage_suffix(usage)") == 2, (
        "both spinners must render the clause through the same helper")

    # ── 10. The post-turn line reports both meanings of "tokens used" ────────
    # The spinner could only ever show the prompt, and only as an estimate: Ollama reports
    # usage in its final chunk alone, and rich's Status is transient, so it erases itself
    # before it can be read. Printed after the answer, both numbers are real.
    state._LAST_PROMPT_TOKENS = 12400
    state._TURN_EVAL_TOKENS = 391
    line = loop.turn_token_line(msgs, "m")
    assert "context 12.4k/49.2k (25%)" in line, line
    assert "generated 391" in line, line
    assert "~" not in line, "both figures are exact after the turn; no tilde"

    # ── 11. Generated tokens are summed over the turn, not per call ──────────
    # One turn is several rounds and each reports only its own eval_count, so the per-call
    # figure would silently under-report every multi-round turn — which is all of them.
    src = (pathlib.Path(__file__).resolve().parent.parent / "agentic" / "loop.py").read_text()
    assert "state._TURN_EVAL_TOKENS += " in src, "must accumulate, not assign"
    assert "state._TURN_EVAL_TOKENS = 0" in src, "must reset at the start of each turn"

    # ── 12. A turn that generated nothing says so by omission, not by "0" ────
    state._TURN_EVAL_TOKENS = 0
    assert "generated" not in loop.turn_token_line(msgs, "m"), (
        "an unknown count must be left out rather than reported as zero")

    # ── 13. The streaming path actually carries eval_count ───────────────────
    # It was discarded entirely before this: _StreamedResp kept prompt_eval_count and dropped
    # the other half, so the buffered path had the number and the default path did not.
    from agentic import ui as _ui
    resp = _ui._StreamedResp(object(), prompt_eval_count=100, eval_count=42)
    assert resp.eval_count == 42, "the streamed response must carry the generated-token count"
    assert _ui._StreamedResp(object()).eval_count == 0, "and default to 0"

    print("test_context_readout: OK")

finally:
    models.get_num_ctx = _real_num_ctx
    loop._tool_schema_tokens = _real_schema
    state._LAST_PROMPT_TOKENS = _real_last
    state._LAST_PROMPT_MSG_COUNT = _real_anchor
    state._TURN_EVAL_TOKENS = 0
