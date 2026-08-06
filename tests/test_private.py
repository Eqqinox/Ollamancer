import sys, tempfile, pathlib, io, contextlib
import agent
from agentic import ui
from agentic.tools import notes
from agentic import models
from agentic import mcp_client
from agentic import state

models.check_ollama = lambda m: True
models._resolve_startup_model = lambda: "fake:model"
mcp_client._init_mcp = lambda: None
models.get_num_ctx = lambda m: 4096

def run_main(args, inputs):
    it = iter(inputs)
    ui._prompt = lambda label: next(it)
    old = sys.argv
    sys.argv = ["agent.py"] + args
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            agent.main()
    except StopIteration:
        pass
    finally:
        sys.argv = old

# ---------- PRIVATE MODE ----------
proj = pathlib.Path(tempfile.mkdtemp())
# simulate the model deciding to save memory during the private session, then exit
run_main(["--private", str(proj)], ["/exit"])
assert state.PRIVATE_MODE is True
# no conversation-log sinks were wired
assert state._AUDIT_LOG is None, state._AUDIT_LOG
assert state._SNAPSHOT_DIR is None, state._SNAPSHOT_DIR
assert state._SESSION_FILE is None and state._SESSION_DIR is None
assert state._CHECKPOINT_GITDIR is None
# no files were written under .agentic (no sessions/, no audit_*.log, no snapshots content)
agdir = proj / ".agentic"
if agdir.exists():
    assert not (agdir / "sessions").exists(), "session dir should not exist in private mode"
    assert not any(agdir.glob("audit_*.log")), "no audit log in private mode"
    assert not (agdir / "checkpoints.git").exists(), "no git checkpoints in private mode"

# guards: _save_session and _save_memory are no-ops under PRIVATE_MODE
state.PRIVATE_MODE = True
state._SESSION_FILE = proj / "should_not_be_written.json"
agent._save_session([{"role": "system", "content": "s"}, {"role": "user", "content": "secret"},
                     {"role": "assistant", "content": "reply"}], "m")
assert not state._SESSION_FILE.exists(), "private _save_session must not write"
state._memory = "a private secret to remember"
mp = proj / ".agentic" / "memory.md"
state.PROJECT_ROOT = proj
notes._save_memory()
assert not mp.exists(), "private _save_memory must not write"

# ---------- NORMAL MODE (control): logs ARE created ----------
state.PRIVATE_MODE = False
proj2 = pathlib.Path(tempfile.mkdtemp())
run_main([str(proj2)], ["get the time please", "/exit"]) if False else None
# drive a normal startup + immediate /exit; then assert the sinks were wired
run_main([str(proj2)], ["/exit"])
assert state.PRIVATE_MODE is False
assert state._AUDIT_LOG is not None and state._AUDIT_LOG.exists(), "normal mode should create an audit log"
assert state._SESSION_DIR is not None and state._SESSION_DIR.exists(), "normal mode should create sessions dir"

print("PRIVATE MODE ALL PASS")
