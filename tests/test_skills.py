import os, tempfile, pathlib
import agent
from agentic import state
state._AUDIT_LOG = pathlib.Path(tempfile.mktemp())

# 1. frontmatter parsing (dependency-free)
meta, body = agent._parse_skill_frontmatter(
    "---\nname: my-skill\ndescription: Do a thing. Use when asked.\nlicense: MIT\n---\n\n# Title\nbody here")
assert meta["name"] == "my-skill", meta
assert meta["description"] == "Do a thing. Use when asked.", meta
assert body.strip().startswith("# Title"), body
# no frontmatter → whole text is body, empty meta
m2, b2 = agent._parse_skill_frontmatter("# Just markdown\nno front")
assert m2 == {} and b2.startswith("# Just markdown")

# 2. discovery finds the shipped example skill (bundled in <repo>/skills/)
skills = agent._discover_skills()
assert "commit-message" in skills, list(skills)
assert "commit" in skills["commit-message"]["description"].lower()

# 3. a project-level skill is discovered and OVERRIDES a same-named one (specificity wins)
proj = pathlib.Path(tempfile.mkdtemp()); state.PROJECT_ROOT = proj
sk = proj / ".agentic" / "skills" / "deploy"
sk.mkdir(parents=True)
(sk / "SKILL.md").write_text("---\nname: deploy\ndescription: Deploy the app safely.\n---\n\n# Deploy\n1. run tests\n2. build\n3. push\n")
# also a project skill overriding 'commit-message'
sk2 = proj / ".agentic" / "skills" / "commit-message"
sk2.mkdir(parents=True)
(sk2 / "SKILL.md").write_text("---\nname: commit-message\ndescription: PROJECT-SPECIFIC commit rules.\n---\n\n# Custom\nuse ticket ids\n")
skills = agent._discover_skills()
assert "deploy" in skills
assert skills["commit-message"]["description"] == "PROJECT-SPECIFIC commit rules.", "project skill should override bundled"

# 4. Tier-1 system-prompt block lists names + descriptions (cheap discovery)
block = agent._skills_prompt_block()
assert "deploy: Deploy the app safely." in block
assert "load_skill" in block   # tells the model how to activate

# 5. load_skill returns the full body + the skill's dir (Tier 2 activation)
out = agent.load_skill("deploy")
assert "run tests" in out and "build" in out
assert str(sk) in out   # points at the skill folder for reference files
# fuzzy match on a near name
assert "run tests" in agent.load_skill("deploi")   # typo tolerated

# 6. unknown skill → helpful message listing available ones (no crash)
r = agent.load_skill("nonexistent")
assert r.startswith("No skill named") and "deploy" in r

# 7. registration + read-only (usable by the architect)
assert agent.load_skill in agent.TOOLS
assert "load_skill" in agent._READ_ONLY_TOOL_NAMES

# 8. make_system_prompt includes the skills block
state._memory = ""
sp = agent.make_system_prompt(proj)
assert "Available skills" in sp and "deploy:" in sp

log = state._AUDIT_LOG.read_text() if state._AUDIT_LOG.exists() else ""
assert "LOAD_SKILL" in log
print("SKILLS ALL PASS")
