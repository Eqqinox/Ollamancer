---
name: new-python-project
description: Scaffold a modern Python project from scratch — structure, virtualenv, pyproject, git, and a first passing test. Use when the user asks to start/create/bootstrap a new Python project or package.
license: MIT
---

# New Python project

Set up a clean, modern layout that's ready to run and test. Confirm the project name first.

## Steps

1. **Confirm basics** with the user: project/package name (import-safe: lowercase,
   underscores), and whether it's an app or an installable library.
2. **Create the structure** with `create_directory` + `write_file`:
   ```
   <name>/
   ├── pyproject.toml
   ├── README.md
   ├── .gitignore            # include .venv/, __pycache__/, *.pyc, .pytest_cache/
   ├── src/<pkg>/__init__.py
   └── tests/test_basic.py
   ```
   Use a `src/` layout. Write files > ~80 lines in chunks (`append_file`).
3. **pyproject.toml** — minimal, modern: `[build-system]` (hatchling or setuptools),
   `[project]` with name/version/description/requires-python, and an optional `[project.scripts]`
   entry point for an app.
4. **A first real test** in `tests/test_basic.py` that imports the package and asserts something
   trivially true — so the suite is green from commit one.
5. **Environment + git** (confirm before running installs):
   - `run_command`: `python3 -m venv .venv` then `.venv/bin/pip install -e ".[dev]"` (or just
     `pytest`).
   - `run_command`: `git init && git add -A && git commit -m "chore: initial project scaffold"`.
6. **Verify** by running the test suite (`run_tests`/`run_command .venv/bin/pytest`) and showing
   it pass. Report the exact commands to run it and where to add code next.

## Notes

- Don't invent dependencies the user didn't ask for — keep the scaffold minimal.
- On this Mac, prefer a project-local `.venv` (PEP 668 blocks system pip installs).
