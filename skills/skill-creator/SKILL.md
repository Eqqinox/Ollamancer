---
name: skill-creator
description: Help the user author a new reusable skill (a SKILL.md workflow) for this agent. Use when the user wants to create, write, design, or scaffold a new skill, or asks "make a skill for X".
license: Apache-2.0
---

# Skill creator

Guide the user through writing a good, reusable `SKILL.md`. Adapted for this agent from
Anthropic's open `skill-creator` (anthropics/skills, Apache-2.0). The most important part of
a skill is the **description**, it's what makes the model pick the skill at the right time.

## Steps

1. **Capture the intent.** Ask (or infer) what repeatable task this skill should handle, and
 *when* it should trigger. One skill = one clear job. If the user's idea is broad, split it.

2. **Choose the name.** Lowercase letters, numbers and hyphens only, ≤ 64 characters, matching
 the task (e.g. `security-review`, `changelog-from-git`).

3. **Write a sharp description** (≤ 1024 chars). State *what it does* AND *when to use it*, in
 words a user would actually say. This drives routing, vague descriptions never trigger.
 - Good: "Audit the current diff for real security issues. Use when the user asks for a
 security review or to check code for vulnerabilities."
 - Bad: "Security stuff."

4. **Write the body** as concrete markdown, referencing THIS agent's real tools:
 - Reading/searching: `read_file`, `read_file_lines`, `search_in_files`, `find_references`,
 `search_semantic`, `list_directory`, `git_diff`/`git_status`/`git_log`.
 - Writing/running: `write_file`, `append_file` (for files > ~80 lines, write in chunks),
 `edit_file`, `run_command`, `python_repl`, `run_tests`, `lint_file`.
 - Structure it as: `## Overview` (one line), `## Steps` (numbered, concrete), `## Example`,
 and `## Notes` (gotchas). Keep the body focused (a few hundred lines max); put long
 reference material in separate files in the same folder and tell the model to `read_file`
 them only when needed (progressive disclosure).

5. **Save it.** Create the folder + file with `write_file`:
 - Global (all projects): `~/.agentic_1a_skills/<name>/SKILL.md`
 - This project only: `<project>/.agentic/skills/<name>/SKILL.md`
 Ask the user which scope they want.

6. **Verify.** Tell the user to run `/skills`, the new skill should appear with its
 description. If it doesn't, check that the frontmatter has both `name` and `description`
 between `---` lines.

## Example

For "make a skill that writes release notes from git history", you'd create
`~/.agentic_1a_skills/release-notes/SKILL.md` with a description like *"Generate release
notes from recent git commits. Use when the user asks for release notes or a changelog"*, and
a body that says: run `git_log`, group commits by type, write `RELEASE_NOTES.md` with
`write_file`, never invent commits that aren't in the log.

## Notes

- Never write instructions that exfiltrate data or run destructive commands, a skill's text
 is followed by the agent, which can act on this machine.
- Keep one behavior per skill; compose several small skills rather than one giant one.
