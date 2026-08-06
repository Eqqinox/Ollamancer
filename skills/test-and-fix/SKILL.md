---
name: test-and-fix
description: Run the project's test suite, diagnose the failures, fix the code, and re-run until green. Use when the user asks to make tests pass, fix failing tests, or "get the build green".
license: MIT
---

# Test and fix

A disciplined red→green loop. Fix the *code*, not the test, unless the test itself is wrong.

## Steps

1. **Find how tests run.** Check for `pytest`, `package.json` scripts (`npm test`), `go test`,
   `cargo test`, a Makefile, or a CI config. Use `list_directory` / `search_in_files`.
2. **Run the suite** with `run_tests` (or `run_command`). Read the *actual* failure output —
   don't guess. Note the first failing test and its real error, not a summary.
3. **Localize.** For each failure, open the relevant code with `read_file_lines` / find it with
   `search_in_files` / `find_references`. Understand *why* it fails before editing.
4. **Fix the smallest thing** that makes it correct, with `edit_file`. Prefer surgical edits.
   If a test encodes wrong behavior, say so explicitly and ask before changing the test.
5. **Re-run** the tests. Repeat 3–5. If the *same* failure recurs unchanged after an edit,
   stop guessing — re-read the code carefully or search the web for the exact error message.
6. **Stop when green** (or when a failure is a real environment/config issue you can't fix —
   then say exactly what's blocking). Never claim "tests pass" without actually running them
   and seeing them pass.

## Notes

- Run the whole suite at the end, not just the one test you were fixing — make sure you didn't
  break something else.
- If there are no tests, say so and offer to write some rather than pretending they passed.
