"""Compact tool display, and the /details record that backs it.

The point of the compact mode is that it shows less on screen while *keeping* more: the
old two-panel view cut every result at 300 characters and threw the remainder away, so
after the turn there was no way to see what a tool had actually returned. The record
asserted here is what makes the collapse lossless.

Offline. No model, no Ollama.

    PYTHONPATH="$PWD" python tests/test_tool_display.py
"""

from agentic import commands, config, loop, state

# ── the one-line summary ─────────────────────────────────────────────────────

# The argument shown is the one that identifies the call, not the whole JSON blob.
assert loop._brief_args({"query": "npm worm"}) == '"npm worm"'
assert loop._brief_args({"path": "agentic/loop.py"}) == '"agentic/loop.py"'
# A recognised key wins over position, so the line stays readable whatever the tool.
assert loop._brief_args({"limit": 5, "query": "hello"}) == '"hello"'
# Unknown shapes still produce something rather than nothing.
assert loop._brief_args({"weird": "value"}) == "value"
assert loop._brief_args({}) == ""
assert loop._brief_args("not a dict") == ""
# Long values are cut, and newlines never break the single-line layout.
long = loop._brief_args({"query": "x" * 200})
assert len(long) < 45 and "…" in long, long
assert "\n" not in loop._brief_args({"query": "a\nb\nc"})

# The prefix is padded so the metrics line up in a column, and carries no newline:
# the loop completes the line after the tool returns.
prefix = loop._compact_call_prefix("search_web", {"query": "test"})
assert "\n" not in prefix
assert "search_web" in prefix

# A very long tool name plus args must still be truncated to the column width.
wide = loop._compact_call_prefix("a_very_long_tool_name_indeed", {"query": "y" * 200})
assert "…" in wide, wide

# Sizes are human units, and a blocked call says so instead of reporting a size.
assert "512 B" in loop._compact_call_suffix("z" * 512, 0.4, False)
assert "2.0 KB" in loop._compact_call_suffix("z" * 2048, 0.4, False)
assert "1.0 MB" in loop._compact_call_suffix("z" * 1048576, 0.4, False)
assert "blocked" in loop._compact_call_suffix("nope", 0.01, True)
assert "1.8s" in loop._compact_call_suffix("abc", 1.83, False)

# ── /details ─────────────────────────────────────────────────────────────────

state._last_turn_tool_calls.clear()
assert "details_none" not in commands._render_tool_details("")   # rendered, not a raw key

big = "R" * 5000
state._last_turn_tool_calls.extend([
    {"name": "search_web", "args": {"query": "q"}, "result": big, "seconds": 1.2, "blocked": False},
    {"name": "run_command", "args": {"command": "rm -rf /"}, "result": "refused",
     "seconds": 0.01, "blocked": True},
])

full = commands._render_tool_details("")
# The whole result is present. This is the property the 300-char panel could not offer.
assert big in full, "result was truncated; the point of /details is that it is not"
assert "search_web" in full and "run_command" in full
assert "blocked" in full
assert '"query": "q"' in full, "arguments must be shown in full"

one = commands._render_tool_details("2")
assert "run_command" in one and "search_web" not in one, one

for bad in ("99", "0", "-1", "abc"):
    msg = commands._render_tool_details(bad)
    assert "run_command" not in msg and "search_web" not in msg, f"{bad} should not select a call"

# ── wiring ───────────────────────────────────────────────────────────────────

# reset() must clear the record, or /details would describe a previous session.
state.reset()
assert state._last_turn_tool_calls == []

# The setting exists, is an enum of exactly the two modes, and defaults to compact.
from agentic import ui
entry = next(p for p in ui._all_params() if p["var"] == "TOOL_DISPLAY")
assert set(entry["options"]) == {"compact", "full"}, entry
assert config.TOOL_DISPLAY == "compact"

# Both languages document the command and have every string it renders.
from agentic.i18n import STR
for lang in ("en", "fr"):
    for key in ("details_none", "details_bad_index", "details_args", "details_result"):
        assert key in STR[lang], f"{key} missing from {lang}"

print("test_tool_display: ALL PASS")
