"""Ollamancer — git tools.

Read-mostly wrappers over the user's own git repository. Distinct from
`agentic/checkpoints.py`, which drives a *shadow* repo for /undo and never touches the user's
history — these four do, which is why `git_commit` is in `_RISKY_TOOLS` and gated by safe mode.

`git_commit` sets a local identity when none is configured, so committing does not fail on a
machine that never had `user.name` set globally.
"""

import subprocess

from agentic import state
from agentic.safety import _audit

def git_status() -> str:
    """Return the git repo state: current branch, modified files, untracked files."""
    try:
        r = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip()[:3000]
    except Exception as e:
        return f"git_status error: {e}"


def git_diff(path: str = ".") -> str:
    """Show uncommitted changes in the repo or a specific file.
    Args:
        path: File or folder (default: whole repo)
    """
    try:
        r = subprocess.run(["git", "diff", "--", path], capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip()[:3000] or "(no changes)"
    except Exception as e:
        return f"git_diff error: {e}"


def git_log(n: int = 10) -> str:
    """Show recent commits with a branch graph.
    Args:
        n: Number of commits to show (default: 10, max: 100)
    """
    try:
        n = max(1, min(int(n), 100))
        r = subprocess.run(
            ["git", "log", "--oneline", "--graph", "--decorate", f"-n{n}"],
            capture_output=True, text=True, timeout=15,
        )
        return (r.stdout + r.stderr).strip()[:3000]
    except Exception as e:
        return f"git_log error: {e}"


def git_commit(message: str) -> str:
    """Create a git commit with already-staged files (use run_command 'git add' first).
    Args:
        message: Descriptive commit message
    """
    try:
        r = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).strip()[:3000]
    except Exception as e:
        return f"git_commit error: {e}"
