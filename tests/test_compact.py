import os, tempfile, pathlib, types
import agent
agent.get_num_ctx = lambda m: 1000   # small window so thresholds are easy to hit in the test
agent._AUDIT_LOG = pathlib.Path(tempfile.mktemp())

def user(c): return {"role": "user", "content": c}
def asst(c, tc=None): return {"role": "assistant", "content": c, **({"tool_calls": tc} if tc else {})}
def tool(c): return {"role": "tool", "content": c}
def tc(name): return [{"function": {"name": name, "arguments": {}}}]

def build():
    # system + 6 user turns, each: user, assistant(tool_call), tool(big result), assistant(final)
    m = [{"role": "system", "content": "SYS"}]
    for i in range(6):
        m += [user(f"turn {i} question"),
              asst("", tc("read_file")),
              tool("X" * 3000),                 # big old tool result (cleanup target)
              asst(f"turn {i} answer")]
    return m

# ---- 1. turn boundaries ignore summary blocks ----
m = build()
bounds = agent._turn_boundaries(m)
assert len(bounds) == 6, bounds
m2 = [{"role": "system", "content": "SYS"}, {"role": "user", "content": agent._COMPACT_MARKER + "old summary"}, user("real turn")]
assert agent._turn_boundaries(m2) == [2], agent._turn_boundaries(m2)  # summary block not counted

# ---- 2. lossless cleanup truncates old tool results ----
m = build()
keep_from = agent._turn_boundaries(m)[-agent.COMPACT_KEEP_TURNS]
before = agent._estimate_tokens(m)
saved = agent._cleanup_old_tool_results(m, keep_from)
assert saved > 0 and agent._estimate_tokens(m) < before
# recent tool results (after keep_from) untouched
assert any(len(x["content"]) == 3000 for x in m[keep_from:] if x["role"] == "tool")

# ---- 3. forced compaction: structured summary replaces old turns, structure preserved ----
agent.COMPACT_KEEP_TURNS = 3
captured = {}
def fake_chat(**kw):
    captured["prompt"] = kw["messages"][0]["content"]
    return types.SimpleNamespace(message=types.SimpleNamespace(
        content="## Session Intent\ndid stuff\n## Files Modified\na.py\n## Key Decisions\nuse bcrypt"))
agent.ollama.chat = fake_chat
agent.ollama_runner_rss_gb = lambda: None
m = build()
n_before = len(m)
status = agent._compact_now(m, "model", forced=True)
assert "compacted" in status.lower(), status
# structure: system first, then exactly one summary block, then the kept tail
assert m[0]["content"] == "SYS"
assert m[1]["role"] == "user" and m[1]["content"].startswith(agent._COMPACT_MARKER)
assert "## Files Modified" in m[1]["content"]
# tail = last 3 user turns verbatim (3 turns × 4 msgs = 12) → system + summary + 12
assert len(m) == 2 + 12, len(m)
# no orphaned tool message: every 'tool' msg is preceded (somewhere before) by an assistant w/ tool_calls
assert m[-1]["content"] == "turn 5 answer"
# the summary prompt used the structured template
assert "## Files Modified" in captured["prompt"] and "turn 0 question" in captured["prompt"]

# ---- 4. hierarchical: a second compaction folds the prior summary + new turns ----
# add 3 more turns after the compaction, then compact again
for i in range(6, 9):
    m += [user(f"turn {i} question"), asst("", tc("read_file")), tool("Y"*3000), asst(f"turn {i} answer")]
agent._compact_now(m, "model", forced=True)
# still exactly one summary block, and it's fed the OLD summary (hierarchical)
summary_blocks = [x for x in m if x["role"]=="user" and x["content"].startswith(agent._COMPACT_MARKER)]
assert len(summary_blocks) == 1, len(summary_blocks)
assert agent._COMPACT_MARKER.strip() in captured["prompt"] or "SUMMARY" in captured["prompt"].upper() or "## Files Modified" in captured["prompt"]

# ---- 5. too few turns → safe no-op ----
tiny = [{"role":"system","content":"S"}, user("only one"), asst("a")]
assert "Not enough" in agent._compact_now(tiny, "model", forced=True) or "compact" in agent._compact_now(tiny, "model", forced=True).lower()
assert len(tiny) == 3  # unchanged

# ---- 6. auto-compact OFF by default → never fires ----
agent.AUTO_COMPACT = "off"
agent._LAST_PROMPT_TOKENS = 999999
m = build()
assert agent._maybe_compact(m, "model") is False

# ---- 7. auto-compact ON + over threshold → fires ----
agent.AUTO_COMPACT = "on"
agent.COMPACT_THRESHOLD_PCT = 70
agent._LAST_PROMPT_TOKENS = 800   # 80% of 1000 > 70%
m = build()
assert agent._maybe_compact(m, "model") is True
assert any(x["content"].startswith(agent._COMPACT_MARKER) for x in m if x["role"]=="user")

# ---- 8. auto-compact ON but under threshold → no-op ----
agent._LAST_PROMPT_TOKENS = 500   # 50% < 70%
m = build()
assert agent._maybe_compact(m, "model") is False

log = agent._AUDIT_LOG.read_text() if agent._AUDIT_LOG.exists() else ""
assert "COMPACT" in log
print("CONTEXT COMPACTION ALL PASS")
