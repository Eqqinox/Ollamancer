"""Agentic_1A — file reading, writing and editing.

The seven file tools, plus the hint machinery that makes them recoverable when a model gets
something slightly wrong. Those hints are not polish; each exists because a model burned a
session without it:

  * `_closest_path_hint` — on file-not-found, suggest the nearest real path (difflib). Added
    after a model repeatedly mistyped a long path and spent a whole session on "file not
    found" without ever correcting itself.
  * `_closest_snippet_hint` — on a failed `edit_file` match, show the closest real passage
    with its line number instead of "check your spelling". Two different models had looped on
    the same stale edit_file call for a long time.
  * `_python_syntax_warning` — after writing a .py file, `ast.parse` it and warn (never
    block) if invalid. Added after a model truncated its own output across eight full-file
    rewrites while `write_file` reported success every time.
  * `_large_write_note` — nudge toward chunked writes past ~80 lines: one huge tool-call
    argument is the most fragile operation in the stack (Ollama truncates the argument JSON
    mid-generation).
  * `_rename_consistency_warning` — flag a rename that left the old identifier behind.

Every path goes through `_check_file_path` first, which confines it to the project root.
"""

import ast
import difflib
import os
import re
from pathlib import Path

from agentic import config, state
from agentic.safety import _audit, _auto_snapshot, _check_file_path

def _closest_path_hint(path_str: str) -> str:
    """On a file-not-found, suggest the nearest real project path via difflib — same design
    as _closest_snippet_hint, which proved effective against the Ornith path-typo loop (it kept
    mistyping `mounirekknaci` for `mounirmeknaci` and burning whole sessions on "file not found").
    Matches first on the basename (right directory, misspelled name — the common case), then on
    the full relative path (wrong directory). Walks the project tree with the same exclude-dirs
    and a hard cap as the reference tools, and only runs on the error path so cost never matters."""
    root = state.PROJECT_ROOT or Path.cwd()
    try:
        wanted = Path(path_str).expanduser()
    except Exception:
        return ""
    names: dict[str, list[str]] = {}
    rels: list[str] = []
    count = 0
    try:
        for p in root.rglob("*"):
            if p.is_dir():
                continue
            if any(part in config._REF_EXCLUDE_DIRS for part in p.parts):
                continue
            try:
                rel = str(p.relative_to(root))
            except ValueError:
                rel = str(p)
            rels.append(rel)
            names.setdefault(p.name, []).append(rel)
            count += 1
            if count >= 2000:  # perf guardrail on very large repos
                break
    except Exception:
        return ""
    if not rels:
        return ""
    name_hit = difflib.get_close_matches(wanted.name, list(names.keys()), n=1, cutoff=0.6)
    if name_hit:
        matches = names[name_hit[0]]
        if len(matches) == 1:
            return f" Did you mean: {matches[0]}?"
        return f" Did you mean one of: {', '.join(matches[:3])}?"
    path_hit = difflib.get_close_matches(str(wanted), rels, n=1, cutoff=0.6)
    if path_hit:
        return f" Did you mean: {path_hit[0]}?"
    return ""


def read_file(path: str) -> str:
    """Read the full content of a file with line numbers.
    Args:
        path: Absolute or relative file path
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}{_closest_path_hint(path)}"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{i+1:4d} | {l}" for i, l in enumerate(lines))
        return f"[{path}] — {len(lines)} lines\n\n{numbered}"
    except Exception as e:
        return f"Read error: {e}"


def read_file_lines(path: str, start_line: int, end_line: int) -> str:
    """Read a specific numbered range of lines from a file, with each line prefixed by its line number.
    Use this to inspect a precise, already-known area of a file (e.g. after search_in_files pointed you
    at a line number) instead of reading the whole file. Do not use this to read an entire small file —
    use read_file for that. All three arguments are required integers/strings; there is no "filename" or
    "file_path" alias, the argument is always named path.
    Example call: read_file_lines(path="agent.py", start_line=10, end_line=25)
    Args:
        path: File path to read from, relative or absolute
        start_line: First line to include, 1-indexed (the first line of the file is 1, not 0)
        end_line: Last line to include, inclusive
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        lines = Path(path).expanduser().read_text(encoding="utf-8").splitlines()
        total = len(lines)
        s = max(1, start_line) - 1
        e = min(total, end_line)
        numbered = "\n".join(f"{s+i+1:4d} | {l}" for i, l in enumerate(lines[s:e]))
        return f"[{path}] lines {start_line}–{end_line} / {total}\n\n{numbered}"
    except Exception as e:
        return f"Error: {e}"


