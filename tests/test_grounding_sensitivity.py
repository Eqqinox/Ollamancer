"""`_grounding_check` never fired in 264 real runs. This measures whether it *would* have.

Two benchmark campaigns — 168 runs of the model ranking and 96 of the honesty A/B — produced
zero grounding-check nudges. `RESULTS.md` §2 originally read that as "the honesty layer is
doing its job", which does not follow: a check that never fires cannot be the reason nothing
was fabricated. But the opposite reading does not follow either, and it is the one that should
worry anyone — **maybe it never fires because it does not work.** Silence is the same
observation for a check that is perfectly calibrated and for one that is dead.

Three things have to be true to tell those apart, and this file measures the two that
`tests/test_a56.py` does not:

  1. **Reachable at runtime.** Covered by `test_a56` scenario B, which drives a fabricated
     number and date through the real `run_agent` and asserts both the injected nudge text and
     the `AUTO_GROUNDING_CHECK_NUDGE` audit record. Not repeated here.
  2. **Sensitive on a realistic haystack** — the hypothesis this file was written to kill.
     `_grounding_check` substring-matches against every tool result of the turn concatenated
     together. Real search turns produce ~20 KB of that (55 KB at the tail), and the worry was
     that a haystack so large matches anything by coincidence, making the check vacuous exactly
     where it matters most. Measured on the banked corpus: **false. An injected fabricated URL
     plus figure was caught in 91 of 91 real answers** (the sweep below reproduces this), and a
     random 4-digit value collides with the concatenated digit-soup only ~3% of the time
     (5 digits: 0.3%; 6+: none).
  3. **Sensitive to a *realistic* fabrication**, not just an obvious one. Appending
     `https://www.example-fabricated-outlet.com` is a straw man; the failure mode that actually
     occurs is a plausible digit change to a figure the model really did retrieve. Measured by
     perturbing one digit of a genuinely-cited number in answers first verified clean:
     **73 of 78 would have nudged (94%), 5 stayed silent.** That figure came from a one-off
     sweep on 2026-08-15, not from the sweep below, which injects rather than perturbs — the
     assertion in §3 pins the behaviour on the fixture, not the rate on the corpus.

So the layer is calibrated, not dead, and §2 can now say so with a number instead of a hope.

**What is still not verified, and is not verified here.** Every positive above is synthetic. No
model has yet been observed fabricating and being caught in the wild, so this measures the
detector, never the deterrent. Paraphrased fabrication remains uncovered by construction (the
bare `owner/repo` blind spot pinned in `test_grounding_recheck`), and the ~6% that slip silently
are unanalysed.

The corpus sweep at the bottom only runs when `benchmarks/model_ranking/results/` is present.
It is gitignored — the run directories hold third-party article text — so CI and a fresh clone
run the self-contained half, which is built to mirror the real corpus's shape rather than to
reproduce its content.

    PYTHONPATH="$PWD" python tests/test_grounding_sensitivity.py
"""

import json
import random
import re
from pathlib import Path

from agentic import loop

SEED = 11
HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "benchmarks" / "model_ranking" / "results"


# Measured off the banked corpus, and both numbers matter. Size is the volume the matcher has
# to survive; density is what makes the digit-soup argument valid or vacuous. An early draft of
# this fixture was almost entirely numbers and showed a 17.8% four-digit collision rate against
# the real corpus's 2.8% — it would have "proved" the matcher was vacuous by testing a haystack
# no search turn produces. Prose padding is not filler here, it is the control.
_REAL_HAYSTACK_BYTES = 20_000     # median of tool_results.json across the 105 banked t2/t4
                                  # runs (19.8 KB; 55 KB at the tail). An earlier constant of
                                  # 10,300 came from a stricter filter over one of the two
                                  # result trees, and was half the real median — which made
                                  # this test EASIER than reality, since a smaller haystack
                                  # produces fewer coincidental matches. Erring small here is
                                  # erring in the direction that flatters the check.
_REAL_DIGIT_DENSITY = 0.028       # median digits per byte, same corpus

_PROSE = (
    "Officials said the situation remained under review and that further guidance would follow "
    "in the coming weeks. Analysts cautioned against drawing conclusions before the full report "
    "is published, noting that earlier estimates had been revised more than once. A spokesperson "
    "declined to comment on the specifics but confirmed the review is ongoing. Local reporting "
    "suggested the effects were uneven across the region, with some areas largely unaffected. ")


def _synthetic_haystack(rng, target_bytes=_REAL_HAYSTACK_BYTES):
    """Tool results shaped like a real search turn, matched to the corpus on *both* axes.

    Content is generated rather than copied: the run directories are gitignored precisely
    because their article text is not ours to republish, so a test that needed them could not
    run in CI. What is reproduced is the shape — size, digit density, and the mix of URLs,
    ISO dates and figures embedded in prose.
    """
    out, i = [], 0
    while sum(len(x) for x in out) < target_bytes:
        i += 1
        out.append(
            f"Title: Regional developments, part {rng.randrange(2, 40)}\n"
            f"URL: https://www.outlet{i % 17}.example/news/{rng.randrange(100000, 999999)}\n"
            f"Published: 2026-0{rng.randrange(1, 9)}-{rng.randrange(10, 28)}\n"
            f"Content: officials reported {rng.randrange(1000, 99999)} cases. "
            + _PROSE * rng.randrange(2, 4) + "\n---\n")
    return out


