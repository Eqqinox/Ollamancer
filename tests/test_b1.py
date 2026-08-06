import os, tempfile, pathlib
import agent
from agentic.tools import rag
from agentic import commands, loop, models
from agentic import checkpoints
from agentic import config, state
config.STREAM_FINAL = "off"  # these predate streaming; use buffered path

assert checkpoints._git_available(), "git binary required for this test"

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d)
state.PROJECT_ROOT = d.resolve()
(d / ".agentic").mkdir()
state._AUDIT_LOG = d / ".agentic" / "audit.log"
state._CHECKPOINTS = []
state._checkpoint_turn = 0
state._checkpoint_made_this_turn = False

checkpoints._init_checkpoints()
assert checkpoints._checkpoints_available(), "checkpoints should be available with git"

# initial project state
(d / "a.txt").write_text("v1")
(d / "keep.txt").write_text("keep")
# excluded heavy dirs that must survive an undo
(d / ".venv").mkdir(); (d / ".venv" / "junk").write_text("x")
(d / "node_modules").mkdir(); (d / "node_modules" / "lib.js").write_text("y")

# ---- Turn 1: checkpoint BEFORE first write, then writes happen ----
state._checkpoint_turn = 1
state._checkpoint_made_this_turn = False
checkpoints._make_turn_checkpoint("turn 1: before write_file")
# guard: a second call same turn is a no-op
checkpoints._make_turn_checkpoint("turn 1: before edit_file")
assert len(state._CHECKPOINTS) == 1, state._CHECKPOINTS

# the turn's writes: modify a.txt, create b.txt
(d / "a.txt").write_text("v2-MODIFIED")
(d / "b.txt").write_text("brand new file")

lst = commands.cmd_undo_list()
assert "turn 1: before write_file" in lst, lst

# ---- Undo last ----
msg = commands.cmd_undo_restore("last")
assert "Restored the project" in msg, msg
assert (d / "a.txt").read_text() == "v1", "a.txt not reverted"
assert not (d / "b.txt").exists(), "b.txt (created this turn) should be removed"
assert (d / "keep.txt").read_text() == "keep"
# excluded dirs untouched
assert (d / ".venv" / "junk").exists(), ".venv wrongly cleaned"
assert (d / "node_modules" / "lib.js").exists(), "node_modules wrongly cleaned"
# checkpoint consumed
assert state._CHECKPOINTS == [], state._CHECKPOINTS

# ---- Multi-turn step-back: two checkpoints, /undo <n> ----
state._CHECKPOINTS = []
(d / "a.txt").write_text("A")
state._checkpoint_turn = 2; state._checkpoint_made_this_turn = False
checkpoints._make_turn_checkpoint("turn 2")
(d / "a.txt").write_text("B")
state._checkpoint_turn = 3; state._checkpoint_made_this_turn = False
checkpoints._make_turn_checkpoint("turn 3")
(d / "a.txt").write_text("C")
assert len(state._CHECKPOINTS) == 2
# /undo 2 = the older one (display index 2 = turn 2 checkpoint) → a.txt back to "A"
r = commands.cmd_undo_restore("2")
assert (d / "a.txt").read_text() == "A", (d/"a.txt").read_text()
assert state._CHECKPOINTS == [], state._CHECKPOINTS

# ---- Integration: run_agent makes a checkpoint before a real write_file ----
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None
config.MAX_VERIFY_NUDGES = 0  # keep the scripted turn count deterministic
state._CHECKPOINTS = []; state._checkpoint_turn = 3
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
rag.ollama.chat = lambda **kw: Resp(next(script))
loop.run_agent([{"role":"system","content":"s"},{"role":"user","content":"edit c"}], "m")
assert len(state._CHECKPOINTS) == 1, state._CHECKPOINTS
# undo should bring c.txt back to "original"
commands.cmd_undo_restore("last")
assert (d / "c.txt").read_text() == "original", (d/"c.txt").read_text()

log = state._AUDIT_LOG.read_text()
assert "CHECKPOINT" in log and "UNDO_CHECKPOINT" in log, log
print("B1 ALL PASS")
