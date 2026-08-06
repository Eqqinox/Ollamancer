---
name: changelog-from-git
description: Generate a CHANGELOG or release notes from real git history. Use when the user asks for a changelog, release notes, or a summary of "what changed" since a tag/date.
license: MIT
---

# Changelog from git

Write release notes grounded in the actual commits — never invent changes.

## Steps

1. **Get the range.** Ask (or infer) the range: since the last tag (`git tag`), since a date, or
   since a commit. Default to "since the most recent tag" if unspecified.
2. **Read the real history** with `run_command`:
   - `git log --oneline --no-merges <range>` for the list,
   - `git log <range> --stat` if you need to see which files each commit touched.
   Use only what's actually there.
3. **Group commits by type** into sections: **Added / Changed / Fixed / Removed / Docs /
   Internal**. Use conventional-commit prefixes (`feat:`, `fix:`, …) as hints when present.
4. **Rewrite each entry** as a short, user-facing line (imperative, present tense) — describe the
   effect, not the commit hash. Drop pure-noise commits (typos, formatting) or fold them into
   "Internal".
5. **Write the file.** Prepend a new dated version section to `CHANGELOG.md` with `read_file` +
   `edit_file` (keep existing entries), or create it with `write_file` if absent. Follow
   "Keep a Changelog" style if the project already uses it.

## Example section

```
## [1.4.0] — 2026-08-05
### Added
- Streamed the final answer live instead of all at once.
### Fixed
- Context is now measured with the real token count, not an estimate.
```

## Notes

- If the range has no commits, say so and stop — there's nothing to release.
- Never attribute a change to a commit that isn't in the log.
