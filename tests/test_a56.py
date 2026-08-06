import os, tempfile, pathlib
import agent
from agentic.tools import rag
from agentic import models
from agentic import config, state
config.STREAM_FINAL = "off"  # these predate streaming; use buffered path

# ---------- Unit: _extract_hard_tokens / _grounding_check ----------
results = ["City report: the metro area has 8,340,000 residents. Published 2021-03-05. See http://ex.com/data"]
# supported answer: number reformatted, url and date present
ok = agent._grounding_check("Population is 8340000 (as of 2021-03-05) per http://ex.com/data.", results)
assert ok == [], ok

# fabricated: none present in the (empty-ish) results
bad = agent._grounding_check(
    "The population is 9,999,999 as of 1999-12-31, source http://fake.example/none.",
    ["A generic status message with no figures."])
assert "9,999,999" in bad or "9999999" in " ".join(bad), bad
assert "1999-12-31" in bad, bad
assert any("fake.example" in b for b in bad), bad

# quoted proper noun not in results
q = agent._grounding_check('The report is titled "Operation Blue Falcon".', ["nothing relevant here"])
assert any("Operation Blue Falcon" in b for b in q), q

# no hard tokens → nothing
assert agent._grounding_check("It went well, thanks.", ["whatever"]) == []

# ---------- Unit: _claim_without_action ----------
assert agent._claim_without_action("I fixed the bug.", had_edit=False, had_verification=False) == "fix"
assert agent._claim_without_action("I fixed the bug.", had_edit=True, had_verification=False) is None
assert agent._claim_without_action("Verified it works as expected.", had_edit=True, had_verification=False) in ("verification", "both")
assert agent._claim_without_action("Done, I corrigé le bug et vérifié.", had_edit=False, had_verification=False) == "both"
assert agent._claim_without_action("Here is the summary.", had_edit=False, had_verification=False) is None
assert agent._claim_without_action("I fixed it.", had_edit=True, had_verification=True) is None

# ---------- Integration: monkeypatched run_agent ----------
d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None
state._AUDIT_LOG = d / "audit.log"

class F:
    def __init__(s, n, a): s.name = n; s.arguments = a
class TC:
    def __init__(s, n, a): s.function = F(n, a)
class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content = content; s.tool_calls = tool_calls; s.thinking = thinking
class Resp:
    def __init__(s, m): s.message = m

def make_chat(script):
    it = iter(script)
    def fake_chat(**kw): return Resp(next(it))
    return fake_chat

# Scenario A: claim "fixed" with no edit → fix nudge fires
script_a = [
    Msg(tool_calls=[TC("todo_write", {"checklist": "- [ ] look at bug"})]),  # non-edit tool
    Msg(content="I fixed the bug.", tool_calls=None),                          # unbacked fix claim
    Msg(content="Sorry, it is not actually fixed yet — I only inspected it.", tool_calls=None),
]
rag.ollama.chat = make_chat(script_a)
msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "fix it"}]
final = agent.run_agent(msgs, "fake-model")
assert "not actually fixed" in final, final
assert any(m["role"] == "user" and "no successful file write" in m["content"] for m in msgs), \
    "claim_action fix nudge not injected"

# Scenario B: fabricated number/date in final answer → grounding_check nudge fires
script_b = [
    Msg(tool_calls=[TC("todo_write", {"checklist": "- [ ] research"})]),
    Msg(content="The population is 8,340,000 as of 2021-03-05.", tool_calls=None),
    Msg(content="I could not confirm those figures from any source.", tool_calls=None),
]
rag.ollama.chat = make_chat(script_b)
msgs2 = [{"role": "system", "content": "sys"}, {"role": "user", "content": "population?"}]
final2 = agent.run_agent(msgs2, "fake-model")
assert "could not confirm" in final2, final2
assert any(m["role"] == "user" and "appear in none of this turn" in m["content"] for m in msgs2), \
    "grounding_check nudge not injected"

# Scenario C: honest, backed answer → NO extra nudges (returns first final)
script_c = [
    Msg(tool_calls=[TC("todo_write", {"checklist": "- [x] done"})]),
    Msg(content="Here is a plain summary with no claims or hard tokens.", tool_calls=None),
]
rag.ollama.chat = make_chat(script_c)
msgs3 = [{"role": "system", "content": "sys"}, {"role": "user", "content": "summarize"}]
final3 = agent.run_agent(msgs3, "fake-model")
assert final3 == "Here is a plain summary with no claims or hard tokens.", final3

log = state._AUDIT_LOG.read_text()
assert "AUTO_CLAIM_ACTION_NUDGE" in log and "AUTO_GROUNDING_CHECK_NUDGE" in log, log

print("A5+A6 ALL PASS")
