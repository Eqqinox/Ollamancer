"""Ollamancer — skills (reusable SKILL.md workflows).

A skill is a folder containing a `SKILL.md`: YAML frontmatter with a `name` and a
`description`, then free-form instructions. The format is the open standard shared with
Claude Code, Cursor and Codex, so skills are portable in both directions.

**Progressive disclosure, three tiers**, which is what keeps the cost near zero:

  1. *Discovery* — at startup only each skill's name and description go into the system
     prompt (`_skills_prompt_block`). A dozen skills cost a few hundred tokens.
  2. *Loading* — when a task matches, the model calls `load_skill` itself (or the user runs
     `/skill <name>`), and only then are the full instructions read.
  3. *Execution* — the instructions may point at other files in the skill folder, which the
     agent reads on demand with its ordinary file tools.

**One documented exception to tier 2**: `web-answer-format` is loaded code-side by
`_maybe_autoload_web_format` when the user's message is obviously a web question, because tier 2
assumes the model *chooses* to load, and on a small local model that assumption is the weak
link (same reasoning, and the same benchmark evidence, as the forced search in `tools/web.py`).
Every other skill still waits to be asked for.

Three sources, most specific wins on a name clash: bundled (`<repo>/skills/`), user-global
(`~/.agentic_1a_skills/`), and per-project (`<project>/.agentic/skills/`).

The frontmatter parser is deliberately minimal — `key: value` lines only, no YAML dependency
— and tolerates a missing frontmatter block rather than failing the whole discovery pass.
"""

import difflib
import re
from pathlib import Path

from agentic import config, state
from agentic.safety import _audit