def _python_syntax_warning(path: str, content: str) -> str:
    """Return a warning suffix if `path` is a .py file and `content` doesn't parse — "" otherwise.
    Without this, write_file/edit_file report success even when the model's own generated content
    got silently truncated mid-write (observed in practice: a model's write_file argument cut off
    mid-string near a long session's context limit, leaving a corrupted file with an unterminated
    string literal — reported as "File written" success, then blindly retried 8 times over ~25
    minutes without ever detecting the corruption, since nothing told it the result was broken).
    """
    if not path.endswith(".py"):
        return ""
    try:
        ast.parse(content)
        return ""
    except SyntaxError as e:
        return (f"\n⚠️ WARNING: the file was written, but it is NOT valid Python — "
                f"{type(e).__name__}: {e.msg} (line {e.lineno}). "
                f"Check whether your content got cut short or malformed before continuing.")


_QUOTED_IDENTIFIER_RE = re.compile(r'["\']([A-Za-z_][A-Za-z0-9_]*)["\']')


def _rename_consistency_warning(old_text: str, new_text: str, new_content: str) -> str:
    """Return a warning suffix if this edit looks like a partial rename — a quoted identifier
    (typically a dict key) present in old_text is gone from new_text, but the same identifier
    still appears elsewhere in the file after the edit. Without this, an edit that renames a key
    in most places while missing one occurrence elsewhere reports plain success, and nothing
    signals the rename wasn't applied consistently across the file. Observed twice in practice on
    the same fixture with two different models: a dict key ("attack" -> "attack_range") renamed
    in every function but one leftover initializer, and separately renamed in every place except
    the one function that generates the object read by the others — both left a KeyError only
    reachable by actually running the program, invisible to lint and to this same check's sibling
    _python_syntax_warning (see agentic_contexte.md, "systemic issue" follow-up).
    """
    removed = set(_QUOTED_IDENTIFIER_RE.findall(old_text)) - set(_QUOTED_IDENTIFIER_RE.findall(new_text))
    if not removed:
        return ""
    still_present = sorted(tok for tok in removed if re.search(rf'["\']{re.escape(tok)}["\']', new_content))
    if not still_present:
        return ""
    shown = ", ".join(f'"{tok}"' for tok in still_present[:5])
    return (f"\n⚠️ NOTE: this edit removed {shown} but the same key still appears elsewhere in the "
            f"file — if this was meant to be a rename everywhere, use search_in_files to check the "
            f"other occurrences before considering the change complete.")


def _large_write_note(content: str) -> str:
    """Tool-result-side nudge when a write_file carries bulky content.
    Generating a single large tool-call argument is the most fragile operation in the whole
    stack (JSON truncation bug on the Ollama/llama-server side, confirmed upstream
    #14570/#15465 — directly correlated with large write_file calls). The client-side
    counter-measure is to never ask the model to emit a huge argument at once: a first
    write_file call, then append_file in chunks of <=80 lines. A nudge, never a block."""
    n_lines = content.count("\n") + 1
    if n_lines <= config.LARGE_WRITE_LINES:
        return ""
    note = (f"\n💡 This file is {n_lines} lines — large single writes are the most truncation-prone "
            f"operation (Ollama can cut off a big tool-call payload mid-JSON). For files over "
            f"~{config.LARGE_WRITE_LINES} lines, prefer writing in chunks: one write_file for the first "
            f"≤{config.LARGE_WRITE_LINES} lines, then append_file for each following chunk.")
    if config.GEN_NUM_PREDICT and config.GEN_NUM_PREDICT > 0 and len(content) // 4 >= config.GEN_NUM_PREDICT * 0.8:
        note += (f" Also note: your Max Output Tokens (num_predict) is set to {config.GEN_NUM_PREDICT} in "
                 f"/parameters — a write this size may be truncated by that limit itself. Raise it "
                 f"or split the write.")
    return note


