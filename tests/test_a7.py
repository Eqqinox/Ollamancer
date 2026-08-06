import os, tempfile, pathlib
import agent
from agentic.tools import rag
from agentic import loop, models
from agentic import config, state
config.STREAM_FINAL = "off"  # these predate streaming; use buffered path

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None
state._AUDIT_LOG = d / "audit.log"

class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content = content; s.tool_calls = tool_calls; s.thinking = thinking
class Resp:
    def __init__(s, m): s.message = m

def RErr(text):
    return rag.ollama.ResponseError(text)

# Helper for _plumbing_failover_target
config.PLUMBING_FAILOVER_MODEL = "backup:model"
assert models._plumbing_failover_target("primary:model") == "backup:model"
assert models._plumbing_failover_target("backup:model") is None      # never to itself
config.PLUMBING_FAILOVER_MODEL = ""
assert models._plumbing_failover_target("primary:model") is None     # disabled

# --- Scenario 1: failover ENABLED. Primary keeps hitting the JSON-truncation bug,
#     retries exhaust, then it fails over to backup which answers. ---
config.PLUMBING_FAILOVER_MODEL = "backup:model"
calls = {"models": []}
# script: primary raises 3x (1 initial + 2 retries exhausts budget=2), then after
# failover the backup model returns a normal final answer.
call_count = {"i": 0}
def fake_chat(**kw):
    calls["models"].append(kw["model"])
    # raise while on primary, succeed once we've switched to backup
    if kw["model"] == "primary:model":
        raise RErr("unexpected end of JSON input")
    return Resp(Msg(content="Backup model answered fine.", tool_calls=None))
rag.ollama.chat = fake_chat
msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "do it"}]
final = loop.run_agent(msgs, "primary:model")
assert final == "Backup model answered fine.", final
assert "primary:model" in calls["models"] and "backup:model" in calls["models"], calls["models"]
log = state._AUDIT_LOG.read_text()
assert "MODEL_FAILOVER" in log and '"trigger": "json_truncation"' in log, log

# --- Scenario 2: failover DISABLED → returns the fallback message, no switch ---
config.PLUMBING_FAILOVER_MODEL = ""
def fake_chat2(**kw):
    raise RErr("unexpected end of JSON input")
rag.ollama.chat = fake_chat2
msgs2 = [{"role": "system", "content": "s"}, {"role": "user", "content": "do it"}]
final2 = loop.run_agent(msgs2, "primary:model")
assert "truncated tool-call response" in final2 or "tronquée" in final2, final2

# --- Scenario 3: failover set to SAME model as current → no switch, fallback returned ---
config.PLUMBING_FAILOVER_MODEL = "primary:model"
rag.ollama.chat = fake_chat2
msgs3 = [{"role": "system", "content": "s"}, {"role": "user", "content": "do it"}]
final3 = loop.run_agent(msgs3, "primary:model")
assert "truncated" in final3 or "tronquée" in final3, final3

print("A7 ALL PASS")
