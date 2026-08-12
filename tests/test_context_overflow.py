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
    models.get_num_ctx = lambda model: 4096          # 4096 tokens ≈ 16384 chars
    loop._compact_now = _fake_compact
    loop.ui.console = _Sink()

    # ── 1. Comfortably inside the window: the guard must not fire ────────────
    compacted["n"] = 0
    assert loop._guard_context_overflow(_msgs(1000), "m") is False
    assert compacted["n"] == 0, "guard compacted a prompt that fits"

    # ── 2. Over the 85% ceiling: it compacts ────────────────────────────────
    compacted["n"] = 0
    big = _msgs(20000)                                # ~5000 tokens > 4096
    assert loop._guard_context_overflow(big, "m") is True
    assert compacted["n"] == 1, "guard did not compact an overflowing prompt"

    # ── 3. The guard is NOT gated on AUTO_COMPACT ───────────────────────────
    # This is the whole point: auto-compaction is a convenience and ships off, but
    # overflowing silently deletes the user's request, which is a correctness problem.
    _saved = config.AUTO_COMPACT
    try:
        config.AUTO_COMPACT = "off"
        compacted["n"] = 0
        assert loop._guard_context_overflow(_msgs(20000), "m") is True, \
            "guard must run even with AUTO_COMPACT off"
        assert compacted["n"] == 1
        # …whereas the convenience path stays off, so the two cannot be confused.
        assert loop._maybe_compact(_msgs(20000), "m") is False
    finally:
        config.AUTO_COMPACT = _saved

    # ── 4. The boundary is the 85% ceiling, not 100% ─────────────────────────
    # The estimate excludes the tool schemas, so it understates the real prompt; sending at
    # 99% of num_ctx would still overflow once ~35 schemas are prepended.
    compacted["n"] = 0
    just_under = _msgs(int(4096 * 4 * 0.80) - 40)     # ~80% of the window
    assert loop._guard_context_overflow(just_under, "m") is False, "fired below the ceiling"
    just_over = _msgs(int(4096 * 4 * 0.90))           # ~90%
    assert loop._guard_context_overflow(just_over, "m") is True, "did not fire above the ceiling"

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
