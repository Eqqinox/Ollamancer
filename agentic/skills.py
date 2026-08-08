"""Agentic_1A — skills (reusable SKILL.md workflows).

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

Three sources, most specific wins on a name clash: bundled (`<repo>/skills/`), user-global
(`~/.agentic_1a_skills/`), and per-project (`<project>/.agentic/skills/`).

The frontmatter parser is deliberately minimal — `key: value` lines only, no YAML dependency
— and tolerates a missing frontmatter block rather than failing the whole discovery pass.
"""

import difflib
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
