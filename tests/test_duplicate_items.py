"""Two list items describing the same event must be questioned.

Every other check compares the answer to its SOURCES. This one compares the answer to
ITSELF. Observed from gpt-oss:20b: item 1 said "seven people were killed" at Debsirin
Nonthaburi School and item 5 said "nine people were killed, including the shooter" at the
same school — one event, two death tolls, presented as unrelated news. Both passed
_grounding_check, because both figures genuinely appeared in tool results (BBC and a
Wikipedia portal).

The corpus below is real output from a cross-model comparison run, not invented examples.
"""
import agent  # noqa: F401
from agentic import i18n, loop

REAL_DUPLICATE = """
 1  Seven people were killed after a Thai student opened fire at his home and Debsirin
    Nonthaburi School - the 14-year-old also killed his grandparents.
 2  Indian shipping minister Sarbananda Sonowal reported that 62 Indian vessels transited
    the Strait of Hormuz during the Iran war.
 5  Nine people were killed, including the shooter, and 15 others injured during a shooting
    spree between a home and Debsirin Nonthaburi School.
"""
hit = loop._duplicate_items(REAL_DUPLICATE)
assert hit is not None, "must catch the same school in two items"
a, b, ent = hit
assert (a, b) == (1, 3), (a, b)                 # 3rd parsed item (labelled 5 in the original)
assert ent == "Debsirin Nonthaburi School", ent

# ── must stay quiet on real, clean answers ──────────────────────────────────
CLEAN = {
"shared single-word entity across items (Hormuz twice) is NOT a duplicate": """
- Strait of Hormuz Deal: Iran and Oman are in the final stages of an agreement to
  facilitate commercial shipping through the strait.
- Saudi Arabia & Houthi Threats: Saudi forces are on alert for coordinated attacks by
  Iraqi militias working alongside Yemen's rebels.
- Ebola Outbreak: the health agency urges a vaccine trial as cases exceed 4,000.
""",
"distinct stories, distinct entities": """
- French Streamer's Death: two people convicted over the death of Raphael Graven.
- India's Pedestrians: the top court spotlights unsafe footpaths.
- Russia-Ukraine Conflict: Moscow drops a record number of glide bombs.
""",
"markets roundup": """
1. Global growth could crash to 1.3% according to the World Bank chief economist.
2. Only 33 vessels passed through Hormuz Monday to Thursday, versus 50 a week earlier.
3. Ukraine's bond restructuring has collapsed after formal talks.
""",
"mixed topics, repeated source name only": """
- Reuters: Carlos Moya denies he will coach Jannik Sinner.
- Reuters: Canada to remove many retaliatory tariffs on US, Carney says.
- Reuters: ByteDance signs a deal over TikTok.
""",
}
for label, text in CLEAN.items():
    assert loop._duplicate_items(text) is None, f"false positive: {label}\n{loop._duplicate_items(text)}"

# ── shape and edge cases ────────────────────────────────────────────────────
assert loop._duplicate_items("") is None
assert loop._duplicate_items("A single paragraph with no list items at all.") is None
assert loop._duplicate_items("- one item only mentioning Debsirin Nonthaburi School") is None
# a URL shared between items must NOT trigger it: live blogs source many stories
SHARED_URL = """
- Saudi Arabia on alert [Source: https://www.cnn.com/2026/08/06/world/live-news/iran-war-trump].
- Israel-Lebanon talks in Rome [Source: https://www.cnn.com/2026/08/06/world/live-news/iran-war-trump].
"""
assert loop._duplicate_items(SHARED_URL) is None, "a shared live-blog URL is not a duplicate"

# ── the strings exist in both languages and format cleanly ──────────────────
for lang in ("en", "fr"):
    for key in ("auto_duplicate_note", "duplicate_nudge"):
        s = i18n.STR[lang][key]
        assert s.strip(), f"missing {key} for {lang}"
        s.format(a=1, b=5, entity="X")          # must not raise

print("duplicate items: ALL PASS")
