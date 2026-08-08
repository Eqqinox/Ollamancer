"""Repository map: a ranked, budgeted outline of what a codebase contains.

The problem this solves is the one every coding agent hits on an unfamiliar repo. The
model needs to know what exists before it can decide what to read, but reading everything
does not fit in the context window and grepping blind wastes turns. A repo map is the
middle path: every file's *signatures* rather than its bodies, ordered so the important
things survive the budget.

The idea and the ranking are Aider's (see https://aider.chat/2023/10/22/repomap.html).
The insight worth stealing is that **definitions are not equally interesting**: a helper
called from twenty places is better context than a private function called once. So the
files form a graph, an edge from A to B meaning "A uses a name that B defines", and
PageRank over that graph decides what gets the budget.

Three deliberate departures from Aider's implementation:

* **Python needs no dependencies.** Extraction uses the standard library's `ast`, so the
  map always works on a Python project with nothing installed. Other languages use
  tree-sitter when `tree-sitter-language-pack` is present and are otherwise listed
  without their definitions rather than silently dropped. `tree-sitter-languages`, which
  Aider used originally, is unmaintained; the language pack is its successor.
* **PageRank is implemented here**, about fifteen lines of power iteration, rather than
  taking a networkx dependency for one function.
* **The budget is characters, not tokens.** The agent has no tokenizer, and inventing one
  to be approximately right anyway is not worth the dependency. Roughly four characters
  per token is close enough to reason about.
"""

import ast
import re
from collections import defaultdict
from pathlib import Path

from agentic import config, state
from agentic.safety import _audit, _check_file_path

# Names that appear everywhere and carry no signal about which file matters. Without this
# every file that calls print() or len() looks connected to every other.
_NOISE = frozenset("""
self cls None True False print len str int float bool list dict set tuple type
range enumerate zip map filter sorted sum min max abs any all open super isinstance
getattr setattr hasattr format join append extend items keys values get add remove
""".split())

_MAX_FILES = 400          # a repo larger than this gets its biggest files sampled
_MIN_NAME_LEN = 3         # one- and two-letter names are almost always locals
_FOOTER_RESERVE = 260     # room kept back for the "omitted" line and any notes, so the
                          # returned string honours max_chars instead of overshooting it

# Method names so common that defining one says nothing about a file's importance.
# Without this, a throwaway test helper class defining __init__, __iter__ and close
# collects an edge from every file in the repository that happens to call any of them,
# and PageRank duly ranks the test above the modules it is testing. Observed exactly
# that on this codebase: tests/test_escape.py came second, above loop.py.
_GENERIC_DEFS = frozenset("""
close read write open run start stop send recv next reset clear update setup teardown
main handle process execute call get set add put delete list count size name value
""".split())


def _is_distinctive(name: str) -> bool:
    """Whether defining this name tells us anything about which file matters."""
    if len(name) < _MIN_NAME_LEN or name in _NOISE:
        return False
    if name.startswith("__") and name.endswith("__"):   # dunders are never distinctive
        return False
    return name not in _GENERIC_DEFS


# ── extraction ───────────────────────────────────────────────────────────────

