"""The architect phase must not demand impossible actions, nor pass invented sources on.

Both guard one real /architect run: three nudges fired before a plan even existed, and the
plan then cited three mangled variants of a single AP article the architect had never fetched
(a transposed hex character, a truncated one, and "https/" with no colon). The editor treated
the plan as approved and copied those URLs into the output file as sources.
"""
import agent  # noqa: F401
from agentic import commands, i18n, loop

# ── 1. the claim-vs-action nudge is unsatisfiable in a read-only phase ───────
# The detector itself still works normally...
assert loop._claim_without_action("I fixed the bug.", False, False) is not None
assert loop._claim_without_action("I fixed the bug.", True, True) is None
# ...but run_agent must suppress it when writes are refused. The architect is *forbidden* to
# edit, so had_edit can never become True and the nudge could never be satisfied.
import inspect
src = inspect.getsource(loop.run_agent)
assert "if allowed_tools is not None:" in src and "claim_kind = None" in src, (
    "run_agent must suppress the claim-vs-action nudge when allowed_tools restricts writes")

# ── 2. invented citations in a plan are detected ────────────────────────────
real = "https://apnews.com/article/mideast-news-roundup-iran-lebanon-israel-aug-6-2026-07074f3374339a34bc539f56d7d6287a"
results = [f"[Published: 2026-08-06]\nIran says it is in the final stage...\nSource: {real}"]

plan_ok = f"1. Middle East: two soldiers killed [Source: {real}]"
assert commands._unseen_urls(plan_ok, results) == [], "a genuinely fetched URL must not be flagged"

# the three real corruptions from the incident
plan_bad = (
    f"- claim A [Source: {real.replace('lebanon', 'leban')}]\n"
    f"- claim B [Source: {real.replace('a34bc539', 'a34cc539')}]\n"
    f"- claim C [Source: https/www.cnn.com/2026/08/06/world/live-news/iran-war-trump]\n")
unseen = commands._unseen_urls(plan_bad, results)
assert len(unseen) == 3, unseen
assert any("leban-israel" in u for u in unseen), unseen
assert any(u.startswith("https/www.cnn.com") for u in unseen), "must catch the missing colon"

# de-duplicated, and trailing punctuation stripped
dupe = f"see {real.replace('lebanon','leban')}, and again {real.replace('lebanon','leban')}."
assert len(commands._unseen_urls(dupe, results)) == 1

# no tool results at all: everything cited is unverified by definition
assert len(commands._unseen_urls(plan_ok, [])) == 1
# no URLs at all is fine
assert commands._unseen_urls("1. Read config.py\n2. Add a flag", results) == []

# ── 3. the warnings exist in both languages ─────────────────────────────────
for lang in ("en", "fr"):
    for key in ("architect_unseen_urls", "architect_unseen_urls_editor"):
        assert i18n.STR[lang][key].strip(), f"missing {key} for {lang}"
assert "{n}" in i18n.STR["en"]["architect_unseen_urls"]
assert "{urls}" in i18n.STR["en"]["architect_unseen_urls_editor"]

print("architect guards: ALL PASS")
