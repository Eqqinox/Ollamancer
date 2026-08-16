import os, tempfile, pathlib
import agent
from agentic import commands, tools
from agentic import state, skills
state._AUDIT_LOG = pathlib.Path(tempfile.mktemp())

# 1. frontmatter parsing (dependency-free)
meta, body = skills._parse_skill_frontmatter(
    "---\nname: my-skill\ndescription: Do a thing. Use when asked.\nlicense: MIT\n---\n\n# Title\nbody here")
assert meta["name"] == "my-skill", meta
assert meta["description"] == "Do a thing. Use when asked.", meta
assert body.strip().startswith("# Title"), body
# no frontmatter → whole text is body, empty meta
m2, b2 = skills._parse_skill_frontmatter("# Just markdown\nno front")
assert m2 == {} and b2.startswith("# Just markdown")

# 2. discovery finds the shipped example skill (bundled in <repo>/skills/)
found = skills._discover_skills()
assert "commit-message" in found, list(found)
assert "commit" in found["commit-message"]["description"].lower()

# 3. a project-level skill is discovered and OVERRIDES a same-named one (specificity wins)
proj = pathlib.Path(tempfile.mkdtemp()); state.PROJECT_ROOT = proj
sk = proj / ".agentic" / "skills" / "deploy"
sk.mkdir(parents=True)
(sk / "SKILL.md").write_text("---\nname: deploy\ndescription: Deploy the app safely.\n---\n\n# Deploy\n1. run tests\n2. build\n3. push\n")
# also a project skill overriding 'commit-message'
sk2 = proj / ".agentic" / "skills" / "commit-message"
sk2.mkdir(parents=True)
(sk2 / "SKILL.md").write_text("---\nname: commit-message\ndescription: PROJECT-SPECIFIC commit rules.\n---\n\n# Custom\nuse ticket ids\n")
found = skills._discover_skills()
assert "deploy" in found
assert found["commit-message"]["description"] == "PROJECT-SPECIFIC commit rules.", "project skill should override bundled"

# 4. Tier-1 system-prompt block lists names + descriptions (cheap discovery)
block = skills._skills_prompt_block()
assert "deploy: Deploy the app safely." in block
assert "load_skill" in block   # tells the model how to activate

# 5. load_skill returns the full body + the skill's dir (Tier 2 activation)
out = skills.load_skill("deploy")
assert "run tests" in out and "build" in out
assert str(sk) in out   # points at the skill folder for reference files
# fuzzy match on a near name
assert "run tests" in skills.load_skill("deploi")   # typo tolerated

# 6. unknown skill → helpful message listing available ones (no crash)
r = skills.load_skill("nonexistent")
assert r.startswith("No skill named") and "deploy" in r

# 7. registration + read-only (usable by the architect)
assert skills.load_skill in tools.TOOLS
assert "load_skill" in tools._READ_ONLY_TOOL_NAMES

# 8. make_system_prompt includes the skills block
state._memory = ""
sp = commands.make_system_prompt(proj)
assert "Available skills" in sp and "deploy:" in sp

# 9. web-answer-format auto-loads on a web-shaped question (code-side, like the forced search)
msgs = [{"role": "user", "content": "what are the latest international news today?"}]
skills._maybe_autoload_web_format(msgs[0]["content"], msgs)
assert len(msgs) == 3, msgs
assert msgs[1]["tool_calls"][0]["function"]["name"] == "load_skill"
assert "[Skill loaded: web-answer-format]" in msgs[2]["content"]
assert "Coverage:" in msgs[2]["content"]        # the body, not just the header

# already in context → not injected a second time
skills._maybe_autoload_web_format("and the latest news on the euro?", msgs)
assert len(msgs) == 3, "should not re-inject while still in recent context"

# a coding question is not web-shaped: no injection, no wasted tokens
code = [{"role": "user", "content": "refactor this function to use a dict comprehension"}]
skills._maybe_autoload_web_format(code[0]["content"], code)
assert len(code) == 1, code
for quiet in ("fix the failing test in tests/test_b9.py", "explain what this module does",
              "write a commit message for my diff", "add type hints here"):
    assert not skills._WEB_FORMAT_INTENT_RE.search(quiet), quiet

# open questions about the world are web-shaped too, not just news: "how do I build a web
# scraper" ran zero searches and answered from memory, unsourced, because the trigger only
# covered recency wording
for asks_the_world in ("how do I build a web scraper?",
                       "what are the best GGUF models right now?",
                       "compare SearXNG and Whoogle",
                       "which library should I use for scraping?"):
    assert skills._WEB_FORMAT_INTENT_RE.search(asks_the_world), asks_the_world

# the loop reads the same marker load_skill writes, so the unsearched-answer nudge cannot
# disagree with the auto-load about what counts as a web question
from agentic import loop as _loop
assert _loop._web_format_skill_loaded(msgs)
assert not _loop._web_format_skill_loaded([{"role": "user", "content": "hello"}])

# the forced-search prefix counts as web-shaped
forced = [{"role": "user", "content": "search openai model prices"}]
skills._maybe_autoload_web_format(forced[0]["content"], forced)
assert len(forced) == 3, forced

log = state._AUDIT_LOG.read_text() if state._AUDIT_LOG.exists() else ""
assert "LOAD_SKILL" in log
print("SKILLS ALL PASS")
