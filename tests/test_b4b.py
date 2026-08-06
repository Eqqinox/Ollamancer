import os, tempfile, pathlib
import agent
agent.STREAM_FINAL = "off"
agent.MAX_VERIFY_NUDGES = 0
agent.get_num_ctx = lambda m: 4096
agent.ollama_runner_rss_gb = lambda: None

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); agent.PROJECT_ROOT = d.resolve()
agent._AUDIT_LOG = d / "audit.log"
agent._CHECKPOINT_GITDIR = None
agent._unload_model = lambda m: None
agent.ARCHITECT_MODEL = "arch:m"; agent.EDITOR_MODEL = "ed:m"

class F:
    def __init__(s,n,a): s.name=n; s.arguments=a
class TC:
    def __init__(s,n,a): s.function=F(n,a)
class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content=content; s.tool_calls=tool_calls; s.thinking=thinking
class Resp:
    def __init__(s,m): s.message=m

# Architect stubbornly tries write_file 3x (all refused), then — after the read-only nudge —
# finally writes a text plan. Editor then executes it for real.
scripts = {
    "arch:m": iter([
        Msg(tool_calls=[TC("write_file", {"path": "x.py", "content": "1"})]),   # refused (1)
        Msg(tool_calls=[TC("edit_file", {"path": "x.py"})]),                      # refused (2)
        Msg(tool_calls=[TC("run_command", {"command": "echo hi > x.py"})]),       # refused (3) -> nudge
        Msg(content="PLAN:\n1. create result.txt containing DONE", tool_calls=None),  # text plan after nudge
    ]),
    "ed:m": iter([
        Msg(tool_calls=[TC("write_file", {"path": "result.txt", "content": "DONE"})]),
        Msg(content="executed", tool_calls=None),
    ]),
}
agent.ollama.chat = lambda **kw: Resp(next(scripts[kw["model"]]))

msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "prior"}]
plan, result = agent.cmd_architect("build the thing", msgs, "cur:m")

assert plan.strip() == "PLAN:\n1. create result.txt containing DONE", repr(plan)
assert result == "executed", result
# architect never wrote a file despite 3 tries
assert not (d / "x.py").exists(), "read-only gate breached"
# editor did the real write
assert (d / "result.txt").read_text() == "DONE"

log = agent._AUDIT_LOG.read_text()
assert "READONLY_PLAN_NUDGE" in log, "read-only plan nudge did not fire"
assert log.count("architect read-only") == 3, log  # exactly 3 refusals

# nudge injected into the architect's message stream (verify the text is there via the tool call count)
print("B4b (architect read-only plan nudge) ALL PASS")
