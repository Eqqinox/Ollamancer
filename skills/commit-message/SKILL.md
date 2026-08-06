---
name: commit-message
description: Write a clean, conventional git commit message from the current staged/unstaged changes. Use when the user asks to commit, or to write/generate a commit message.
license: MIT
---

# Commit message

A reusable workflow for producing a good git commit message from the actual diff —
not a guess.

## Steps

1. Run `git_status` to see what changed, then `git_diff` to read the real diff.
   Never write a message without looking at the actual changes.
2. Summarize the change in one **imperative** subject line, ≤ 50 characters, using a
   conventional prefix when it fits:
   - `feat:` a new capability · `fix:` a bug fix · `refactor:` no behavior change ·
     `docs:` documentation · `test:` tests · `chore:` tooling/deps.
3. If the change is non-trivial, add a blank line then a short body (wrap ~72 cols)
   explaining **why**, not just what — the diff already shows the what.
4. Do **not** invent changes that aren't in the diff. If the diff is empty, say so and
   stop (there's nothing to commit).
5. Show the proposed message to the user first. Only run `git_commit` if they confirm,
   or if they already asked you to commit directly.

## Example output

```
fix: guard against empty search results before rendering

SearXNG can return non-empty snippets that are actually category pages.
Treat all-thin excerpts as "no results" so the model doesn't fabricate.
```

## Notes

- Respect any commit convention the project already uses (check recent `git_log`).
- Keep it factual and specific; a reader should understand the change from the subject
  line alone.
