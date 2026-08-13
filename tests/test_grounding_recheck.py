"""The correction produced by a grounding nudge must itself be checked.

`MAX_GROUNDING_CHECK_NUDGES = 1`, so the check ran on the answer and never on the repair. A
fabrication introduced *in response to* the nudge reached the user unexamined — and with the
model's confidence raised, not lowered, because it believed it had just verified itself.

Observed live, asking for the most-starred GitHub repositories: the model cited a URL for
`ethereum/build-your-own-x`, the check flagged it (a URL in no tool result), and the model
"corrected" it to `jvns/build-your-own-x, a tutorial list by Julia Evans` — equally invented —
then signed off with "all other values are accurate and sourced from that page". The true
owner, `codecrafters-io`, was in the very table it had fetched. Every star count was exact to
the digit; only the name was improvised, twice.

The re-check runs once on the correction and **warns** rather than nudging again. A second
nudge is what stacks up and talks a small model into an empty answer — four nudges in one turn
did exactly that on qwen-heretic. A warning costs the model nothing and tells the reader which
values to distrust.

**Known blind spot, pinned below rather than assumed away.** `_grounding_check` extracts four
token classes — URL, date, number, quote — so a bare `owner/repo` slug written in prose is
invisible to it, including the exact `jvns/build-your-own-x` above. The re-check would have
caught that answer's *first* form (a URL) but not its second. Widening the extractor to catch
bare slugs was considered and rejected: in a coding agent `agentic/loop.py` and
`tests/README.md` have the same shape, and the docstring commits to being "conservative by
design (fewer false alarms)". The gap is real and documented, not fixed.

Offline: `_grounding_check` is the real function, fed synthetic tool results.

    PYTHONPATH="$PWD" python tests/test_grounding_recheck.py
"""

from pathlib import Path

from agentic import config, i18n, loop

# What the tool actually returned, with the true owner in it.
TOOL_RESULTS = [
    "codecrafters-io/build-your-own-x 539183 stars "
    "https://github.com/codecrafters-io/build-your-own-x\n"
    "sindresorhus/awesome 495052 stars\n"
]

# ── 1. A fabricated URL in the correction is caught ─────────────────────────
# This is the shape the re-check exists for: the first answer was flagged on exactly this
# basis, and nothing was watching when the model produced a second one.
bad_url = "Good catch — the real repo is https://github.com/jvns/build-your-own-x, 539183 stars."
flagged = loop._grounding_check(bad_url, TOOL_RESULTS)
assert any("jvns" in f for f in flagged), f"a fabricated URL in a correction must be flagged, got {flagged}"

# ── 2. A fabricated figure in the correction is caught ──────────────────────
bad_number = "Corrected: it has 612000 stars."
assert "612000" in loop._grounding_check(bad_number, TOOL_RESULTS), \
    "an invented figure in a correction must be flagged"

# ── 3. A genuine correction stays silent ────────────────────────────────────
# If the warning fires on good corrections it becomes noise, and a warning that is always
# on is a warning nobody reads.
honest = "Corrected: it is codecrafters-io/build-your-own-x with 539183 stars."
assert not loop._grounding_check(honest, TOOL_RESULTS), \
    "a correction matching the tool results must not warn"

# ── 4. Correct figures are never flagged ────────────────────────────────────
# Every number in the real answer was right. Grounding checks provenance, not truth, and
# it must not cry wolf about values that are genuinely present.
assert not loop._grounding_check("539183 and 495052 stars.", TOOL_RESULTS), \
    "figures present in the tool results must not be flagged"

# ── 5. The documented blind spot, pinned so nobody assumes coverage ─────────
# If someone later teaches _extract_hard_tokens about bare slugs, this fails loudly and
# the docstring above should be revisited — that is the intent, not an oversight.
bare_slug = "The real repo is jvns/build-your-own-x, a tutorial list by Julia Evans."
assert loop._grounding_check(bare_slug, TOOL_RESULTS) == [], (
    "a bare owner/repo slug is NOT detectable by design — if this now flags, the extractor "
    "gained a token class and the trade-off in this file's docstring needs rewriting")
assert set(loop._extract_hard_tokens("x")) == {"URL", "date", "number", "quote"}, \
    "token classes changed; re-read what the re-check can and cannot see"

# ── 6. It is capped, and warns instead of nudging again ─────────────────────
body = Path(loop.__file__).read_text()
body = body[body.index("def run_agent"):]
assert "grounding_recheck_done = True" in body, "the re-check must mark itself done"
start = body.index("elif turn_tool_results and grounding_check_nudges_used")
block = body[start:start + 1800]
block = block[:block.index("# Same event reported twice")]
assert "_nudge(" not in block, "must warn, not nudge — a second nudge is what empties small models"
assert "continue" not in block, "must not re-enter the loop"
assert "grounding_recheck_warning" in block, "must surface a warning to the user"

# ── 7. The warning exists in both languages and names the values ────────────
for lang in ("en", "fr"):
    assert "{values}" in i18n.STR[lang]["grounding_recheck_warning"], \
        f"{lang}: the warning must list which values are unverified"

assert config.MAX_GROUNDING_CHECK_NUDGES == 1, \
    "if the nudge cap changes, revisit whether a single re-check is still the right shape"

print("test_grounding_recheck: all assertions passed")
