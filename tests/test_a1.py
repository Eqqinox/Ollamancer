import os, tempfile, pathlib
import agent
from agentic import config, state

d = pathlib.Path(tempfile.mkdtemp())
os.chdir(d)
state.PROJECT_ROOT = d.resolve()

# 1. append creates a new file
r1 = agent.append_file("out.txt", "line1\n")
assert r1.startswith("Appended:"), r1
assert "new file created" in r1, r1
assert (d / "out.txt").read_text() == "line1\n"

# 2. append adds to existing
r2 = agent.append_file("out.txt", "line2\n")
assert r2.startswith("Appended:"), r2
assert "new file created" not in r2, r2
assert (d / "out.txt").read_text() == "line1\nline2\n"

# 3. chunked-write equivalence: write_file + 2 appends == one big write
big = "".join(f"row {i}\n" for i in range(200))
first = "".join(f"row {i}\n" for i in range(80))
mid = "".join(f"row {i}\n" for i in range(80, 160))
last = "".join(f"row {i}\n" for i in range(160, 200))
agent.write_file("chunked.txt", first)
agent.append_file("chunked.txt", mid)
agent.append_file("chunked.txt", last)
assert (d / "chunked.txt").read_text() == big

# 4. large-write note fires only for big content
small_res = agent.write_file("small.txt", "a\nb\nc\n")
assert "prefer writing in chunks" not in small_res, small_res
big_res = agent.write_file("big.txt", big)
assert "prefer writing in chunks" in big_res, big_res
assert "201 lines" in big_res or "200 lines" in big_res, big_res

# 5. GEN_NUM_PREDICT finite warning
config.GEN_NUM_PREDICT = 10
warn_res = agent.write_file("big2.txt", big)
assert "num_predict" in warn_res, warn_res
config.GEN_NUM_PREDICT = -1
noover = agent.write_file("big3.txt", big)
assert "num_predict" not in noover, noover

# 6. registration & tracking
assert agent.append_file in agent.TOOLS
assert "append_file" in agent.TOOL_MAP
assert "append_file" in agent._EDIT_TOOLS
assert agent._EDIT_SUCCESS_PREFIX["append_file"] == "Appended:"

# 7. path safety: outside project blocked
blocked = agent.append_file("/etc/evil.txt", "x")
assert blocked.startswith("⛔"), blocked

# 8. syntax warning still flows through append for .py
agent.write_file("mod.py", "def f():\n    return 1\n")
bad = agent.append_file("mod.py", "def g(\n")
assert "syntax" in bad.lower() or "SyntaxError" in bad, bad

print("A1 ALL PASS")
