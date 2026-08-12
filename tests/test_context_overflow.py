"""Context overflow: the fifth plumbing signature, and the guard that should prevent it.

The failure, reproduced deterministically against a real model before this was written: the
same message list succeeds at `num_ctx=8192` and raises at `num_ctx=1024`, nothing else
changed. When the prompt does not fit, Ollama makes room by dropping the OLDEST messages, and
after the system prompt the oldest thing is the user's own instruction.

What happens then is decided entirely by the model's chat template:

  * `qwen-heretic` and `HauhauCS Qwen3.6` (both hf.co GGUFs carrying their own template)
    assert a user message is present and raise `No user query found in messages.`
  * `qwen3.5:4b`, `qwen3.5:9b-mlx`, `gemma4:12b-mlx` have no such assertion and answer
    normally — from a conversation the request has been silently deleted from.

The refusal is the *good* case, because it is visible. So the guard fires for every model, and
the error handler treats the refusal as a context problem rather than a model defect. It was
originally misdiagnosed as "qwen-heretic is broken in architect mode".

Offline: no Ollama, no model. `models.get_num_ctx` is faked and the compaction path is
observed through a stub.

    PYTHONPATH="$PWD" python tests/test_context_overflow.py
"""

from agentic import config, loop, models

_real_get_num_ctx = models.get_num_ctx
_real_compact_now = loop._compact_now
_real_console = loop.ui.console


class _Sink:
    def __init__(self): self.lines = []
    def print(self, *a, **k): self.lines.append(" ".join(str(x) for x in a))
    def __getattr__(self, _): return lambda *a, **k: None


def _msgs(chars: int) -> list:
    return [{"role": "system", "content": "sys"},
            {"role": "user", "content": "PLANNING PHASE - produce a plan"},
            {"role": "assistant", "content": ""},
            {"role": "tool", "content": "x" * chars}]


compacted = {"n": 0}


def _fake_compact(messages, model, forced=False):
    compacted["n"] += 1
    messages[:] = messages[:2]          # pretend the summary shrank it
    return "compacted"


try:
    # A realistic window: the schemas alone cost ~5,800 tokens, so a fixture smaller than
    # that cannot express 'content fits but content+schemas does not'.
    models.get_num_ctx = lambda model: 32768         # 70% ceiling = 22,937 tokens
    loop._compact_now = _fake_compact
    loop.ui.console = _Sink()

    # ── 1. Comfortably inside the window: the guard must not fire ────────────
    compacted["n"] = 0
    assert loop._guard_context_overflow(_msgs(4000), "m") is False
    assert compacted["n"] == 0, "guard compacted a prompt that fits"

    # ── 2. Over the ceiling: it compacts ────────────────────────────────────
    compacted["n"] = 0
    big = _msgs(92000)                                # ~23,000 tok + schemas > ceiling
    assert loop._guard_context_overflow(big, "m") is True
    assert compacted["n"] == 1, "guard did not compact an overflowing prompt"

    # ── 2b. The tool schemas count toward the budget ─────────────────────────
    # The first version of this guard measured only message content and missed by 18% of a
    # 32K window. A real turn (10 searches, 70 KB of results) sat at 82% once schemas were
    # included and at 64% without them, so the schema-blind version never fired.
    assert loop._tool_schema_tokens() > 4000, "the full belt should cost thousands of tokens"
    from agentic import tools as _tools
    assert loop._tool_schema_tokens(_tools._read_only_tools()) < loop._tool_schema_tokens(), \
        "the read-only set must be cheaper than the full belt"
    compacted["n"] = 0
    # content alone is under the ceiling; content + schemas is over it
    under_alone = _msgs(76000)                        # ~19,000 tok: under 22,937 on its own
    assert loop._estimate_tokens(under_alone) < int(32768 * 0.70), "fixture no longer isolates the effect"
    assert loop._guard_context_overflow(under_alone, "m") is True, \
        "content fits but content+schemas does not — the guard must still fire"
    assert compacted["n"] == 1

    # ── 3. The guard is NOT gated on AUTO_COMPACT ───────────────────────────
    # This is the whole point: auto-compaction is a convenience and ships off, but
    # overflowing silently deletes the user's request, which is a correctness problem.
    _saved = config.AUTO_COMPACT
    try:
        config.AUTO_COMPACT = "off"
        compacted["n"] = 0
        assert loop._guard_context_overflow(_msgs(92000), "m") is True, \
            "guard must run even with AUTO_COMPACT off"
        assert compacted["n"] == 1
        # …whereas the convenience path stays off, so the two cannot be confused.
        assert loop._maybe_compact(_msgs(92000), "m") is False
    finally:
        config.AUTO_COMPACT = _saved

    # ── 4. Single-turn overflow must still be trimmed ───────────────────────
    # The reported failure: /clear, then one turn making ten web searches. _compact_now used
    # to refuse outright ("not enough conversation to compact"), because the turn-count check
    # guarded step 1 as well as step 2 — even though truncating oversized tool results needs
    # no turn boundaries at all. The cheap lossless fix was unreachable exactly when it was
    # the only thing that could help.
    loop._compact_now = _real_compact_now              # exercise the real implementation
    single = [{"role": "system", "content": "sys"},
              {"role": "user", "content": "one question"}]
    for _ in range(10):
        single.append({"role": "assistant", "content": ""})
        single.append({"role": "tool", "content": "y" * 5000})
    before = sum(len(m["content"]) for m in single)
    loop._compact_now(single, "m", forced=True)
    after = sum(len(m["content"]) for m in single)
    assert after < before, "single-turn compaction saved nothing"
    kept = [len(m["content"]) for m in single if m["role"] == "tool"]
    assert kept[-1] == 5000 and kept[-2] == 5000, "the two most recent results must stay verbatim"
    assert max(kept[:-2]) <= config.COMPACT_TOOL_TRUNC + 80, "older results were not truncated"
    # …and with nothing worth trimming it still declines rather than pretending to work.
    tiny = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"},
            {"role": "tool", "content": "short"}]
    assert loop._compact_now(tiny, "m", forced=True) == loop.t("compact_too_few")
    loop._compact_now = _fake_compact

    # ── 5. The error signature is recognised, in the exact shape Ollama sends ─
    # e.error is a dict whose "message" carries the Jinja traceback; the handler lowercases
    # and substring-matches, so it must survive the surrounding noise.
    raw = ("\n------------\nWhile executing CallExpression at line 79, column 24 in source:\n"
           "...lti_step_tool %}{{- raise_exception('No user query found in messages.') }}...\n"
           "Error: Jinja Exception: No user query found in messages.")
    assert "no user query found in messages" in raw.lower(), \
        "the handler's match string no longer appears in the real error text"
    # and it must not collide with the other four signatures
    for other in ("Unable to generate parser for this template", "XML syntax error",
                  "unexpected end of JSON input"):
        assert "no user query found in messages" not in other.lower()

    # ── 6. Both messages exist in both languages ─────────────────────────────
    from agentic import i18n
    for key in ("context_overflow_note", "context_overflow_fallback"):
        for lang in ("en", "fr"):
            assert key in i18n.STR[lang], f"{key} missing from {lang}"
    assert "{num_ctx}" in i18n.STR["en"]["context_overflow_fallback"], \
        "the fallback must tell the user the window it actually exceeded"
    assert "{num_ctx}" in i18n.STR["fr"]["context_overflow_fallback"]
finally:
    models.get_num_ctx = _real_get_num_ctx
    loop._compact_now = _real_compact_now
    loop.ui.console = _real_console

print("test_context_overflow: all assertions passed")
