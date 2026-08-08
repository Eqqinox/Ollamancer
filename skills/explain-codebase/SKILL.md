---
name: explain-codebase
description: Explore an unfamiliar project and explain its architecture, structure, key modules, entry points, and how data flows. Use when the user asks to understand, explain, onboard to, or "give me a tour of" a codebase.
license: MIT
---

# Explain a codebase

Build an accurate mental map from the real code, not assumptions. Cite files as you go.

## Steps

1. **Survey the layout.** `list_directory` the root; read `README`, `pyproject.toml`/
 `package.json`/`go.mod`, and any docs. Note the language(s), framework, and how it's run.
2. **Find the entry points.** Look for `main`, `__main__`, `if __name__ == "__main__"`, CLI
 definitions, server `app`/`routes`, or `bin`/`cmd`, `search_in_files` for them.
3. **Map the key modules.** Identify the few files that carry the core logic (biggest, most
 imported). Use `search_semantic` for concept-based questions ("where is auth handled?") and
 `find_references` to see how a central function/class is used across the project.
4. **Trace one real flow end-to-end.** Pick the main use case and follow it from entry point
 through the modules that handle it, `read_file_lines` the relevant parts. This reveals the
 actual architecture better than reading everything.
5. **Summarize** for the user: a short "what it is", a component map (module responsibility),
 the main flow you traced, and where to start for a typical change. Point to concrete files
 (`path:line`). Flag anything surprising or fragile you noticed.

## Notes

- Don't invent components you didn't actually see, if something is unclear, say so and point to
 where you'd look next.
- Keep it proportional: a tour, not a line-by-line dump.
