import os, tempfile, pathlib, json, time
import agent
from agentic import state

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"
sess = d / ".agentic" / "sessions"; sess.mkdir(parents=True)
state._SESSION_DIR = sess

# 1. save skips a system-only conversation
state._SESSION_FILE = sess / "20260101_000000.json"
agent._save_session([{"role": "system", "content": "s"}], "m")
assert not state._SESSION_FILE.exists(), "empty session should not be saved"

# 2. save a real conversation
msgs = [
    {"role": "system", "content": "s"},
    {"role": "user", "content": "hello there general"},
    {"role": "assistant", "content": "hi", "tool_calls": [{"function": {"name": "get_datetime", "arguments": {}}}]},
    {"role": "tool", "content": "2026-08-05"},
    {"role": "assistant", "content": "It is 2026."},
]
agent._save_session(msgs, "primary:model")
assert state._SESSION_FILE.exists()
data = json.loads(state._SESSION_FILE.read_text())
assert data["model"] == "primary:model" and len(data["messages"]) == 5

# 3. a second, newer session
time.sleep(0.05)
state._SESSION_FILE = sess / "20260102_000000.json"
msgs2 = [{"role": "system", "content": "s"}, {"role": "user", "content": "second session topic"},
         {"role": "assistant", "content": "ok"}]
agent._save_session(msgs2, "backup:model")

# 4. list: newest first, preview present
lst = agent._list_sessions()
assert len(lst) == 2, lst
assert lst[0]["preview"] == "second session topic", lst[0]
assert "Saved sessions" in agent.cmd_resume_list()

# 5. resume 'last' loads newest
loaded = agent.cmd_resume_load("last")
assert loaded is not None
m, model = loaded
assert model == "backup:model" and any("second session topic" in x.get("content", "") for x in m)

# 6. resume by index 2 loads the older one
loaded2 = agent.cmd_resume_load("2")
assert loaded2[1] == "primary:model", loaded2[1]
assert any("hello there general" in x.get("content", "") for x in loaded2[0])

# 7. bad index → None
assert agent.cmd_resume_load("99") is None
assert agent.cmd_resume_load("nope") is None

# 8. tool_calls survive the round trip (JSON serializable)
assert any(x.get("tool_calls") for x in loaded2[0])

log = state._AUDIT_LOG.read_text()
assert "RESUME_SESSION" in log, log
print("B3 ALL PASS")
