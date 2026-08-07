"""A degenerating answer must not be nudged again, and generation must have a ceiling.

Both guard the same real incident: three nudges fired back-to-back (citation, grounding,
claim-vs-action), each triggering a full rewrite; the model collapsed into repeating itself,
and with Max Output Tokens at -1 it kept generating toward the 64K context. Measured at
~6 tok/s that is ~3 hours of apparent hang, with nothing on screen.
"""
import agent  # noqa: F401
from agentic import config, loop, i18n

# ── 1. the detector fires on real degenerate output ──────────────────────────
degenerate = "\n".join(
    ["Here's the international news roundup for Thursday, August 6, 2026, compiled from multiple sources:"] * 8
)
assert loop._looks_repetitive(degenerate), "should catch a repeated header"

apology_loop = "\n".join(
    ["You're absolutely right — let me carefully verify each value against what my tools returned."] * 5
)
assert loop._looks_repetitive(apology_loop), "should catch the apology loop"

# ── 2. it does NOT fire on a legitimate answer ───────────────────────────────
real_answer = """Here are the major international news stories for Thursday, August 6, 2026:

- Strait of Hormuz deal in final stage — Iran says it is drafting an agreement with Oman.
- Yemen Houthis escalate with major attacks on government troops in Marib and Hadramout.
- Israeli soldiers killed in Lebanon; negotiators met in Rome over the June truce.
- Uganda approves sending troops for the international force in Gaza.
- FIFA president Infantino retains internal support after a crisis meeting in Morocco.

Sources: AP News, NPR, The Guardian, BBC.
"""
assert not loop._looks_repetitive(real_answer), "must not fire on a normal answer"

# repeated *short* lines (bullets, rules, blank separators) are not degeneration
assert not loop._looks_repetitive("- a\n- b\n- c\n" + "-" * 40 + "\n" + "-" * 40)
assert not loop._looks_repetitive(""), "empty answer is not repetitive"
assert not loop._looks_repetitive(None or ""), "None-safe"

# a line repeated only twice is not yet a loop (headers legitimately recur)
twice = "This is a reasonably long line that appears exactly twice here.\n" * 2
assert not loop._looks_repetitive(twice), "two occurrences is not a loop"

# ── 3. generation is bounded by default ─────────────────────────────────────
assert config.GEN_NUM_PREDICT > 0, (
    "GEN_NUM_PREDICT must default to a finite ceiling: with -1 a repetition loop "
    "generates until the context is full (~3 hours at 6 tok/s)")
assert config.GEN_NUM_PREDICT >= 2048, "…but large enough not to truncate a real answer"

# -1 must remain *selectable* for anyone who wants it
from agentic import ui
p = next(x for x in ui._all_params() if x["var"] == "GEN_NUM_PREDICT")
assert p["min"] == -1, "unlimited must still be reachable in /parameters"
assert p["default"] == config.GEN_NUM_PREDICT, "schema default and config must agree"

# ── 4. the user-facing note exists in both languages ────────────────────────
for lang in ("en", "fr"):
    assert i18n.STR[lang]["repetition_stop_note"].strip(), f"missing note for {lang}"

print("repetition breaker: ALL PASS")