def _python_tags(path: Path, src: str) -> tuple[list[dict], set[str]]:
    """Definitions and referenced names in a Python file, via the standard library.

    Returns ([{kind, name, line, sig}], {referenced names}). A syntax error yields nothing
    rather than raising: a repo map that dies on one unparseable file is useless.
    """
    try:
        tree = ast.parse(src, filename=str(path))
    except (SyntaxError, ValueError):
        return [], set()

    defs, refs = [], set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
            defs.append({"kind": "def", "name": node.name, "line": node.lineno,
                         "sig": f"{node.name}({', '.join(args)})"})
        elif isinstance(node, ast.ClassDef):
            bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
            defs.append({"kind": "class", "name": node.name, "line": node.lineno,
                         "sig": f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")})
        elif isinstance(node, ast.Name):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            refs.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                refs.add((alias.asname or alias.name).split(".")[0])
    return defs, refs


# Grammars name their definition nodes differently and there is no cross-language
# convention: JavaScript has function_declaration, C has function_definition, Rust has
# function_item, Go wraps its types in a type_spec. Matching a keyword plus one of these
# suffixes covers all of them without a per-language query file. Verified against
# JavaScript, Go, Rust, Java, C and Ruby; see tests/test_repomap.py.
_TS_DEF_KINDS = ("function", "method", "class", "struct", "interface",
                 "type", "enum", "trait", "module")
_TS_DEF_SUFFIXES = ("_declaration", "_definition", "_item", "_specifier", "_spec")
_TS_DEF_EXACT = frozenset({"method", "class", "module", "function"})


def _is_definition_node(kind: str) -> bool:
    if kind in _TS_DEF_EXACT:
        return True
    return (any(k in kind for k in _TS_DEF_KINDS)
            and kind.endswith(_TS_DEF_SUFFIXES))


def _treesitter_tags(path: Path, src: str) -> tuple[list[dict], set[str]] | None:
    """Same, for non-Python files, when the optional language pack is installed.

    Returns None when tree-sitter is unavailable or has no grammar for this extension, so
    the caller can distinguish "nothing defined here" from "could not look".
    """
    try:
        from tree_sitter_language_pack import get_language, get_parser
    except Exception:                                          # noqa: BLE001
        return None

    lang = _LANG_BY_EXT.get(path.suffix)
    if not lang:
        return None
    try:
        parser = get_parser(lang)
        tree = parser.parse(src.encode("utf-8", errors="ignore"))
    except Exception:                                          # noqa: BLE001
        return None

    defs, refs = [], set()

    def walk(node, depth=0):
        if depth > 60:
            return
        kind = node.type
        if _is_definition_node(kind):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = src[name_node.start_byte:name_node.end_byte]
                if name:
                    # Use the language's own keyword. Calling a Rust struct or a Go type
                    # a "class" would be telling the model something untrue about the
                    # code it is about to edit.
                    label = next((k for k in ("class", "struct", "interface", "trait",
                                              "enum", "module", "type") if k in kind), "")
                    is_type = bool(label)
                    params = node.child_by_field_name("parameters")
                    if params is not None and not is_type:
                        raw = src[params.start_byte:params.end_byte]
                        sig = f"{name}{' '.join(raw.split())}"
                    elif is_type:
                        sig = f"{label} {name}"
                    else:
                        sig = name
                    defs.append({"kind": "class" if is_type else "def",
                                 "name": name, "line": node.start_point[0] + 1,
                                 "sig": sig[:120]})
        elif kind == "identifier":
            refs.add(src[node.start_byte:node.end_byte])
        for child in node.children:
            walk(child, depth + 1)

    walk(tree.root_node)
    return defs, refs


# Extensions the agent already treats as source, mapped to language-pack names.
_LANG_BY_EXT = {
    ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust", ".java": "java", ".c": "c", ".cpp": "cpp",
    ".h": "c", ".hpp": "cpp", ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".kt": "kotlin",
}


# ── ranking ──────────────────────────────────────────────────────────────────

def _pagerank(nodes: list, edges: dict, personalization: dict | None = None,
              damping: float = 0.85, iterations: int = 30) -> dict:
    """Plain power-iteration PageRank over a weighted directed graph.

    `edges` is {src: {dst: weight}}. `personalization` biases the random restart toward
    particular nodes, which is how a caller's focus is honoured: restarting more often at
    the files you asked about pulls their neighbours up the ranking too.
    """
    n = len(nodes)
    if n == 0:
        return {}
    idx = {node: i for i, node in enumerate(nodes)}

    if personalization:
        total = sum(personalization.values()) or 1.0
        restart = [personalization.get(node, 0.0) / total for node in nodes]
        if not any(restart):
            restart = [1.0 / n] * n
    else:
        restart = [1.0 / n] * n

    rank = [1.0 / n] * n
    out = []
    for node in nodes:
        targets = edges.get(node, {})
        total_w = sum(targets.values()) or 1.0
        out.append([(idx[t], w / total_w) for t, w in targets.items() if t in idx])

    for _ in range(iterations):
        nxt = [(1.0 - damping) * restart[i] for i in range(n)]
        dangling = 0.0
        for i, targets in enumerate(out):
            if not targets:
                dangling += rank[i]
                continue
            for j, w in targets:
                nxt[j] += damping * rank[i] * w
        if dangling:
            for i in range(n):
                nxt[i] += damping * dangling * restart[i]
        rank = nxt
    return {node: rank[idx[node]] for node in nodes}


# ── the tool ─────────────────────────────────────────────────────────────────

def repo_map(focus: str = "", max_chars: int = 6000) -> str:
    """Outline the whole project: every file's classes and functions, ranked by importance.

    Use this FIRST on an unfamiliar codebase, before reading files or grepping. It shows
    what exists and how the pieces connect, so you can choose what to read instead of
    guessing. It lists signatures only, never function bodies.

    Files are ranked with PageRank over a "who uses whose names" graph, so widely used
    modules appear before leaf scripts, and the output is truncated to a character budget
    rather than dumping everything.

    Args:
        focus: optional space-separated file paths or symbol names to bias the ranking
            toward, e.g. "loop.py retry" or "search_web". Their neighbours in the graph
            are pulled up too. Leave empty for an overview of the whole project.
        max_chars: budget for the map, default 6000, roughly 1500 tokens.
    """
    root = state.PROJECT_ROOT
    if root is None:
        return "ERROR: no project folder is active."

    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in config._REF_SOURCE_EXTS:
            continue
        if any(part in config._REF_EXCLUDE_DIRS or part.startswith(".") for part in p.relative_to(root).parts[:-1]):
            continue
        files.append(p)

    if not files:
        return (f"No source files found under {root}. Recognised extensions: "
                f"{', '.join(sorted(config._REF_SOURCE_EXTS))}.")

    truncated_repo = False
    if len(files) > _MAX_FILES:
        files.sort(key=lambda p: p.stat().st_size, reverse=True)
        files = files[:_MAX_FILES]
        truncated_repo = True

    defs_by_file: dict[Path, list[dict]] = {}
    refs_by_file: dict[Path, set[str]] = {}
    unparsed: list[Path] = []

    for p in files:
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if p.suffix == ".py":
            d, r = _python_tags(p, src)
        else:
            got = _treesitter_tags(p, src)
            if got is None:
                unparsed.append(p)
                d, r = [], set()
            else:
                d, r = got
        defs_by_file[p] = d
        refs_by_file[p] = {x for x in r if len(x) >= _MIN_NAME_LEN and x not in _NOISE}

    # Which file defines which name. A name defined in several files is ambiguous and
    # tells us little about direction, so it is dropped rather than guessed at.
    definer: dict[str, list[Path]] = defaultdict(list)
    for p, ds in defs_by_file.items():
        for d in ds:
            if not _is_distinctive(d["name"]):
                continue
            definer[d["name"]].append(p)

    edges: dict[Path, dict[Path, float]] = defaultdict(lambda: defaultdict(float))
    for p, refs in refs_by_file.items():
        for name in refs:
            owners = definer.get(name)
            if not owners or len(owners) > 3:
                continue
            for owner in owners:
                if owner != p:
                    edges[p][owner] += 1.0

    personalization: dict[Path, float] = {}
    focus_terms = [t for t in focus.split() if t]
    if focus_terms:
        for p in files:
            rel = str(p.relative_to(root))
            score = 0.0
            for term in focus_terms:
                if term in rel:
                    score += 10.0
                if any(d["name"] == term for d in defs_by_file.get(p, [])):
                    score += 10.0
                elif term in refs_by_file.get(p, set()):
                    score += 2.0
            if score:
                personalization[p] = score

    ranked = _pagerank(files, {k: dict(v) for k, v in edges.items()}, personalization or None)

    order = sorted(files, key=lambda p: (-ranked.get(p, 0.0), str(p)))

    lines: list[str] = []
    header = f"Repository map of {root.name}, {len(files)} source files ranked by how widely each is used."
    if focus_terms:
        header += f" Focused on: {' '.join(focus_terms)}."
    lines.append(header)
    lines.append("")

    used = len(header) + 2
    shown = 0
    for p in order:
        ds = defs_by_file.get(p, [])
        rel = str(p.relative_to(root))
        block = [f"{rel}"]
        # Most-referenced definitions first, so a truncated block keeps the useful ones.
        ds_sorted = sorted(ds, key=lambda d: -sum(1 for r in refs_by_file.values() if d["name"] in r))
        for d in ds_sorted[:12]:
            block.append(f"  {d['line']:>5}  {d['sig']}")
        if not ds:
            block.append("        (no definitions extracted)")
        chunk = "\n".join(block) + "\n"
        # Reserve room for the footer. Appending it after spending the whole budget is
        # how a caller asking for 200 characters used to receive 324.
        if used + len(chunk) > max(0, max_chars - _FOOTER_RESERVE):
            remaining = len(order) - shown
            if remaining > 0:
                lines.append(f"... {remaining} more files omitted (budget {max_chars} chars). "
                             f"Raise max_chars, or pass focus= to rank what you care about first.")
            break
        lines.append(chunk.rstrip("\n"))
        used += len(chunk)
        shown += 1

    notes = []
    if truncated_repo:
        notes.append(f"repository has more than {_MAX_FILES} source files; the largest {_MAX_FILES} were mapped")
    if unparsed:
        exts = sorted({p.suffix for p in unparsed})
        notes.append(f"{len(unparsed)} non-Python files ({', '.join(exts)}) were listed without definitions: "
                     f"install the optional extra for those languages "
                     f'(pip install "ollamancer[treesitter] @ git+https://github.com/Eqqinox/Ollamancer.git")')
    if notes:
        lines.append("")
        lines.extend(f"Note: {n}." for n in notes)

    _audit("REPO_MAP", {"files": len(files), "shown": shown, "focus": focus})
    return "\n".join(lines)
