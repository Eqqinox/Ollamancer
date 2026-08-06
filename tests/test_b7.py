import os, tempfile, pathlib
import agent
from agentic import state

d = pathlib.Path(tempfile.mkdtemp()); os.chdir(d); state.PROJECT_ROOT = d.resolve()
state.SANDBOX_MODE = False

# 1. state persists across calls
assert agent.python_repl("x = 40 + 2") == "(no output)", "assignment should have no output"
assert agent.python_repl("print(x)").strip() == "42"

# 2. last-expression echo (REPL behavior)
assert agent.python_repl("2 * 21").strip() == "42"

# 3. multi-line block with final expression
out = agent.python_repl("def sq(n):\n    return n*n\nsq(7)")
assert out.strip() == "49", out

# 4. imports persist
agent.python_repl("import math")
assert agent.python_repl("math.floor(3.9)").strip() == "3"

# 5. exceptions surface as traceback, don't kill the session
err = agent.python_repl("raise ValueError('boom')")
assert "ValueError" in err and "boom" in err, err
assert agent.python_repl("print('still alive')").strip() == "still alive"  # session survived

# 6. safety filter blocks destructive shell embedded in code
blocked = agent.python_repl("import os; os.system('rm -rf /')")
assert blocked.startswith("⛔"), blocked

# 7. timeout resets the interpreter (use a small timeout via monkeypatch-free infinite loop)
#    keep it fast: patch the read timeout by calling with a tiny loop then confirm recovery
import agent as A
# simulate a hang: an infinite loop should time out and reset
# (temporarily shrink the timeout by wrapping _repl_read_until_done)
_orig = A._repl_read_until_done
A._repl_read_until_done = lambda proc, timeout: _orig(proc, 2)
t = agent.python_repl("while True:\n    pass")
assert t.startswith("⏱ Timeout"), t
A._repl_read_until_done = _orig
# recovers cleanly after the reset
assert agent.python_repl("1 + 1").strip() == "2"

# registration + risky
assert agent.python_repl in agent.TOOLS
assert "python_repl" in agent._RISKY_TOOLS
assert "append_file" in agent._RISKY_TOOLS  # also hardened in B7

agent._repl_stop()
print("B7 ALL PASS")
