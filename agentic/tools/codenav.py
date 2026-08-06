"""Agentic_1A — code navigation.

Three ways to find things, deliberately distinct because they fail differently:

  * `search_in_files` — literal/regex grep. Fast, exact, no understanding of code.
  * `find_files` — locate files by name or glob.
  * `find_references` — understands code. For Python it is a real `ast.parse` walk, so it
    separates definitions from uses (FunctionDef/ClassDef vs a Name load), catches attribute
    access and imports, and *intrinsically* ignores mentions inside comments and docstrings,
    because the AST does not contain them. For other languages it degrades to a regex
    heuristic over common definition patterns and says so by tagging results `def?`.

The AST path is what makes this worth having over grep: before a rename you want everything
that would actually break, not every line that happens to contain the word.

Semantic search — finding code by *meaning* rather than by name — is the fourth pillar and
lives in `rag.py`.
"""

import ast
import os
import re
import subprocess
from pathlib import Path

from agentic import config, state
from agentic.safety import _audit, _check_file_path

def search_in_files(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Search recursively for a text or regex pattern across files in a directory (like grep -rEn), returning
    matching file paths and line numbers. Use this to locate where something is defined or used before
    reading or editing it — for example finding which file contains a function before calling edit_file
    on it. Use find_files instead if you're looking for files by name rather than by content. There are
    exactly three arguments, named pattern, path, and file_type — there is no "directory_path" or
    "file_name" parameter; the search root is always named path and defaults to the whole project.
    pattern uses extended regular expression (ERE) syntax — the same style as Python's re module or grep -E:
    unescaped |, +, ?, (...) groups, and {n,m} all work as metacharacters, not literal characters. To search
    for one of those characters literally, escape it with a backslash (e.g. "config\\.json").
    Example call: search_in_files(pattern="def add|def subtract", path=".", file_type=".py")
    Args:
        pattern: Text or extended-regex (ERE) pattern to search for
        path: Directory to search recursively, relative or absolute (defaults to the current project root)
        file_type: Optional extension filter such as .py, .js, or .md; leave empty to search all file types
    """
    try:
        cmd = ["grep", "-rEn", "--color=never", "-I",
               "--exclude-dir=.git", "--exclude-dir=.venv", "--exclude-dir=node_modules",
               "--exclude-dir=__pycache__", "--exclude-dir=.next", "--exclude-dir=dist"]
        if file_type:
            cmd += ["--include", f"*{file_type}"]
        cmd += [pattern, path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        output = result.stdout.strip()
        if not output:
            return f"No occurrences of '{pattern}'."
        lines = output.split("\n")
        total = len(lines)
        suffix = f"\n... ({total-50} more results)" if total > 50 else ""
        return f"{total} occurrence(s):\n" + "\n".join(lines[:50]) + suffix
    except Exception as e:
        return f"search_in_files error: {e}"


def find_files(pattern: str, path: str = ".") -> str:
    """Find files by name or glob pattern within the project.
    Args:
        pattern: Filename pattern, e.g. *.py, *controller*, README.*
        path: Search directory (default: current project)
    """
    try:
        result = subprocess.run(
            ["find", path, "-name", pattern,
             "-not", "-path", "*/.git/*", "-not", "-path", "*/.venv/*",
             "-not", "-path", "*/node_modules/*", "-not", "-path", "*/__pycache__/*"],
            capture_output=True, text=True, timeout=15,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        if not files:
            return f"No file matching '{pattern}'."
        return f"{len(files)} file(s):\n" + "\n".join(files[:50])
    except Exception as e:
        return f"find_files error: {e}"


_REF_DEF_KINDS    = {"def", "class", "assign", "import", "param", "def?"}


def _iter_source_files(root: Path):
    count = 0
    for p in root.rglob("*"):
        if p.is_dir() or p.suffix.lower() not in config._REF_SOURCE_EXTS:
            continue
        if any(part in config._REF_EXCLUDE_DIRS for part in p.parts):
            continue
        yield p
        count += 1
        if count >= 500:  # perf guardrail on very large repos
            return


def _ast_symbol_hits(path: Path, symbol: str) -> list[tuple[int, str]]:
    """Real (precise) AST analysis for Python files."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except Exception:
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            hits.append((node.lineno, "def"))
        elif isinstance(node, ast.ClassDef) and node.name == symbol:
            hits.append((node.lineno, "class"))
        elif isinstance(node, ast.Name) and node.id == symbol:
            hits.append((node.lineno, "assign" if isinstance(node.ctx, ast.Store) else "use"))
        elif isinstance(node, ast.Attribute) and node.attr == symbol:
            hits.append((node.lineno, "attr"))
        elif isinstance(node, ast.arg) and node.arg == symbol:
            hits.append((node.lineno, "param"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if (alias.asname or alias.name) == symbol or alias.name == symbol:
                    hits.append((node.lineno, "import"))
    return hits


_REF_DEF_PATTERN_TEMPLATE = (
    r'\b(function|const|let|var|class|interface|type|fn|def)\s+{s}\b'
    r'|\b{s}\s*[:=]\s*(async\s*)?\('
    r'|\b{s}\s*\([^)]*\)\s*\{{'
)


def find_references(symbol: str, path: str = ".") -> str:
    """Find where a function/class/variable is DEFINED versus just USED across the
    project — more precise than search_in_files (plain grep), which can't tell a real
    definition from a mention inside a comment or string. For .py files this parses a
    real AST (exact); for other languages it uses pattern heuristics on definition
    syntax (best-effort, may miss or misclassify some). Use this before renaming or
    removing something, to see every place that would break.
    Args:
        symbol: The exact identifier name to look for (plain name, not a dotted path)
        path: Directory to search (default: current project)
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', symbol):
        return "symbol must be a plain identifier (letters/digits/underscore, not starting with a digit)."

    root = Path(path).expanduser().resolve()
    if not root.exists():
        return f"Path not found: {root}"

    word_pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
    def_pattern = re.compile(_REF_DEF_PATTERN_TEMPLATE.format(s=re.escape(symbol)))

    results = []  # (file, lineno, kind, line_text)
    for f in _iter_source_files(root):
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        if f.suffix.lower() == ".py":
            for lineno, kind in _ast_symbol_hits(f, symbol):
                text = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
                results.append((f, lineno, kind, text))
        else:
            for i, line in enumerate(lines, start=1):
                if word_pattern.search(line):
                    kind = "def?" if def_pattern.search(line) else "use"
                    results.append((f, i, kind, line.strip()))

    if not results:
        return f"No reference to '{symbol}' found under {root}."

    defs = [r for r in results if r[2] in _REF_DEF_KINDS]
    uses = [r for r in results if r[2] not in _REF_DEF_KINDS]
    n_files = len({r[0] for r in results})

    out = [f"{len(results)} reference(s) to '{symbol}' in {n_files} file(s):"]
    if defs:
        out.append(f"\nDefinitions/bindings ({len(defs)}):")
        for f, lineno, kind, text in defs[:30]:
            out.append(f"  {f.relative_to(root)}:{lineno} [{kind}] {text}")
    if uses:
        out.append(f"\nUsages ({len(uses)}):")
        for f, lineno, kind, text in uses[:50]:
            out.append(f"  {f.relative_to(root)}:{lineno} [{kind}] {text}")
        if len(uses) > 50:
            out.append(f"  ... ({len(uses) - 50} more usages not shown)")
    return "\n".join(out)
