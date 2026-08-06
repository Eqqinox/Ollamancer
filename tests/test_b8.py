import os, tempfile, pathlib, types
import agent
from agentic.tools import rag
from agentic import commands, config, models, state
config.STREAM_FINAL = "off"
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"

# 1. no diff → cmd_review_by returns None
state._snapshots = {}
assert commands.cmd_review_by("reviewer:m", [{"role": "user", "content": "task"}], "main:m") is None

# 2. set up a real diff via _snapshots (file changed on disk vs snapshot)
f = d / "calc.py"; f.write_text("def add(a, b):\n    return a - b\n")   # buggy current content
state._snapshots = {str(f.resolve()): "def add(a, b):\n    return a + b\n"}   # original was correct
assert "diff" in commands.cmd_diff().lower() or "```diff" in commands.cmd_diff()

# 3. reviewer critique + sequential unload
unloaded = []
models._unload_model = lambda m: unloaded.append(m)
def fake_chat(**kw):
    assert kw["model"] == "reviewer:m"
    return types.SimpleNamespace(message=types.SimpleNamespace(
        content="Bug: add() now subtracts instead of adds — line `return a - b` is wrong."))
rag.ollama.chat = fake_chat
msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "make add() work"}]
critique = commands.cmd_review_by("reviewer:m", msgs, "main:m")
assert "subtract" in critique, critique
assert unloaded == ["main:m", "reviewer:m"], unloaded   # sequential: main out before reviewer, reviewer out after

log = state._AUDIT_LOG.read_text()
assert "REVIEW_BY_START" in log and "REVIEW_BY_DONE" in log, log

# 4. same model as current → no unload churn
unloaded.clear()
rag.ollama.chat = lambda **kw: types.SimpleNamespace(message=types.SimpleNamespace(content="looks fine"))
commands.cmd_review_by("main:m", msgs, "main:m")
assert unloaded == [], unloaded

print("B8 ALL PASS")
