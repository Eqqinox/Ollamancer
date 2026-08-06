import os, tempfile, pathlib
import agent
from agentic import tools
from agentic.tools import rag
from agentic import config, models, state
config.STREAM_FINAL = "off"
config.MAX_VERIFY_NUDGES = 0
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"
state._CHECKPOINT_GITDIR = None   # skip checkpoints in this unit test

# 1. read-only toolset excludes the dangerous tools
ro = {fn.__name__ for fn in tools._read_only_tools()}
for banned in ("write_file", "append_file", "edit_file", "run_command", "run_tests", "git_commit", "create_directory"):
    assert banned not in ro, banned
for ok in ("read_file", "search_in_files", "find_references", "list_directory"):
    assert ok in ro, ok

# 2. model resolution
config.ARCHITECT_MODEL = "arch:m"; config.EDITOR_MODEL = "editor:m"
assert agent._architect_models("cur:m") == ("arch:m", "editor:m")
config.ARCHITECT_MODEL = ""; config.EDITOR_MODEL = ""
assert agent._architect_models("cur:m") == ("cur:m", "cur:m")   # degenerate fallback
config.ARCHITECT_MODEL = "arch:m"; config.EDITOR_MODEL = "editor:m"

# 3. record unload order (sequential loading guarantee)
unloaded = []
models._unload_model = lambda m: unloaded.append(m)

class F:
    def __init__(s,n,a): s.name=n; s.arguments=a
class TC:
    def __init__(s,n,a): s.function=F(n,a)
class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content=content; s.tool_calls=tool_calls; s.thinking=thinking
class Resp:
    def __init__(s,m): s.message=m

scripts = {
    "arch:m": iter([
        Msg(tool_calls=[TC("write_file", {"path": "arch_should_not_exist.txt", "content": "x"})]),  # must be refused
        Msg(content="PLAN:\n1. create editor_made.txt with hello", tool_calls=None),
    ]),
    "editor:m": iter([
        Msg(tool_calls=[TC("write_file", {"path": "editor_made.txt", "content": "hello"})]),          # allowed
        Msg(content="done", tool_calls=None),
    ]),
}
def router(**kw):
    return Resp(next(scripts[kw["model"]]))
rag.ollama.chat = router

msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "prior context"}]
plan, result = agent.cmd_architect("build the thing", msgs, "cur:m")

assert "PLAN:" in plan, plan
assert result == "done", result
# architect's write was refused → file must NOT exist
assert not (d / "arch_should_not_exist.txt").exists(), "read-only gate failed — architect wrote a file!"
# editor's write executed → file exists with content
assert (d / "editor_made.txt").read_text() == "hello", "editor did not write"
# sequential loading: current unloaded before architect, architect unloaded before editor
assert unloaded == ["cur:m", "arch:m"], unloaded
# main history not polluted with the architect's tool spam (only the 2 originals still)
assert len(msgs) == 2, [m.get("role") for m in msgs]

log = state._AUDIT_LOG.read_text()
assert "ARCHITECT_START" in log and "ARCHITECT_DONE" in log, log
assert "architect read-only" in log, "read-only refusal not audited"

print("B4 ALL PASS")
