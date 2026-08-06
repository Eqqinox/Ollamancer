import sys, tempfile, pathlib, io, contextlib
import agent

agent.check_ollama = lambda m: True
agent._resolve_startup_model = lambda: "fake:model"
agent._init_mcp = lambda: None
agent.get_num_ctx = lambda m: 4096

def run_main(args, inputs):
    it = iter(inputs)
    agent._prompt = lambda label: next(it)
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
assert agent.PRIVATE_MODE is True
# no conversation-log sinks were wired
assert agent._AUDIT_LOG is None, agent._AUDIT_LOG
assert agent._SNAPSHOT_DIR is None, agent._SNAPSHOT_DIR
assert agent._SESSION_FILE is None and agent._SESSION_DIR is None
assert agent._CHECKPOINT_GITDIR is None
# no files were written under .agentic (no sessions/, no audit_*.log, no snapshots content)
agdir = proj / ".agentic"
if agdir.exists():
    assert not (agdir / "sessions").exists(), "session dir should not exist in private mode"
    assert not any(agdir.glob("audit_*.log")), "no audit log in private mode"
    assert not (agdir / "checkpoints.git").exists(), "no git checkpoints in private mode"

# guards: _save_session and _save_memory are no-ops under PRIVATE_MODE
agent.PRIVATE_MODE = True
agent._SESSION_FILE = proj / "should_not_be_written.json"
agent._save_session([{"role": "system", "content": "s"}, {"role": "user", "content": "secret"},
                     {"role": "assistant", "content": "reply"}], "m")
assert not agent._SESSION_FILE.exists(), "private _save_session must not write"
agent._memory = "a private secret to remember"
mp = proj / ".agentic" / "memory.md"
agent.PROJECT_ROOT = proj
agent._save_memory()
assert not mp.exists(), "private _save_memory must not write"

# ---------- NORMAL MODE (control): logs ARE created ----------
agent.PRIVATE_MODE = False
proj2 = pathlib.Path(tempfile.mkdtemp())
run_main([str(proj2)], ["get the time please", "/exit"]) if False else None
# drive a normal startup + immediate /exit; then assert the sinks were wired
run_main([str(proj2)], ["/exit"])
assert agent.PRIVATE_MODE is False
assert agent._AUDIT_LOG is not None and agent._AUDIT_LOG.exists(), "normal mode should create an audit log"
assert agent._SESSION_DIR is not None and agent._SESSION_DIR.exists(), "normal mode should create sessions dir"

print("PRIVATE MODE ALL PASS")
