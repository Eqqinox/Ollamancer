import sys, tempfile, pathlib, io, contextlib
import agent
from agentic import config
from agentic import ui
from agentic import models
from agentic import mcp_client

# This test drives main() all the way to its exit path, and cli.py's exit handler calls
# readline.write_history_file(config.HISTORY_FILE). Left alone that appends to the user's
# real ~/.agentic_1a_history, which is exactly the class of leak the suite's config guard
# exists to catch: it made the pytest run fail intermittently, only when the written
# content happened to differ from what was already on disk. Redirect before importing
# anything that reads it.
config.HISTORY_FILE = pathlib.Path(tempfile.mkdtemp()) / "history"

# Patch the heavy startup bits so main() runs without a real model/MCP.
models.check_ollama = lambda m: True
models._resolve_startup_model = lambda: "fake:model"
mcp_client._init_mcp = lambda: None
models.get_num_ctx = lambda m: 4096

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
    ui._prompt = scripted
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

# 1. Ctrl+C at the prompt does NOT quit, it cancels the line and re-prompts.
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
