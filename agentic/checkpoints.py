"""Agentic_1A — git checkpoints (the engine behind /undo).

A **shadow** git repository lives in `.agentic/checkpoints.git`, using the project folder as
its work tree. It is completely independent of whatever git the user has: dedicated GIT_DIR
and GIT_WORK_TREE, so it never touches their index, refs, commits, or HEAD. Two consequences
that matter:

  * it behaves identically in a git project and a non-git one (the approach Aider uses), and
  * `/undo` can never damage the user's own history, because it is not writing to it.

One checkpoint = one commit of the project state **before the first write of a turn**, so
`/undo last` reverts a whole turn rather than a single edit. The bookkeeping (`_CHECKPOINTS`,
`_checkpoint_turn`, `_checkpoint_made_this_turn`) lives in `agentic/state.py`.

Everything degrades quietly: if git is unavailable, or the shadow repo cannot be created,
`_checkpoints_available()` returns False and the agent falls back to the older in-memory
snapshot undo. Checkpoints are also disabled entirely under `--private`, where
`state._CHECKPOINT_GITDIR` is never set.
"""

import os
import shutil
import subprocess
from datetime import datetime

from agentic import state
from agentic.safety import _audit

_CHECKPOINT_EXCLUDES = (
    ".agentic/\n.git/\n.venv/\nvenv/\nenv/\nnode_modules/\n__pycache__/\n*.pyc\n"
    ".next/\ndist/\nbuild/\n.cache/\n.ruff_cache/\n.pytest_cache/\n.mypy_cache/\n"
    ".DS_Store\n.serena/\n"
)


def _git_available() -> bool:
    return shutil.which("git") is not None


def _checkpoints_available() -> bool:
    return state._CHECKPOINT_GITDIR is not None and state._CHECKPOINT_GITDIR.exists() and _git_available()


def _git_ckpt(*args, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a git command against the shadow checkpoint repo (dedicated GIT_DIR + the
    project root as work-tree, so it never touches the user's own git)."""
    env = {**os.environ,
           "GIT_DIR": str(state._CHECKPOINT_GITDIR),
           "GIT_WORK_TREE": str(state.PROJECT_ROOT)}
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=timeout, env=env)


def _init_checkpoints() -> None:
    """Create/prepare the shadow checkpoint repo. Silent no-op if git is missing —
    the agent then falls back to the legacy in-memory /undo (RAM snapshots)."""
    if not _git_available() or state.PROJECT_ROOT is None:
        state._CHECKPOINT_GITDIR = None
        return
    gitdir = state.PROJECT_ROOT / ".agentic" / "checkpoints.git"
    state._CHECKPOINT_GITDIR = gitdir
    try:
        if not gitdir.exists():
            r = _git_ckpt("init", timeout=30)
            if r.returncode != 0:
                state._CHECKPOINT_GITDIR = None
                return
            # Local identity (the commit fails if a global user.name/email is missing).
            _git_ckpt("config", "user.email", "agentic@local")
            _git_ckpt("config", "user.name", "Agentic_1A")
            _git_ckpt("config", "commit.gpgsign", "false")
        (gitdir / "info").mkdir(parents=True, exist_ok=True)
        (gitdir / "info" / "exclude").write_text(_CHECKPOINT_EXCLUDES, encoding="utf-8")
    except Exception:
        state._CHECKPOINT_GITDIR = None


def _make_turn_checkpoint(label: str) -> None:
    """Commit the current (pre-write) project state to the shadow repo, at most once per
    user turn (before that turn's first write). Guarded by _checkpoint_made_this_turn."""
    if state._checkpoint_made_this_turn or not _checkpoints_available():
        return
    try:
        _git_ckpt("add", "-A")
        c = _git_ckpt("commit", "-m", label, "--allow-empty", "--quiet")
        if c.returncode != 0:
            return
        sha = _git_ckpt("rev-parse", "HEAD").stdout.strip()
        if not sha:
            return
        state._CHECKPOINTS.append({
            "sha": sha, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "turn": state._checkpoint_turn, "label": label,
        })
        state._checkpoint_made_this_turn = True
        _audit("CHECKPOINT", {"turn": state._checkpoint_turn, "sha": sha[:10], "label": label})
    except Exception:
        pass


def _restore_checkpoint(sha: str) -> bool:
    """Restore the project work-tree to a checkpoint: hard-reset tracked files to the
    commit and remove files created since (untracked, honoring info/exclude — so .venv/
    node_modules/.agentic are never touched). Returns True on success."""
    if not _checkpoints_available():
        return False
    try:
        r1 = _git_ckpt("reset", "--hard", sha)
        _git_ckpt("clean", "-fd")   # removes untracked files created since (honours info/exclude)
        return r1.returncode == 0
    except Exception:
        return False
