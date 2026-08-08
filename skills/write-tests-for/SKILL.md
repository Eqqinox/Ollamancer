---
name: write-tests-for
description: Write real unit tests for a given function, class, module, or file, covering the happy path, edge cases, and errors, and make sure they pass. Use when the user asks to write/add tests or improve test coverage for specific code.
license: MIT
---

# Write tests for

Tests that actually exercise behavior, not tautologies, not tests of the mock.

## Steps

1. **Read the target code** (`read_file`/`read_file_lines`) and understand what it's *supposed*
 to do: inputs, outputs, side effects, and the error conditions it should handle. Use
 `find_references` to see how it's really called.
2. **Detect the test framework** already in use (`pytest`, `unittest`, `jest`, `go test`, …) and
 match its style and file layout (`tests/`, `*_test.py`, `*.test.js`). Don't introduce a new
 framework without asking.
3. **Enumerate cases** before writing: the happy path; boundary/edge inputs (empty, zero,
 negative, very large, unicode); and each error/exception the code should raise. One clear
 assertion per behavior.
4. **Write the tests** with `write_file`/`append_file` (chunk long files). Use real, meaningful
 assertions on actual outputs, avoid `assert True`, avoid asserting only that a mock was
 called. Keep each test independent and named for what it checks.
5. **Run them** (`run_tests`/`run_command`) and make sure they **pass against the real code**.
 If a test fails, decide honestly: is the test wrong, or did it find a real bug? If it's a real
 bug, tell the user (optionally hand off to `debug-error`/`test-and-fix`).
6. **Report** what you covered and any behavior you deliberately left untested (and why).

## Notes

- Don't write tests that just restate the implementation, test the *contract*, so they'd catch a
 regression if someone changed the code.
- If the code has hidden dependencies (network, time, filesystem), isolate them minimally; note
 what you stubbed.
