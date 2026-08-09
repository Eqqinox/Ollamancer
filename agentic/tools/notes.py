"""Ollamancer — the clock, the task checklist, and persistent memory.

Three tools at three different lifetimes.

  * `get_datetime` — the model is forbidden from guessing today's date (it once hallucinated
    "December 2025" and built every search query around it), so this exists to be called
    before any "today"/"current" lookup.
  * `todo_write`/`todo_read` — a free-text checklist for the current multi-step task. In
    memory, dies with the session; that is intended.
  * `memory_write`/`memory_read` — durable facts in `.agentic/memory.md`, reloaded into the
    system prompt on every future start. Writing REPLACES the file rather than appending, and
    the content is re-injected into every model call, hence the soft size warning. A no-op
    under `--private`.
"""

from datetime import datetime
from pathlib import Path

from agentic import config, state
from agentic.safety import _audit

def get_datetime() -> str:
    """Return the current date and time on the local machine."""
    return datetime.now().strftime("It is %A, %B %d, %Y — %H:%M:%S")


def todo_write(checklist: str) -> str:
    """Create or update the task checklist for the current multi-step task (full overwrite,
    replaces whatever was there before). Use this for any task with more than ~3 steps, so
    you track progress instead of re-deciding the plan from scratch every turn.
    Write it as a plain markdown checklist, one item per line, for example:
    - [x] Explore the codebase
    - [ ] Implement the change
    - [ ] Verify with lint_file / run_tests
    Call it again with the same list but updated [x]/[ ] marks as you complete steps.
    Args:
        checklist: The full checklist text, replacing the previous one entirely
    """
    state._todo = checklist.strip()
    return "Checklist updated." if state._todo else "Checklist cleared."


def todo_read() -> str:
    """Read the current task checklist for this session. Empty if none has been set yet."""
    return state._todo or "(no checklist set)"


def _memory_path() -> Path | None:
    return state._SNAPSHOT_DIR.parent / "memory.md" if state._SNAPSHOT_DIR else None


def _save_memory() -> None:
    if state.PRIVATE_MODE:
        return  # private session: memory is never written to disk
    path = _memory_path()
    if path:
        try:
            path.write_text(state._memory, encoding="utf-8")
        except Exception:
            pass


def _load_memory() -> str:
    path = _memory_path()
    if path and path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def memory_write(content: str) -> str:
    """Save durable project/user knowledge that should persist across sessions (full
    overwrite, replaces whatever was saved before) — unlike todo_write, this survives
    restarting the agent and is re-read into every future conversation automatically.
    Use it for things worth remembering long-term: user preferences, project conventions,
    decisions made and why, recurring gotchas. Do NOT dump the whole conversation or task
    checklist here — keep it short and curated, it gets added to every future system
    prompt. If asked to remember something, save it here; if asked to forget, remove it
    from this text and call memory_write again with the updated content.
    Args:
        content: The full memory text, replacing the previous one entirely
    """
    state._memory = content.strip()
    _save_memory()
    if len(state._memory) > config.MEMORY_SOFT_LIMIT:
        return f"Memory updated ({len(state._memory)} chars) — getting long, consider trimming to keep only what's still relevant."
    return "Memory updated." if state._memory else "Memory cleared."


def memory_read() -> str:
    """Read the current persistent memory (project/user knowledge saved across sessions)."""
    return state._memory or "(no memory saved yet)"
