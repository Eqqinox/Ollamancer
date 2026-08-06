import os, sys, tempfile, pathlib, io, types, contextlib
import agent

# 1. failure heuristic
assert agent._looks_like_failure("⚠️ Stopped after 25 rounds")
assert agent._looks_like_failure("⛔ Blocked: nope")
assert not agent._looks_like_failure("Here is your answer, all good.")

# 2. recipe parsing — Constraints + Steps headings
d = pathlib.Path(tempfile.mkdtemp())
rp = d / "recipe.md"
rp.write_text("""# My recipe
## Constraints
- do not touch tests
- keep it small
## Steps
1. read config.py
2. add a --verbose flag
""")
steps = agent._parse_recipe(str(rp))
assert len(steps) == 2, steps
assert "read config.py" in steps[0] and "do not touch tests" in steps[0], steps[0]
assert "--verbose flag" in steps[1]

# plain list, no headings → each item a step
rp2 = d / "plain.md"; rp2.write_text("- first thing\n- second thing\n")
s2 = agent._parse_recipe(str(rp2))
assert s2 == ["first thing", "second thing"], s2

# no list at all → whole file is one step
rp3 = d / "prose.md"; rp3.write_text("Just do the whole thing please.")
s3 = agent._parse_recipe(str(rp3))
assert s3 == ["Just do the whole thing please."], s3

# 3. end-to-end headless --run via main(), catching SystemExit
proj = pathlib.Path(tempfile.mkdtemp())
agent.check_ollama = lambda m: True
agent._resolve_startup_model = lambda: "fake:model"
agent._init_mcp = lambda: None
agent.get_num_ctx = lambda m: 4096
agent.ollama_runner_rss_gb = lambda: None

class Msg:
    def __init__(s, content="", tool_calls=None, thinking=""):
        s.content=content; s.tool_calls=tool_calls; s.thinking=thinking
class Resp:
    def __init__(s,m): s.message=m

def run_main(argv, responses):
    it = iter(responses)
    agent.ollama.chat = lambda **kw: Resp(next(it))
    old = sys.argv
    sys.argv = ["agent.py"] + argv
    buf = io.StringIO()
    code = None
    try:
        with contextlib.redirect_stdout(buf):
            agent.main()
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv = old
    return code, buf.getvalue()

# success: plain answer → exit 0, answer on stdout
code, out = run_main(["--run", "say hi", str(proj)], [Msg(content="Hello, done.")])
assert code == 0, code
assert "Hello, done." in out, repr(out)

# failure: fallback answer → exit 1
code2, out2 = run_main(["--run", "do x", str(proj)], [Msg(content="⚠️ Stopped after 25 tool-call rounds")])
assert code2 == 1, code2

# recipe: two steps → two answers, exit 0
code3, out3 = run_main(["--recipe", str(rp), str(proj)],
                       [Msg(content="step one done"), Msg(content="step two done")])
assert code3 == 0, code3
assert "step one done" in out3 and "step two done" in out3, repr(out3)

print("B9 ALL PASS")
