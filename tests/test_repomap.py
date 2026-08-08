"""repo_map: extraction, ranking, budget, and honest degradation.

Everything here is offline and builds its own throwaway project, so it never depends on
this repository's own contents. The tree-sitter half is skipped rather than failed when
the optional language pack is absent, because working without it is the design.

    PYTHONPATH="$PWD" python tests/test_repomap.py
"""

import tempfile
from pathlib import Path

from agentic import state
from agentic.tools import repomap
from agentic.tools.repomap import _is_distinctive, _pagerank, _python_tags, repo_map

# ── PageRank ─────────────────────────────────────────────────────────────────
# A star: everyone points at "core", which must therefore outrank all of them.
nodes = ["core", "a", "b", "c"]
edges = {"a": {"core": 1.0}, "b": {"core": 1.0}, "c": {"core": 1.0}}
rank = _pagerank(nodes, edges)
assert rank["core"] == max(rank.values()), rank
assert abs(sum(rank.values()) - 1.0) < 0.05, sum(rank.values())

# Personalisation must move the result, otherwise `focus` is decorative.
biased = _pagerank(nodes, edges, personalization={"a": 1.0})
assert biased["a"] > rank["a"], (rank["a"], biased["a"])

# Empty graph must not raise.
assert _pagerank([], {}) == {}

# ── distinctiveness filter ───────────────────────────────────────────────────
assert _is_distinctive("run_agent")
assert not _is_distinctive("__init__"), "dunders are defined everywhere"
assert not _is_distinctive("close"), "generic method names carry no signal"
assert not _is_distinctive("ab"), "too short"
assert not _is_distinctive("print"), "builtin"

# ── Python extraction, no dependencies ───────────────────────────────────────
src = (
    "import os\n"
    "class Widget(Base):\n"
    "    def resize(self, w, h):\n"
    "        return os.stat(w)\n"
    "async def fetch(url, timeout=3):\n"
    "    pass\n"
)
defs, refs = _python_tags(Path("x.py"), src)
names = {d["name"] for d in defs}
assert names == {"Widget", "resize", "fetch"}, names
sig = next(d["sig"] for d in defs if d["name"] == "resize")
assert sig == "resize(w, h)", sig          # self dropped
cls = next(d["sig"] for d in defs if d["name"] == "Widget")
assert cls == "class Widget(Base)", cls
assert "os" in refs and "stat" in refs, refs

# A syntax error yields nothing rather than exploding the whole map.
broken, broken_refs = _python_tags(Path("bad.py"), "def oops(:\n")
assert broken == [] and broken_refs == set()

# ── end to end on a synthetic project ────────────────────────────────────────
proj = Path(tempfile.mkdtemp())
state.PROJECT_ROOT = proj
(proj / "pkg").mkdir()
(proj / "pkg" / "core.py").write_text(
    "def compute_total(items):\n    return sum(items)\n"
    "class Ledger:\n    def post(self, x):\n        return x\n"
)
# Three modules all lean on core, so core must win the ranking.
for n in ("alpha", "beta", "gamma"):
    (proj / "pkg" / f"{n}.py").write_text(
        f"from pkg.core import compute_total, Ledger\n"
        f"def {n}_run(v):\n    return compute_total(v) + Ledger().post(v)\n"
    )

out = repo_map()
assert "core.py" in out, out
assert "compute_total(items)" in out, out
assert "class Ledger" in out, out
first_file_line = next(l for l in out.splitlines() if l.endswith(".py"))
assert "core.py" in first_file_line, f"core.py should rank first, got: {first_file_line}"

# focus= must reorder the output, not merely annotate it.
focused = repo_map(focus="gamma")
first_focused = next(l for l in focused.splitlines() if l.endswith(".py"))
assert "gamma" in first_focused, f"focus ignored, got: {first_focused}"
assert "Focused on: gamma" in focused

# The budget must be respected, and say so rather than silently truncating. The returned
# string must never exceed max_chars: the footer used to be appended after the budget was
# already spent, so a request for 200 characters returned 324.
for budget in (6000, 1000, 400, 300):
    out_b = repo_map(max_chars=budget)
    assert len(out_b) <= budget, f"budget {budget} exceeded: got {len(out_b)}"
tight = repo_map(max_chars=300)
assert "more files omitted" in tight, tight

# No active project is an error, not a traceback.
state.PROJECT_ROOT = None
assert repo_map().startswith("ERROR"), repo_map()
state.PROJECT_ROOT = proj

# A project with no recognised source files says so plainly.
empty = Path(tempfile.mkdtemp())
(empty / "notes.txt").write_text("hello")
state.PROJECT_ROOT = empty
assert "No source files found" in repo_map()
state.PROJECT_ROOT = proj

# ── other languages ──────────────────────────────────────────────────────────
poly = Path(tempfile.mkdtemp())
state.PROJECT_ROOT = poly
(poly / "a.js").write_text("export function alpha(a, b) { return b; }\nexport class Beta {}\n")
(poly / "m.go").write_text("package main\ntype Server struct { port int }\n"
                           "func Listen(host string) error { return nil }\n")
(poly / "l.rs").write_text("pub struct Cfg { pub n: u32 }\npub fn build(n: u32) -> Cfg { Cfg { n } }\n")

try:
    import tree_sitter_language_pack  # noqa: F401
    have_ts = True
except Exception:                                              # noqa: BLE001
    have_ts = False

poly_out = repo_map()
if have_ts:
    for expected in ("alpha(a, b)", "class Beta", "type Server", "Listen(host string)",
                     "struct Cfg", "build(n: u32)"):
        assert expected in poly_out, f"missing {expected!r} in:\n{poly_out}"
    # The label must be the language's own keyword, not Python's.
    assert "class Cfg" not in poly_out, "a Rust struct must not be called a class"
    assert "class Server" not in poly_out, "a Go type must not be called a class"
    print("  tree-sitter: 6 languages verified")
else:
    # Without the extra, files are still listed and the user is told what to install.
    assert "a.js" in poly_out and "m.go" in poly_out, poly_out
    assert "no definitions extracted" in poly_out, poly_out
    assert "install the optional extra" in poly_out, poly_out
    print("  tree-sitter absent: degradation path verified")

# Whichever branch the environment took above, the other one still has to work. CI has no
# language pack and this machine does, so without forcing it neither run would cover both.
_real = repomap._treesitter_tags
try:
    repomap._treesitter_tags = lambda path, src: None      # simulate the pack being absent
    degraded = repo_map()
    assert "a.js" in degraded and "m.go" in degraded, degraded
    assert "no definitions extracted" in degraded, degraded
    assert "install the optional extra" in degraded, degraded
    assert "alpha(a, b)" not in degraded, "should not have parsed anything"
finally:
    repomap._treesitter_tags = _real
print("  degradation path verified by forcing the import to fail")

state.PROJECT_ROOT = None
print("test_repomap: ALL PASS")