def _parse_skill_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a SKILL.md's minimal YAML frontmatter (--- ... ---) with no dependency: plain
    `key: value` lines. Returns (metadata, body). Tolerates a missing frontmatter block."""
    meta: dict = {}
    body = text
    if text.lstrip().startswith("---"):
        rest = text.lstrip()[3:]
        end = rest.find("\n---")
        if end != -1:
            front = rest[:end]
            body = rest[end + 4:].lstrip("\n")
            for line in front.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition(":")
                    meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, body


def _skill_dirs() -> list[Path]:
    """Root directories to search for skills, least to most specific (most specific wins
    on a name clash)."""
    dirs = [config.bundled_skills_dir(), config.SKILLS_GLOBAL_DIR]
    if state.PROJECT_ROOT is not None:
        dirs.append(state.PROJECT_ROOT / ".agentic" / "skills")
    return dirs


def _discover_skills() -> dict:
    """Scan the sources and return {name: {"description","body_path","dir","source"}}. One
    skill = one subfolder containing a SKILL.md (frontmatter name+description). The frontmatter
    name wins, otherwise the folder name. More specific sources override the others."""
    found: dict = {}
    for root in _skill_dirs():
        try:
            if not root.exists():
                continue
            for sub in sorted(root.iterdir()):
                skill_md = sub / "SKILL.md"
                if not (sub.is_dir() and skill_md.exists()):
                    continue
                try:
                    text = skill_md.read_text(encoding="utf-8")
                except Exception:
                    continue
                meta, _ = _parse_skill_frontmatter(text)
                name = (meta.get("name") or sub.name).strip().lower()
                desc = meta.get("description", "").strip() or "(no description provided)"
                found[name] = {"description": desc, "body_path": skill_md,
                               "dir": sub, "source": str(root)}
        except Exception:
            continue
    return found


def _skills_prompt_block() -> str:
    """Tier 1 (discovery): a compact name+description block to inject into the system prompt.
    Empty when there are no skills — zero cost when none exist."""
    skills = _discover_skills()
    if not skills:
        return ""
    lines = ["\n\nAvailable skills (reusable workflows). When a task matches one, call load_skill(name) "
             "to load its full instructions, then follow them. The user can also load one with /skill <name>."]
    for name, info in sorted(skills.items()):
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)


def load_skill(name: str) -> str:
    """Load the full instructions of a named skill (a reusable workflow) into context, then
    follow them. Skills are listed in your system prompt with a one-line description each; call
    this when a task matches one of them. The returned text may reference other files in the
    skill's folder — read them with read_file as needed. Use the exact skill name.
    Args:
        name: The skill name to load (as shown in the available-skills list)
    """
    skills = _discover_skills()
    key = (name or "").strip().lower()
    info = skills.get(key)
    if info is None:
        # tolerance: approximate match on the name
        match = difflib.get_close_matches(key, list(skills.keys()), n=1, cutoff=0.6)
        if match:
            info = skills[match[0]]
            key = match[0]
    if info is None:
        avail = ", ".join(sorted(skills.keys())) or "(none)"
        return f"No skill named '{name}'. Available skills: {avail}."
    try:
        text = info["body_path"].read_text(encoding="utf-8")
    except Exception as e:
        return f"Could not read skill '{key}': {e}"
    _, body = _parse_skill_frontmatter(text)
    _audit("LOAD_SKILL", {"name": key, "source": info["source"]})
    return (f"[Skill loaded: {key}] — reference files for this skill live in {info['dir']} "
            f"(read them with read_file if the instructions point to them).\n\n{body}")


# ── Auto-load: web-answer-format ─────────────────────────────────────────────
# Same reasoning as `_maybe_force_search` in tools/web.py: tier-2 loading assumes the model
# *chooses* to call load_skill, and the benchmarks show a small local model mostly doesn't —
# it answers straight from the first search result, in one flat undated list. So for the one
# case where the output shape matters most (a question that will obviously be answered from
# the web), the load happens code-side, before the model gets its turn.
#
# Deliberately narrow: recency/news wording, an explicit "look it up" verb, or the forced-search
# prefix. An ordinary coding question is not caught, and shouldn't be — these are chat-answer
# formatting rules, not general ones. `latest` is the one loose term, it also fires on "upgrade
# to the latest pandas"; kept anyway, because it is the recency word users actually type, and
# the cost of a false positive is ~1.3k tokens (2% of the default 64K window), not a wrong
# answer.
_WEB_FORMAT_SKILL = "web-answer-format"
_WEB_FORMAT_INTENT_RE = re.compile(
    # Recency and "go look it up" wording.
    r'\b(news|breaking|headlines?|latest|today|todays|current events|happening now|'
    r'this (week|month)|search (the )?(web|online|internet)|look (it |them )?up|google it|'
    r'actualit[ée]s?|nouvelles|derni[èe]res?|aujourd.hui|cherche sur (le web|internet))\b'
    # Open questions that want an answer from the world rather than from this repo. "How do I
    # build a web scraper" ran zero searches and answered from memory, unsourced, which is the
    # all-purpose half of the job — the trigger only covered the news half.
    r'|\bwhat (are|is) the best\b|\bbest (way|tool|library|framework|model|practice)s?\b'
    r'|\bhow (do|can) (i|you|we) (build|make|set up|install|choose|start)\b'
    r'|\b(compare|vs\.?|versus)\b|\bwhich (one |tool |library |model )?should i\b'
    r'|^\s*search\b',
    re.IGNORECASE,
)


def _maybe_autoload_web_format(user_input: str, messages: list) -> None:
    """If the user's message clearly calls for a web answer, inject the web-answer-format skill
    as an already-completed `load_skill` call, before the model's turn. Skipped when the skill
    is already in recent context (it stays there, no point paying for it twice)."""
    if not _WEB_FORMAT_INTENT_RE.search(user_input or ""):
        return
    marker = f"[Skill loaded: {_WEB_FORMAT_SKILL}]"
    for msg in messages[-24:]:
        if marker in str(msg.get("content") or ""):
            return
    body = load_skill(_WEB_FORMAT_SKILL)
    if not body.startswith(f"[Skill loaded: {_WEB_FORMAT_SKILL}]"):
        return                                  # skill removed or unreadable: stay silent
    args = {"name": _WEB_FORMAT_SKILL}
    messages.append({
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "load_skill", "arguments": args}}],
    })
    messages.append({"role": "tool", "content": body})
