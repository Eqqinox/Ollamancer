import os, tempfile, pathlib
import agent
from agentic import config
config.STREAM_FINAL = "off"  # these predate streaming; use buffered path

assert agent._git_available(), "git binary required for this test"

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d)
agent.PROJECT_ROOT = d.resolve()
(d / ".agentic").mkdir()
agent._AUDIT_LOG = d / ".agentic" / "audit.log"
agent._CHECKPOINTS = []
agent._checkpoint_turn = 0
agent._checkpoint_made_this_turn = False

agent._init_checkpoints()
assert agent._checkpoints_available(), "checkpoints should be available with git"

# initial project state
(d / "a.txt").write_text("v1")
(d / "keep.txt").write_text("keep")
# excluded heavy dirs that must survive an undo
(d / ".venv").mkdir(); (d / ".venv" / "junk").write_text("x")
(d / "node_modules").mkdir(); (d / "node_modules" / "lib.js").write_text("y")

# ---- Turn 1: checkpoint BEFORE first write, then writes happen ----
agent._checkpoint_turn = 1
agent._checkpoint_made_this_turn = False
agent._make_turn_checkpoint("turn 1: before write_file")
# guard: a second call same turn is a no-op
agent._make_turn_checkpoint("turn 1: before edit_file")
assert len(agent._CHECKPOINTS) == 1, agent._CHECKPOINTS

# the turn's writes: modify a.txt, create b.txt
(d / "a.txt").write_text("v2-MODIFIED")
(d / "b.txt").write_text("brand new file")

lst = agent.cmd_undo_list()
assert "turn 1: before write_file" in lst, lst

# ---- Undo last ----
msg = agent.cmd_undo_restore("last")
assert "Restored the project" in msg, msg
assert (d / "a.txt").read_text() == "v1", "a.txt not reverted"
assert not (d / "b.txt").exists(), "b.txt (created this turn) should be removed"
assert (d / "keep.txt").read_text() == "keep"
# excluded dirs untouched
assert (d / ".venv" / "junk").exists(), ".venv wrongly cleaned"
assert (d / "node_modules" / "lib.js").exists(), "node_modules wrongly cleaned"
# checkpoint consumed
assert agent._CHECKPOINTS == [], agent._CHECKPOINTS

# ---- Multi-turn step-back: two checkpoints, /undo <n> ----
agent._CHECKPOINTS = []
(d / "a.txt").write_text("A")
agent._checkpoint_turn = 2; agent._checkpoint_made_this_turn = False
agent._make_turn_checkpoint("turn 2")
(d / "a.txt").write_text("B")
agent._checkpoint_turn = 3; agent._checkpoint_made_this_turn = False
agent._make_turn_checkpoint("turn 3")
(d / "a.txt").write_text("C")
assert len(agent._CHECKPOINTS) == 2
# /undo 2 = the older one (display index 2 = turn 2 checkpoint) → a.txt back to "A"
r = agent.cmd_undo_restore("2")
assert (d / "a.txt").read_text() == "A", (d/"a.txt").read_text()
assert agent._CHECKPOINTS == [], agent._CHECKPOINTS

# ---- Integration: run_agent makes a checkpoint before a real write_file ----
agent.get_num_ctx = lambda m: 4096
agent.ollama_runner_rss_gb = lambda: None
config.MAX_VERIFY_NUDGES = 0  # keep the scripted turn count deterministic
agent._CHECKPOINTS = []; agent._checkpoint_turn = 3
(d / "c.txt").write_text("original")
class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content=content; s.tool_calls=tool_calls; s.thinking=thinking
class Resp:
    def __init__(s,m): s.message=m
class F:
    def __init__(s,n,a): s.name=n; s.arguments=a
class TC:
    def __init__(s,n,a): s.function=F(n,a)
script = iter([
    Msg(tool_calls=[TC("write_file", {"path": "c.txt", "content": "changed by model"})]),
    Msg(content="Done.", tool_calls=None),
])
agent.ollama.chat = lambda **kw: Resp(next(script))
agent.run_agent([{"role":"system","content":"s"},{"role":"user","content":"edit c"}], "m")
assert len(agent._CHECKPOINTS) == 1, agent._CHECKPOINTS
# undo should bring c.txt back to "original"
agent.cmd_undo_restore("last")
assert (d / "c.txt").read_text() == "original", (d/"c.txt").read_text()

log = agent._AUDIT_LOG.read_text()
assert "CHECKPOINT" in log and "UNDO_CHECKPOINT" in log, log
print("B1 ALL PASS")