rng = random.Random(SEED)
HAY = _synthetic_haystack(rng)
HAY_BYTES = sum(len(x) for x in HAY)
HAY_DENSITY = len(re.sub(r"\D", "", "".join(HAY))) / HAY_BYTES
assert 18000 < HAY_BYTES < 45000, (
    f"haystack should be at least the real corpus median (~20 KB), got {HAY_BYTES}. "
    "Undersizing it makes the volume test easier than reality.")
assert abs(HAY_DENSITY - _REAL_DIGIT_DENSITY) < 0.015, (
    f"digit density {HAY_DENSITY:.3f} vs the corpus's {_REAL_DIGIT_DENSITY:.3f} — the fixture "
    "must not be denser in numbers than real search output, or §4 below measures nothing")

# ── 1. Specificity: an answer built only from the haystack must not be flagged ──────
# A check that fires on grounded answers is worse than one that never fires, per DESIGN.md
# §4.2: a silent miss costs nothing, a false alarm teaches the user to ignore the warnings.
m = re.search(r"URL: (\S+)\nPublished: (\S+)\nContent: officials reported (\d+) cases", "".join(HAY))
real_url, real_date, real_num = m.group(1), m.group(2), m.group(3)
grounded = (f"According to [{real_url}], published {real_date}, officials reported "
            f"{real_num} cases.")
assert loop._grounding_check(grounded, HAY) == [], \
    "an answer whose every hard token came from the tool results must not be flagged"

# ── 2. Sensitivity: an invented URL and figure are caught despite the volume ────────
# The hypothesis this file exists to kill — that 20 KB of haystack makes the check vacuous.
fabricated = grounded + (" A separate analysis at "
                         "https://www.entirely-invented-outlet.example/story/9182736 "
                         "put the figure at 87,412,339.")
flags = loop._grounding_check(fabricated, HAY)
assert any("entirely-invented-outlet" in f for f in flags), \
    f"a fabricated URL must be caught in a {HAY_BYTES}-byte haystack, got {flags}"
assert any(re.sub(r"\D", "", f) == "87412339" for f in flags), \
    f"a fabricated figure must be caught in a {HAY_BYTES}-byte haystack, got {flags}"

# ── 3. The realistic fabrication: one digit of a genuinely-cited figure ─────────────
# Not a straw man like the above. This is what actually happens — the model retrieves a real
# number and reports it slightly wrong.
perturbed = real_num[:-1] + str((int(real_num[-1]) + 5) % 10)
if perturbed != real_num and perturbed not in "".join(HAY):
    assert loop._grounding_check(grounded.replace(real_num, perturbed), HAY), \
        "a one-digit change to a cited figure must not pass silently"

# ── 4. Why it works: the digit-soup is sparse, not dense ───────────────────────────
# Numbers are matched on their digit sequence with separators stripped, against every digit in
# every tool result concatenated. The fear was that this soup contains everything. It does not,
# and the measurement is what licenses the claim rather than the intuition.
soup = re.sub(r"\D", "", "".join(HAY))
collide = {}
for length in (4, 5, 6):
    hits = sum(1 for _ in range(400)
               if "".join(rng.choice("0123456789") for _ in range(length)) in soup)
    collide[length] = hits / 400
assert collide[4] < 0.15, f"4-digit collision rate {collide[4]:.1%} — matcher may be vacuous"
assert collide[6] < 0.02, f"6-digit collision rate {collide[6]:.1%} — matcher may be vacuous"

# ── 5. The corpus sweep, when the banked runs are present ──────────────────────────
# Gitignored, so this is skipped in CI and on a fresh clone. When it does run it reproduces the
# numbers quoted in RESULTS.md §2 and in this file's docstring, so those cannot silently drift.
if CORPUS.is_dir():
    caught = total = 0
    runs = list(CORPUS.glob("*/t[24]_rep*/meta.json"))
    runs += list(CORPUS.with_name("results_ab").glob("*/t[24]_*/meta.json"))
    for meta in runs:
        d = meta.parent
        ans, res = d / "answer.txt", d / "tool_results.json"
        if not (ans.exists() and res.exists()):
            continue
        # answer.txt is the run's whole stdout, not just msg.content — it carries the agent's
        # own warnings and echoed tool JSON, which are not what the runtime check sees. Only
        # answers this check already calls clean are usable as a baseline.
        text = ans.read_text(errors="ignore").strip()
        if text.startswith("ERROR") or len(text) < 200:
            continue
        try:
            results = [str(x) for x in json.loads(res.read_text())]
        except Exception:                                          # noqa: BLE001
            continue
        if loop._grounding_check(text, results):
            continue
        mutated = text + ("\n\nPer https://www.entirely-invented-outlet.example/x/9182736 "
                          "the figure was 87,412,339.")
        hit = loop._grounding_check(mutated, results)
        total += 1
        caught += bool(any("entirely-invented-outlet" in h for h in hit))
    if total:
        rate = caught / total
        print(f"corpus sweep: {caught}/{total} injected fabrications caught ({rate:.0%})")
        assert rate > 0.95, \
            f"sensitivity on the real corpus fell to {rate:.0%}; the matcher regressed"
else:
    print("corpus sweep: skipped (benchmarks/model_ranking/results/ is gitignored)")

print("test_grounding_sensitivity: all assertions passed")
