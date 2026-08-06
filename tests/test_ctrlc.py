import sys, tempfile, pathlib, io, contextlib
import agent

# Patch the heavy startup bits so main() runs without a real model/MCP.
agent.check_ollama = lambda m: True
agent._resolve_startup_model = lambda: "fake:model"
agent._init_mcp = lambda: None
agent.get_num_ctx = lambda m: 4096

def run_main_with_inputs(items):
    """Drive main()'s input loop with a scripted _prompt. Items may be strings (returned) or
    exception classes (raised). Returns the list of items actually consumed."""
    it = iter(items)
    consumed = []
    def scripted(label):
        x = next(it)
        consumed.append(x)
        if isinstance(x, type) and issubclass(x, BaseException):
            raise x()
        return x
    agent._prompt = scripted
    proj = tempfile.mkdtemp()
    old_argv = sys.argv
    sys.argv = ["agent.py", proj]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            agent.main()
    finally:
        sys.argv = old_argv
    return consumed, buf.getvalue()

# 1. Ctrl+C at the prompt does NOT quit — it cancels the line and re-prompts.
#    If it wrongly quit on Ctrl+C, the second input ("/exit") would never be consumed.
consumed, out = run_main_with_inputs([KeyboardInterrupt, "/exit"])
assert consumed == [KeyboardInterrupt, "/exit"], consumed  # both consumed → Ctrl+C continued
assert "input cleared" in out or "Ctrl+C" in out, "expected the Ctrl+C hint"

# 2. Ctrl+C multiple times still doesn't quit; only /exit does.
consumed, out = run_main_with_inputs([KeyboardInterrupt, KeyboardInterrupt, "/exit"])
assert consumed == [KeyboardInterrupt, KeyboardInterrupt, "/exit"], consumed

# 3. Ctrl+D (EOFError) at the prompt DOES quit (only one input consumed → it broke out).
consumed, out = run_main_with_inputs([EOFError, "/exit"])
assert consumed == [EOFError], consumed  # exited on Ctrl+D, never reached "/exit"

# 4. /exit quits normally.
consumed, out = run_main_with_inputs(["/exit"])
assert consumed == ["/exit"], consumed

print("CTRL+C-AT-PROMPT ALL PASS")
