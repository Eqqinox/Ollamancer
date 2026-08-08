---
name: debug-error
description: Systematically debug a specific error, exception, traceback, or crash, reproduce it, localize the cause, fix it, and verify. Use when the user pastes an error/traceback or says "this crashes / throws / doesn't work".
license: MIT
---

# Debug an error

Reproduce first, guess never. The goal is to find the *real* cause, not to patch symptoms.

## Steps

1. **Read the error exactly.** Identify the exception type, message, and the *deepest* frame in
 the traceback that is in the project's own code (not a library), that's usually where to
 look first.
2. **Reproduce it** with the smallest possible run: `run_command` the failing script/command, or
 use `python_repl` to call the offending function with representative input. If you can't
 reproduce it, say so and ask for the exact steps/inputs, don't invent a fix blind.
3. **Localize.** Open the failing code (`read_file_lines`), and use `find_references` /
 `search_in_files` to see how the failing value/function is produced and used. Form a concrete
 hypothesis: "X is None here because Y never sets it."
4. **Confirm the hypothesis** before editing, add a quick `print`/check via `python_repl` or a
 temporary `run_command`, or trace the data flow by reading. Only then edit.
5. **Fix** with `edit_file` (smallest correct change), then **verify by re-running** the exact
 reproduction from step 2. The same input that crashed must now succeed.
6. **Check for siblings.** If the bug was a missing key/guard/edge case, search for the same
 pattern elsewhere (`search_in_files`), the same mistake is often repeated.

## Notes

- If you look up the error online, use `search_web` for the specific message; cite what you used.
- Don't declare it "fixed" until you've re-run the reproduction and seen it pass.
