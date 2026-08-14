"""The "you claim to have verified" nudge must not fire on a research turn.

`had_verification` only becomes True when a tool from `_VERIFY_TOOLS` runs — lint_file,
run_tests, run_command. On a turn made of search and read calls none of those can run, because
there is nothing to execute, so the flag is structurally False. Any answer containing
"verified" or "confirmed that" therefore triggered the nudge, and the nudge told the model it
had claimed to run tests that it never ran.

Observed live on gemma-4-26B-A4B-it-uncensored-heretic, on a search_web / search_web_deep
turn. The model did exactly as instructed and answered the nudge instead of the user:

    I have not run any automated verification tools (such as run_tests or lint_file) during
    this turn to verify the accuracy of my answer. The "verification" I referred to was a
    manual comparison of my generated response against the text contained in the search
    results...

Which was true, cooperative, and worthless — the research answer it replaced was gone. The
model had not lied; the check had. "Verified" against sources is the correct use of the word
on a search turn, and `_grounding_check` already audits provenance there, more precisely,
naming the individual unsupported values rather than demanding a wholesale recant.

The literature says a nudge on a false premise is worse than no nudge. Correct-to-incorrect
flips outrank the reverse under self-correction, and a prompt that asserts the error up front
("You state this was verified, but...") drives the flip rather than prompting a check —
"prompt bias", in Understanding the Dark Side of LLMs' Intrinsic Self-Correction (ACL 2025).
Every other nudge here keeps its premise true; this one had stopped.

**Why the gate is not simply `had_edit`.** That was the first shape considered and it loses
the worst case of the three: a turn with no tool calls at all that says "I tested it, it
works". Nothing happened there, so the premise is true and the nudge belongs. The gate is
research-*only* — research tools ran and nothing was edited — which keeps that case and the
edit-without-verifying case, and stands down on exactly one shape.

Offline: `_claim_without_action` is the real function, called with the flags the loop keeps.

    PYTHONPATH="$PWD" python tests/test_claim_action_research.py
"""

from pathlib import Path

from agentic import loop

VERIFIED = "I verified this against the sources; confirmed that the figure is right."
FIXED_AND_VERIFIED = "Fixed the bug, and I tested it — it works now."

# ── 1. The reported case: research turn, no edit, claims verification ───────
assert loop._claim_without_action(VERIFIED, had_edit=False, had_verification=False,
                                  had_research=True) is None, \
    "a search/read turn saying 'verified' must not be nudged — that is what it means there"

# ── 2. No tools at all: the premise is true, the nudge stays ────────────────
# The most brazen of the three shapes, and the one a bare `had_edit` gate would have lost.
# Nothing ran, nothing was read, and the model claims a test.
assert loop._claim_without_action("I tested it and it works.", had_edit=False,
                                  had_verification=False, had_research=False) == "verification", \
    "a claim of testing on a turn with no tool calls at all must still be nudged"

# ── 3. Edited but never verified: unchanged ────────────────────────────────
# The case the check was written for. Research may well have run alongside the edit; what
# matters is that a file changed and nothing was executed against it.
assert loop._claim_without_action(VERIFIED, had_edit=True, had_verification=False,
                                  had_research=True) == "verification", \
    "an edit turn claiming verification must be nudged even if it also searched"

# ── 4. The fix half is untouched by the research gate ──────────────────────
# A model claiming a fix on a turn that only read files has still fixed nothing, and
# `had_research` must not buy it an exemption.
assert loop._claim_without_action("Fixed — it works now.", had_edit=False,
                                  had_verification=False, had_research=True) == "fix", \
    "a fix claimed with no edit is unbacked whether or not the turn did research"
assert loop._claim_without_action(FIXED_AND_VERIFIED, had_edit=False,
                                  had_verification=False, had_research=False) == "both", \
    "the both-branch still reports both when neither happened"

# ── 5. Real verification silences it, as before ────────────────────────────
assert loop._claim_without_action(VERIFIED, had_edit=True, had_verification=True,
                                  had_research=True) is None, \
    "a turn that actually ran a verification tool is never nudged"
assert loop._claim_without_action("Nothing to report.", had_edit=False,
                                  had_verification=False, had_research=True) is None, \
    "an answer claiming neither a fix nor a verification is never nudged"

# ── 6. The flag is set from the tool name, next to the two it joins ────────
body = Path(loop.__file__).read_text()
assert "search_web" in loop._RESEARCH_TOOLS and "read_file" in loop._RESEARCH_TOOLS, \
    "the tools that produced the live failure must be in the set"
assert not (loop._RESEARCH_TOOLS & loop._VERIFY_TOOLS), \
    "a tool cannot be both evidence to read and a program to run"
assert not (loop._RESEARCH_TOOLS & loop._EDIT_TOOLS), \
    "research tools must not overlap the edit set"
assert "had_research = True" in body, "the loop must actually set the flag"
assert "had_verification, had_research)" in body, "the call site must pass it"

# ── 7. It narrows the check and never widens it ────────────────────────────
# Whatever the flags, `had_research` can only remove claims from the verdict, never add one.
# That is the whole argument for the change — it subtracts a firing condition, so it cannot
# cost anyone an answer it would otherwise have got. If a future edit lets it turn a nudge
# *on*, this fails. Note "both" narrowing to "fix" is expected: the fix half is unaffected.
KINDS = {None: set(), "fix": {"fix"}, "verification": {"verification"},
         "both": {"fix", "verification"}}
for answer in (VERIFIED, FIXED_AND_VERIFIED, "Fixed.", "confirmed it", "plain text"):
    for edit in (True, False):
        for verif in (True, False):
            without = loop._claim_without_action(answer, edit, verif, False)
            with_res = loop._claim_without_action(answer, edit, verif, True)
            assert KINDS[with_res] <= KINDS[without], \
                f"had_research turned {without!r} into {with_res!r} — it must only ever silence"

print("test_claim_action_research: all assertions passed")
