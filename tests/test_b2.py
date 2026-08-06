import os, tempfile, pathlib, types
import agent
from agentic.tools import rag
from agentic import models
from agentic import config, state

models.get_num_ctx = lambda m: 4096
models.ollama_runner_rss_gb = lambda: None
d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state._AUDIT_LOG = d / "audit.log"

def chunk(content="", tool_calls=None, thinking=None):
    return types.SimpleNamespace(message=types.SimpleNamespace(
        content=content, tool_calls=tool_calls, thinking=thinking))

def F(n, a): return types.SimpleNamespace(function=types.SimpleNamespace(name=n, arguments=a))

# 1. _consume_stream reconstructs a plain-text answer + calls on_text incrementally
seen = []
stream = iter([chunk("Hel"), chunk("lo "), chunk("world"), chunk(thinking="hmm")])
resp = agent._consume_stream(stream, on_text=lambda t: seen.append(t))
assert resp.message.content == "Hello world", resp.message.content
assert resp.message.tool_calls is None
assert resp.message.thinking == "hmm"
assert seen == ["Hel", "Hello ", "Hello world"], seen

# 2. tool_calls in stream → reconstructed, and on_text stops once tool_calls appear
seen2 = []
stream2 = iter([chunk("prefix "), chunk(tool_calls=[F("write_file", {"path": "x"})]), chunk("ignored-after")])
resp2 = agent._consume_stream(stream2, on_text=lambda t: seen2.append(t))
assert resp2.message.tool_calls and resp2.message.tool_calls[0].function.name == "write_file"
assert resp2.message.content == "prefix ignored-after"   # content still accumulates
assert seen2 == ["prefix "], seen2   # live text stopped as soon as a tool_call arrived

# 3. STREAM_FINAL off → buffered path used (stream=False)
config.STREAM_FINAL = "off"
calls = []
def fake_chat_buf(**kw):
    calls.append(kw.get("stream"))
    return types.SimpleNamespace(message=types.SimpleNamespace(content="buffered", tool_calls=None, thinking=None))
rag.ollama.chat = fake_chat_buf
r = agent._stream_or_buffer_chat("m", [{"role": "user", "content": "hi"}])
assert r.message.content == "buffered"
assert calls == [False], calls

# 4. STREAM_FINAL on → stream=True path used
config.STREAM_FINAL = "on"
def fake_chat_stream(**kw):
    assert kw.get("stream") is True
    return iter([chunk("streamed "), chunk("answer")])
rag.ollama.chat = fake_chat_stream
r2 = agent._stream_or_buffer_chat("m", [{"role": "user", "content": "hi"}])
assert r2.message.content == "streamed answer", r2.message.content

# 5. Integration in run_agent: streaming tool round then streaming final answer
def make_router(rounds):
    it = iter(rounds)
    def router(**kw):
        item = next(it)
        return iter(item) if kw.get("stream") else item
    return router
config.MAX_VERIFY_NUDGES = 0
rag.ollama.chat = make_router([
    [chunk(tool_calls=[F("todo_write", {"checklist": "- [ ] go"})])],   # tool round (streamed)
    [chunk("Final "), chunk("streamed "), chunk("reply.")],              # final answer (streamed)
])
final = agent.run_agent([{"role": "system", "content": "s"}, {"role": "user", "content": "do"}], "m")
assert final == "Final streamed reply.", repr(final)

# 6. Mid-stream plumbing error still propagates → retry branch handles it (fallback returned)
def boom_stream(**kw):
    def gen():
        yield chunk("partial")
        raise rag.ollama.ResponseError("unexpected end of JSON input")
    return gen() if kw.get("stream") else None
config.PLUMBING_FAILOVER_MODEL = ""
rag.ollama.chat = boom_stream
final2 = agent.run_agent([{"role": "system", "content": "s"}, {"role": "user", "content": "do"}], "m")
assert "truncated" in final2 or "tronquée" in final2, final2

print("B2 ALL PASS")
