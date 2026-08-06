import tempfile, pathlib
import agent
from agentic import state

state._AUDIT_LOG = pathlib.Path(tempfile.mktemp())


class FakeBlock:
    def __init__(self, text): self.text = text
class FakeResult:
    def __init__(self, text): self.content = [FakeBlock(text)]
class FakeConn:
    def __init__(self, text=None, raise_if_called=False):
        self.text = text; self.raise_if_called = raise_if_called; self.calls = []
    def call_tool(self, name, args):
        self.calls.append((name, args))
        if self.raise_if_called:
            raise AssertionError("DDG failover should NOT have been called")
        return FakeResult(self.text), []


def set_ddg(conn):
    agent.MCP_TOOL_MAP.clear()
    if conn is not None:
        agent.MCP_TOOL_MAP["mcp__duckduckgo__search"] = (conn, "search")

def patch_searxng(fn):
    agent._searxng_fetch = fn

GOOD = [{"title": "Real", "url": "http://ex.com/a", "content": "x" * 100, "engines": ["google"]}]
THIN = [{"title": "Cat", "url": "http://ex.com", "content": "hi", "engines": ["bing"]}]

# 1. No MCP + empty SearXNG → unchanged "No results."
set_ddg(None); patch_searxng(lambda q, c="general": [])
assert agent.search_web("nothing here") == "No results."

# 2. DDG configured + empty SearXNG → failover text returned
ddg = FakeConn(text="DDG: found article about foo\nhttp://foo.com")
set_ddg(ddg); patch_searxng(lambda q, c="general": [])
r = agent.search_web("some query")
assert "DDG: found article" in r, r
assert r.startswith(agent._WEB_SNIPPET_HEADER[:20]), r[:60]
assert ddg.calls, "DDG not called"

# 3. DDG + thin excerpts → failover
ddg = FakeConn(text="DDG thin rescue content http://bar.com")
set_ddg(ddg); patch_searxng(lambda q, c="general": THIN)
r = agent.search_web("thin query")
assert "DDG thin rescue" in r, r

# 4. DDG + SearXNG raises → failover
ddg = FakeConn(text="DDG after crash http://baz.com")
def boom(q, c="general"): raise ValueError("CAPTCHA page not JSON")
set_ddg(ddg); patch_searxng(boom)
r = agent.search_web("crash query")
assert "DDG after crash" in r, r

# 5. Good SearXNG → NO failover (DDG must not be called)
ddg = FakeConn(raise_if_called=True)
set_ddg(ddg); patch_searxng(lambda q, c="general": GOOD)
r = agent.search_web("good query")
assert "Real" in r and "http://ex.com/a" in r, r
assert not ddg.calls, "DDG should not have been called on good results"

# 6. _find_mcp_search_tool matches duckduckgo
set_ddg(FakeConn())
found = agent._find_mcp_search_tool()
assert found is not None and found[1] == "search"

# 7. DDG returns empty → failover yields None, falls back to "No results."
empty_ddg = FakeConn(text="(empty result)")
set_ddg(empty_ddg); patch_searxng(lambda q, c="general": [])
assert agent.search_web("q") == "No results."

# 8. audit event written
log = state._AUDIT_LOG.read_text() if state._AUDIT_LOG.exists() else ""
assert "SEARCH_FAILOVER_DDG" in log, log

print("A2 ALL PASS")
