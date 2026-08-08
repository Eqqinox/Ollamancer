"""Agentic_1A — the tool belt.

One module per domain: `web`, `files`, `codenav`, `rag`, `vcs`, `exec`, `vision`, `notes`,
plus `load_skill` from `agentic/skills.py`. Each exposes the tools the model can call and the
private helpers that serve only them.

This file is the **registry**, and the single place a new tool has to be declared. `TOOLS` is
the list handed to Ollama, which derives each tool's JSON schema from the function's name,
type hints and docstring — so the docstring is not documentation, it is the interface the
model reads when deciding what to call.

Two subsets carve up `TOOLS` and both fail dangerously if they drift:

  * `_RISKY_TOOLS` (in `agentic/safety.py`) — gated behind safe-mode approval. A risky tool
    missing from it silently skips the prompt.
  * `_READ_ONLY_TOOL_NAMES` — what the architect phase is allowed to touch. A write tool
    leaking in would let a "read-only" planning pass modify the project.

`tests/test_structure.py` freezes all three sets and cross-checks them, so a tool lost or
miscategorised during a refactor fails the build rather than going quiet.
"""

from agentic.skills import load_skill
from agentic.tools.codenav import find_files, find_references, search_in_files
from agentic.tools.exec import (
    check_process, kill_process, lint_file, list_processes, python_repl, run_background,
    run_command, run_tests)
from agentic.tools.files import (
    append_file, create_directory, edit_file, list_directory, read_file, read_file_lines,
    write_file)
from agentic.tools.notes import (
    get_datetime, memory_read, memory_write, todo_read, todo_write)
from agentic.tools.rag import search_semantic
from agentic.tools.vcs import git_commit, git_diff, git_log, git_status
from agentic.tools.vision import analyze_image
from agentic.tools.web import fetch_url, fetch_url_rendered, search_web, search_web_deep

TOOLS = [
    search_web, search_web_deep, fetch_url, fetch_url_rendered,
    read_file, read_file_lines, write_file, append_file, edit_file, create_directory, list_directory,
    search_in_files, find_files, find_references, search_semantic, load_skill,
    git_status, git_diff, git_log, git_commit,
    lint_file, run_tests, run_command, python_repl, get_datetime, analyze_image,
    todo_write, todo_read, memory_write, memory_read,
    run_background, check_process, kill_process, list_processes,
]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}

# Read-only tools the architect phase (B4) may use: navigation, search, reading and linting,
# but nothing that writes or executes code, no write/append/edit/create_directory/
# run_command/run_tests/run_background/kill/git_commit/memory_write, and no MCP tools, which
# are potentially destructive.
_READ_ONLY_TOOL_NAMES = {
    "search_web", "search_web_deep", "fetch_url", "fetch_url_rendered",
    "read_file", "read_file_lines", "list_directory", "search_in_files",
    "find_files", "find_references", "search_semantic", "load_skill", "git_status", "git_diff", "git_log",
    "lint_file", "get_datetime", "todo_write", "todo_read", "memory_read",
}


def _read_only_tools() -> list:
    return [fn for fn in TOOLS if fn.__name__ in _READ_ONLY_TOOL_NAMES]
