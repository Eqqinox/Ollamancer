"""pass^k roll-up and per-rep hand judgements in benchmarks/model_ranking/score.py.

A standalone assertion script, like its neighbours: `conftest.py` excludes
`tests/test_*.py` from collection and `test_scripts.py` runs each one in its own
interpreter. Nothing here touches `results/` or the real `judged.json` — every case is
built from synthetic run directories under a temp dir, so this is safe to run while a
benchmark campaign is writing to `results/`.

What is pinned here is the metric itself:

  * pass^k is the MINIMUM across reps, never the mean. This is the whole claim of
    PLAN.md §1.3, and the version of score.py before 2026-08-11 did not implement it —
    it emitted N unlinked rows for N reps and nothing ever compared them.
  * A rep count that differs from the rest of the table is visible in the output. A
    pass^1 row silently sitting in a pass^2 table is the failure this roll-up exists
    to prevent.
  * An unjudged item is `judged_pending`, NOT a zero. Those are different facts and
    conflating them turns "nobody has looked at this yet" into "this was bad".
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORE_PY = ROOT / "benchmarks" / "model_ranking" / "score.py"


def _load_score_module():
    spec = importlib.util.spec_from_file_location("_score_under_test", SCORE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sc = _load_score_module()


def _run(model, task, run, total, rep=1, pending=None, status="ok", mx=25):
    """A per-run score dict shaped exactly like score_run() returns."""
    return {"run": run, "model": model, "task": task, "rep": rep, "status": status,
            "total": total, "max": mx, "parts": {}, "notes": [],
            "judged_pending": list(pending or []), "seconds": 1.0, "n_tool_calls": 0}


# ── 1. pass^k takes the MIN, not the mean ────────────────────────────────────

rows = sc.rollup([
    _run("m", "t1", "r/m/t1_rep1", 80, rep=1, mx=100),
    _run("m", "t1", "r/m/t1_rep2", 40, rep=2, mx=100),
])
assert len(rows) == 1, rows
assert rows[0]["pass_k_total"] == 40, f"pass^k must be the min, got {rows[0]['pass_k_total']}"
assert rows[0]["mean_total"] == 60.0, rows[0]["mean_total"]
assert rows[0]["spread"] == 40, rows[0]["spread"]
assert rows[0]["n_reps"] == 2

# The mean must never be mistaken for the headline: 60 is recorded, 40 is reported.
assert rows[0]["pass_k_total"] != rows[0]["mean_total"]

# A failed rep collapses the total on its own, even if the other rep was perfect.
rows = sc.rollup([
    _run("m", "t1", "r/m/t1_rep1", 25, rep=1),
    _run("m", "t1", "r/m/t1_rep2", 0, rep=2, status="timeout"),
])
assert rows[0]["pass_k_total"] == 0, rows[0]
assert rows[0]["status_all_ok"] is False, "a non-ok rep must clear status_all_ok"
assert rows[0]["spread"] == 25, "bimodal must be distinguishable from consistently bad"


# ── 2. 1-rep and 2-rep models coexist, and the difference is visible ─────────

mixed = sc.rollup([
    _run("two_reps", "t1", "r/a/t1_rep1", 20, rep=1),
    _run("two_reps", "t1", "r/a/t1_rep2", 18, rep=2),
    _run("one_rep", "t1", "r/b/t1_rep1", 24, rep=1),
])
by_model = {r["model"]: r for r in mixed}
assert by_model["two_reps"]["n_reps"] == 2
assert by_model["one_rep"]["n_reps"] == 1
assert by_model["one_rep"]["pass_k_total"] == 24, "a single rep is still reported"

# The marker must actually reach the printed output, not just the JSON.
model_rows = sc.rollup_by_model(mixed)
import io
import contextlib

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    sc.print_rollup(mixed, model_rows)
out = buf.getvalue()
assert "◆" in out, "a differing rep count must be visually marked in the table"
assert "NOT comparable" in out, "the legend must spell out why the marked rows differ"
assert " 2 " in out and " 1 " in out, "n_reps must be shown per row"

# Per-model roll-up sums pass^k across tasks and ranks descending.
ranked = sc.rollup_by_model(sc.rollup([
    _run("hi", "t1", "r/hi/t1_rep1", 20, rep=1), _run("hi", "t2", "r/hi/t2_rep1", 20, rep=1),
    _run("lo", "t1", "r/lo/t1_rep1", 5, rep=1), _run("lo", "t2", "r/lo/t2_rep1", 5, rep=1),
]))
assert [r["model"] for r in ranked] == ["hi", "lo"], "must be sorted by pass^k sum, descending"
assert ranked[0]["pass_k_sum"] == 40, ranked[0]
assert ranked[0]["n_tasks"] == 2


# ── 3./4./5. judged.json key resolution ──────────────────────────────────────
# These exercise score_run() end to end, so they need a run directory on disk and a
# judged.json next to the module. HERE is repointed at a temp dir so the real
# judged.json is never read and never written.

def _make_run(tmp: Path, name: str, model: str, task: str, answer: str) -> Path:
    run = tmp / "results" / "mdl" / name
    run.mkdir(parents=True)
    (run / "answer.txt").write_text(answer)
    (run / "meta.json").write_text(json.dumps(
        {"model": model, "task": task, "status": "ok", "seconds": 1.0, "n_tool_calls": 0}))
    (run / "tool_trace.json").write_text("[]")
    (run / "tool_outputs.json").write_text("[]")
    return run


# A t1 answer that scores the deterministic items, leaving only d_judged outstanding.
T1_ANSWER = "(a) A: 10:00, B: 11:00, C: 12:00, D: 09:00\n(b) 255\n(c) 6\n(d) some prose\n"

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    original_here = sc.HERE
    sc.HERE = tmp
    try:
        rep1 = _make_run(tmp, "t1_rep1", "mdl:x", "t1", T1_ANSWER)
        rep2 = _make_run(tmp, "t1_rep2", "mdl:x", "t1", T1_ANSWER)

        # 3. per-rep key wins over the legacy model-level key -------------------
        (tmp / "judged.json").write_text(json.dumps({
            "t1.d_judged": {"mdl:x": 1, "mdl:x#rep2": 4},
        }))
        s2 = sc.score_run(rep2)
        assert s2["rep"] == 2, f"rep must be parsed from the dir name, got {s2['rep']}"
        assert s2["parts"]["d_judged"] == 4, f"per-rep key must win, got {s2['parts']}"
        assert s2["judged_pending"] == []
        assert any("judged for this rep" in n for n in s2["notes"]), s2["notes"]
        assert not any("inherited" in n for n in s2["notes"]), "per-rep hit must not be flagged inherited"

        # 4. legacy model-only key still resolves, and is flagged as inherited ---
        s1 = sc.score_run(rep1)
        assert s1["rep"] == 1
        assert s1["parts"]["d_judged"] == 1, "legacy model-level key must still resolve"
        assert s1["judged_pending"] == []
        assert any("inherited from legacy model-level key" in n for n in s1["notes"]), s1["notes"]

        # 5. absent from judged.json -> judged_pending, NOT a silent 0 ----------
        (tmp / "judged.json").write_text(json.dumps({"t1.d_judged": {"someone:else": 4}}))
        s3 = sc.score_run(rep2)
        assert s3["judged_pending"] == ["d_judged"], s3["judged_pending"]

        # The roll-up must refuse to call such a total final.
        prov = sc.rollup([s3])
        assert prov[0]["provisional"] is True, "pending judgement must mark the total PROVISIONAL"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sc.print_rollup(prov, sc.rollup_by_model(prov))
        assert "PROVISIONAL" in buf.getvalue()

        # …and the debt must appear in the worklist with its task, item, model and rep.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sc.print_judgement_worklist([s3])
        work = buf.getvalue()
        assert "t1.d_judged" in work and "mdl:x" in work, work
        assert "\n    2 " in work.replace("  ", "  ") or " 2 " in work, "rep number must be listed"

        # A judged total and an unjudged one are NOT the same number: the pending run
        # scores strictly lower, which is why it must be labelled rather than compared.
        (tmp / "judged.json").write_text(json.dumps({"t1.d_judged": {"mdl:x#rep2": 4}}))
        judged_total = sc.score_run(rep2)["total"]
        assert judged_total > s3["total"], "unjudged must be a floor below the judged score"
    finally:
        sc.HERE = original_here


# ── 6. a half-written run directory must not crash the roll-up ───────────────
# results/ is written concurrently by rank.sh, so this is a real state, not a hypothetical.

with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    partial = tmp / "t1_rep1"
    partial.mkdir()
    (partial / "meta.json").write_text('{"model": "m", "task": "t1", "stat')  # truncated
    assert sc.score_run(partial) is None, "an unparseable meta.json must skip, not raise"

    empty = tmp / "t2_rep1"
    empty.mkdir()
    assert sc.score_run(empty) is None, "a run dir with no meta.json must skip, not raise"

print("test_score_rollup: all assertions passed")
