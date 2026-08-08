import os, tempfile, pathlib, types
import agent
from agentic.tools import rag
from agentic import loop, models
from agentic import config, state
models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None
config.STREAM_FINAL = "on"
d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"

def chunk(content="", tool_calls=None):
    return types.SimpleNamespace(message=types.SimpleNamespace(content=content, tool_calls=tool_calls, thinking=None),
                                 prompt_eval_count=10)

# 1. _EscapeWatcher is a safe NO-OP when stdin isn't a TTY (tests, pipes, headless) , 
#    it must NEVER abort in non-interactive contexts.
w = loop._EscapeWatcher()
w.__enter__()
assert w.pressed() is False   # non-tty → never "pressed"
w.__exit__(None, None, None)

# 2. _consume_stream raises _UserAbort when abort_check fires
class ClosableIter:
    def __init__(self, items): self._it = iter(items); self.closed = False
    def __iter__(self): return self
    def __next__(self): return next(self._it)
    def close(self): self.closed = True
s = ClosableIter([chunk("hi"), chunk(" there")])
try:
    loop._consume_stream(s, abort_check=lambda: True)
    assert False, "should have raised _UserAbort"
except loop._UserAbort:
    pass
assert s.closed is True, "stream should be closed on abort (signals Ollama to stop)"

# 3. _consume_stream completes normally when abort_check never fires
s2 = ClosableIter([chunk("full "), chunk("answer")])
resp = loop._consume_stream(s2, abort_check=lambda: False)
assert resp.message.content == "full answer"

# 4. run_agent propagates _UserAbort when a keypress is simulated (patch watcher.pressed → True)
orig_pressed = loop._EscapeWatcher.pressed
loop._EscapeWatcher.pressed = lambda self: True
def fake_stream(**kw):
    return ClosableIter([chunk("partial answer being streamed…")])
rag.ollama.chat = fake_stream
try:
    loop.run_agent([{"role": "system", "content": "s"}, {"role": "user", "content": "do a long thing"}], "m")
    assert False, "run_agent should propagate _UserAbort"
except loop._UserAbort:
    pass
loop._EscapeWatcher.pressed = orig_pressed   # restore

# 5. run_agent completes normally when no key is pressed (watcher no-op in tests)
seq = iter([ClosableIter([chunk("final answer")])])
rag.ollama.chat = lambda **kw: next(seq)
final = loop.run_agent([{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}], "m")
assert final == "final answer", final

# 6. _UserAbort is an Exception (so call sites' `except _UserAbort` work and it's catchable)
assert issubclass(loop._UserAbort, Exception)

print("ESCAPE-TO-STOP ALL PASS")