def write_file(path: str, content: str) -> str:
    """Create a new file, or completely overwrite an existing one, with the given content.
    Use this to create a brand-new file or when you genuinely need to replace an entire file's contents.
    For changing part of an existing file, use edit_file instead — it is safer because it fails loudly if
    the target text isn't unique, instead of silently discarding everything else in the file. For a file
    longer than ~80 lines, write the first chunk here and add the rest with append_file — one huge write
    is the single most failure-prone tool call (Ollama can truncate a big payload mid-JSON). Creates any
    missing parent directories automatically. There are only two arguments, named exactly path and content
    — there is no "new_content", "text", or "lines_to_add" parameter.
    Example call: write_file(path="notes.md", content="# Notes\\n\\nFirst line.")
    Args:
        path: File path to create or overwrite, relative or absolute
        content: The complete file content to write, replacing anything already there
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        _auto_snapshot(path)
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return (f"File written: {p.resolve()} ({len(content)} characters)"
                + _python_syntax_warning(path, content) + _large_write_note(content))
    except Exception as e:
        return f"Write error: {e}"


def append_file(path: str, content: str) -> str:
    """Append content to the end of an existing file (creates it if it doesn't exist, like shell >>).
    This is the safe way to write a long file without risking a truncated tool call: create the file with
    write_file (first ≤80 lines), then call append_file once per following ≤80-line chunk. Each chunk is a
    small, reliable tool call — far less likely to be cut off mid-generation than one giant write_file.
    The content is added exactly as given; add a leading newline yourself if the previous chunk didn't end
    with one. There are exactly two arguments, named path and content — same names as write_file.
    Example call: append_file(path="app.py", content="\\n\\ndef helper():\\n    return 42\\n")
    Args:
        path: File path to append to (relative or absolute); created if missing
        content: The text to add at the end of the file
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        _auto_snapshot(path)
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        total = p.stat().st_size
        created = "" if existed else " (new file created)"
        return (f"Appended: {p.resolve()}{created} (+{len(content)} characters, {total} bytes total)"
                + _python_syntax_warning(path, p.read_text(encoding="utf-8")))
    except Exception as e:
        return f"Append error: {e}"


def _closest_snippet_hint(content: str, old_text: str) -> str:
    """On a failed edit_file match, find the most similar block actually in the file and
    show it — without this, a model whose old_text is stale (e.g. from an earlier edit it
    forgot about) has no way to self-correct except guessing again or re-reading the whole
    file, and in practice it usually just resubmits a near-identical guess and fails again.
    """
    content_lines = content.splitlines()
    old_lines = old_text.splitlines() or [old_text]
    n = len(old_lines)
    if n == 0 or len(content_lines) < n:
        return ""
    best_ratio = 0.0
    best_start = 0
    for i in range(len(content_lines) - n + 1):
        window = "\n".join(content_lines[i:i + n])
        ratio = difflib.SequenceMatcher(None, window, old_text).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = i
    if best_ratio < 0.5:
        return ""
    snippet = "\n".join(content_lines[best_start:best_start + n])
    return (f" Closest actual content in the file (line {best_start + 1}, "
            f"{best_ratio:.0%} similar) — use this as your new old_text:\n{snippet}")


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Make a surgical, in-place edit to an existing file by replacing one exact snippet of text with
    another, leaving the rest of the file untouched. This is the preferred way to fix a bug, change a
    function, or tweak a few lines — prefer it over write_file whenever the file already exists and you
    only need to change part of it. It fails safely (no changes made) if old_text does not appear in the
    file, or if it appears more than once — in the latter case, include a few more surrounding lines in
    old_text to make it uniquely identify the spot you mean. There are exactly three arguments, named
    path, old_text, and new_text — there is no "content", "lines_to_add", or "diff" parameter.
    Example call: edit_file(path="calc.py", old_text="return abs(a) + abs(b)", new_text="return a + b")
    Args:
        path: File path to modify, relative or absolute
        old_text: The exact existing text to find and replace; must match verbatim and be unique in the file
        new_text: The text to put in its place
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return f"File not found: {p}{_closest_path_hint(path)}"
        content = p.read_text(encoding="utf-8")
        count = content.count(old_text)
        if count == 0:
            hint = _closest_snippet_hint(content, old_text)
            return f"Text not found in {p.name}. Check the exact spelling.{hint}"
        if count > 1:
            return f"Text found {count} times in {p.name} — narrow down the context."
        _auto_snapshot(path)
        new_content = content.replace(old_text, new_text, 1)
        p.write_text(new_content, encoding="utf-8")
        return (f"Modified: {p.resolve()}" + _python_syntax_warning(path, new_content)
                + _rename_consistency_warning(old_text, new_text, new_content))
    except Exception as e:
        return f"Edit error: {e}"


def create_directory(path: str) -> str:
    """Create a directory and all necessary parents (mkdir -p).
    Args:
        path: Directory path to create
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        p = Path(path).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return f"Directory created: {p}"
    except Exception as e:
        return f"Error: {e}"


def list_directory(path: str = ".") -> str:
    """List a directory's contents with types and sizes. Defaults to the project root.
    Args:
        path: Directory path to list
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Folder not found: {p}"
        if not p.is_dir():
            return f"Not a folder: {p}"
        items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        if not items:
            return f"📁 {p}\n  (empty folder)"
        lines = [f"📁 {p}"]
        for item in items:
            # Hidden files: show only .gitignore and .gitkeep (not .env)
            if item.name.startswith(".") and item.name not in {".gitignore", ".gitkeep"}:
                continue
            if item.is_dir():
                try:
                    n = sum(1 for _ in item.iterdir())
                except PermissionError:
                    n = "?"
                lines.append(f"  📂 {item.name}/  ({n} items)")
            else:
                sz = item.stat().st_size
                sz_s = f"{sz}B" if sz < 1024 else f"{sz//1024}KB" if sz < 1048576 else f"{sz//1048576}MB"
                lines.append(f"  📄 {item.name}  [{sz_s}]")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"
