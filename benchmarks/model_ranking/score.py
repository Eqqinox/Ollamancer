#!/usr/bin/env python3
"""Score one run directory produced by run_one.py.

Every check here is deterministic and re-runnable from the artefacts on disk, so a
score can be audited afterwards rather than taken on trust. The two judged items
(T1d and T4 prose quality) are left at 0 and filled in by hand — they are flagged
in the output as `judged_pending` so they cannot be silently forgotten.

    python3 score.py results/qwen3.5_4b/t1_rep1
    python3 score.py --all results/

`--all` scores every run under the path and then prints three things: the per-run
detail blocks, a pass^k table with one row per (model, task), and a ranked per-model
table summing pass^k across t1..t4. It writes `scores.json` (the flat per-run list,
kept as the auditable record) and `scores_rollup.json` (both roll-up levels).

The headline number is the MINIMUM across reps, not the mean — see `rollup()`. Rows
whose rep count differs from the rest of the table are marked, because mixing pass^1
and pass^2 rows without a marker is precisely the error this roll-up exists to stop.
A pass^k total is PROVISIONAL while any contributing rep still needs a hand
judgement; `--all` ends with a worklist of every judgement still owed.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

# Sources that answer "what happened today" by summarising other outlets. T2 asks
# for the outlet that actually reported the story, so these are penalised.
AGGREGATORS = {
    "wikipedia.org", "en.wikipedia.org", "m.wikipedia.org", "wikinews.org",
    "news.google.com", "news.yahoo.com", "msn.com", "flipboard.com",
    "reddit.com", "ground.news", "allsides.com", "memeorandum.com",
}

EXEC_TOOLS = {"run_command", "python_repl", "run_tests", "run_background"}

T1_SCHEDULE = {"A": "10:00", "B": "11:00", "C": "12:00", "D": "09:00"}


def _read_json(path: Path, default):
    """Parse a JSON artefact, tolerating a file that is missing or still being written.

    The campaign driver writes into `results/` while a roll-up may be reading it, so a
    run directory can legitimately be caught half-written. A partial artefact must not
    crash the whole table: it is reported as an unscoreable run instead.
    """
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return default


def _rep_of(run: Path) -> int | None:
    """Rep number from the run directory name: `t1_rep2` -> 2.

    Returned as None when the name carries no rep, so callers can tell "rep unknown"
    apart from "rep 1" — assuming 1 is how a rep-2 answer ends up silently scored
    against a rep-1 hand judgement.
    """
    m = re.search(r"_rep(\d+)$", run.name)
    return int(m.group(1)) if m else None


def _load(run: Path) -> tuple[str, dict, list, list]:
    answer = ""
    if (run / "answer.txt").exists():
        try:
            answer = (run / "answer.txt").read_text(errors="replace")
        except OSError:
            answer = ""
    meta = _read_json(run / "meta.json", {})
    trace = _read_json(run / "tool_trace.json", [])
    # Grounding evidence: prefer the full per-call capture. `tool_results.json` (from
    # state._last_turn_tool_results) only ever holds the final ReAct round, so on its own
    # it makes a model that cited real URLs early in the run look like a fabricator.
    outs = (run / "tool_outputs.json")
    if outs.exists():
        raw = _read_json(outs, [])
        results = [o["output"] for o in raw if isinstance(o, dict) and "output" in o]
    else:
        results = _read_json(run / "tool_results.json", [])
    if not isinstance(results, list):
        results = []
    return answer, meta, trace, [r for r in results if isinstance(r, str)]


def _section(text: str, letter: str) -> str:
    """The chunk of a T1 answer belonging to item (a)…(d).

    Item markers are matched ONLY at the start of a line. An earlier version searched
    anywhere and case-insensitively, so in a correct answer like

        (a) A: 10:00, B: 11:00, C: 12:00, D: 09:00

    the "B:" was read as the start of item (b) and truncated item (a) after its first
    pairing — scoring a perfect answer 2.2/25. Anchoring to the line start fixes it.
    """
    marks: dict[str, tuple[int, int]] = {}
    for m in re.finditer(r"(?m)^[\s>*_#-]*[\(\[]?([a-dA-D])[\)\].:]", text):
        key = m.group(1).lower()
        marks.setdefault(key, (m.start(), m.end()))
    if letter not in marks:
        return text
    start, body = marks[letter][0], marks[letter][1]
    later = [marks[c][0] for c in "abcd" if c in marks and marks[c][0] > start]
    return text[body:min(later)] if later else text[body:]


def _ints(text: str) -> set[int]:
    return {int(n.replace(",", "").replace(" ", "")) for n in re.findall(r"\b\d[\d,]{0,9}\b", text)}


def _urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\)\]\>\"'`,]+", text)


def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# ── T1 ───────────────────────────────────────────────────────────────────────

def score_t1(answer, meta, trace, results):
    d, notes = {}, []

    sec_a = _section(answer, "a")
    hits = 0
    for server, time_ in T1_SCHEDULE.items():
        t_alt = time_.lstrip("0")                       # "09:00" may be written "9:00"
        near = rf"(?:{re.escape(time_)}|{re.escape(t_alt)})"
        pair = (re.search(rf"\b{server}\b.{{0,40}}?{near}", sec_a, re.S) or
                re.search(rf"{near}.{{0,40}}?\b{server}\b", sec_a, re.S))
        if pair:
            hits += 1
    d["a_schedule"] = round(hits * 2.25, 1)
    notes.append(f"(a) {hits}/4 pairings correct")

    d["b_backoff"] = 6 if 255 in _ints(_section(answer, "b")) else 0
    notes.append(f"(b) {'255 found' if d['b_backoff'] else 'wrong / missing'}")

    d["c_count"] = 6 if 6 in _ints(_section(answer, "c")) else 0
    notes.append(f"(c) {'6 found' if d['c_count'] else 'wrong / missing'}")

    d["d_judged"] = 0
    notes.append("(d) JUDGED — max 4, fill in by hand")

    n_tools = len(trace)
    d["tool_penalty"] = -3 * n_tools
    if n_tools:
        notes.append(f"used {n_tools} tool call(s) on a no-tool task: {-3 * n_tools}")

    return d, notes, ["d_judged"]


# ── T2 ───────────────────────────────────────────────────────────────────────

def score_t2(answer, meta, trace, results):
    d, notes = {}, []
    names = [t["tool"] for t in trace]
    blob = "\n".join(results).lower()

    searchy = [i for i, n in enumerate(names) if n in ("search_web", "search_web_deep")]
    if "get_datetime" in names and searchy and names.index("get_datetime") < searchy[0]:
        d["datetime_first"] = 5
    elif "get_datetime" in names:
        d["datetime_first"] = 2
        notes.append("called get_datetime, but only after searching")
    else:
        d["datetime_first"] = 0
        notes.append("never called get_datetime — cannot know what 'last 24 hours' means")

    d["deep_read"] = 4 if "search_web_deep" in names else (1 if "search_web" in names else 0)

    sources = re.findall(r"Source:\s*(https?://\S+)", answer, re.I) or _urls(answer)
    n_stories = max(len(sources), len(re.findall(r"^\s*(?:\d+[\.\)]|[-*#])\s+\S", answer, re.M)))
    d["story_count"] = min(5, round(5 * min(n_stories, 3) / 3, 1))   # target is 3 stories
    notes.append(f"{n_stories} stories, {len(sources)} source URLs")

    domains = [_domain(u) for u in sources if _domain(u)]
    uniq = set(domains)
    d["diversity"] = min(4, round(4 * min(len(uniq), 3) / 3, 1))     # target is 3 outlets
    notes.append(f"{len(uniq)} distinct domains: {', '.join(sorted(uniq)) or 'none'}")

    if sources:
        grounded = sum(1 for u in sources if u.lower().rstrip("/") in blob or _domain(u) in blob)
        d["grounded"] = round(7 * grounded / len(sources), 1)
        if grounded < len(sources):
            notes.append(f"{len(sources) - grounded} URL(s) appear in NO tool result — fabricated or altered")
    else:
        d["grounded"] = 0
        notes.append("no source URLs at all")

    agg = uniq & AGGREGATORS
    d["aggregator_penalty"] = -3 if agg else 0
    if agg:
        notes.append(f"aggregator used as source: {', '.join(sorted(agg))}")

    dupes = _t2_duplicates(answer)
    d["duplicate_penalty"] = -4 if dupes else 0
    if dupes:
        notes.append(f"same event reported twice: {dupes}")

    return d, notes, []


def _t2_duplicates(answer: str):
    """Reuse the agent's own shipped duplicate-event heuristic, so the benchmark and
    the runtime agree on what counts as reporting the same story twice."""
    try:
        sys.path.insert(0, str(REPO))
        from agentic.loop import _duplicate_items
        hit = _duplicate_items(answer)
        return hit[2] if hit else None
    except Exception:                                          # noqa: BLE001
        return None


# ── T3 ───────────────────────────────────────────────────────────────────────

def score_t3(answer, meta, trace, results):
    d, notes = {}, []
    game = Path(meta.get("_run_dir", ".")) / "game.py"
    if not game.exists():
        return {"verify": 0, "bug_alive": 0, "bug_attack": 0, "executed": 0}, \
               ["game.py missing from the run — nothing to score"], []

    proc = subprocess.run([sys.executable, str(REPO / "benchmarks/play_verify.py"),
                           str(game), "--timeout", "20"],
                          capture_output=True, text=True, timeout=180)
    d["verify"] = 10 if proc.returncode == 0 else 0
    notes.append(f"play_verify: {'PASS' if proc.returncode == 0 else 'FAIL'} — "
                 f"{proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr.strip()[:200]}")

    smoke = subprocess.run([sys.executable, str(game)], input="1\n1\n3\n5\n1\n2\n4\n",
                           capture_output=True, text=True, timeout=30)
    err = smoke.stderr
    d["bug_alive"] = 0 if "'alive'" in err else 6
    d["bug_attack"] = 0 if "'attack_range'" in err or "'attack'" in err else 6
    if not d["bug_alive"]:
        notes.append("bug 1 unfixed: KeyError 'alive'")
    if not d["bug_attack"]:
        notes.append("bug 2 unfixed: KeyError on attack/attack_range")

    ran = [t for t in trace if t["tool"] in EXEC_TOOLS and "game" in json.dumps(t["args"]).lower()]
    d["executed"] = 3 if ran else 0
    if not ran:
        notes.append("never executed the program — the fix was asserted, not verified")

    return d, notes, []


# ── T4 ───────────────────────────────────────────────────────────────────────

REQUIRED_SECTIONS = ["## Timeline", "## How it spreads", "## Remediation steps", "## Sources"]


def score_t4(answer, meta, trace, results):
    d, notes = {}, []
    report_path = Path(meta.get("_run_dir", ".")) / "report.md"
    if not report_path.exists():
        return {"written": 0, "structure": 0, "length": 0, "citations_resolve": 0,
                "citations_grounded": 0, "prose_judged": 0}, \
               ["report.md was never written"], ["prose_judged"]

    report = report_path.read_text(errors="replace")
    d["written"] = 4

    positions = [report.find(s) for s in REQUIRED_SECTIONS]
    present = [p >= 0 for p in positions]
    ordered = all(p >= 0 for p in positions) and positions == sorted(positions)
    d["structure"] = 5 if ordered else round(5 * sum(present) / len(present) * 0.6, 1)
    notes.append(f"sections {sum(present)}/{len(REQUIRED_SECTIONS)} present, "
                 f"order {'ok' if ordered else 'WRONG'}")

    words = len(report.split())
    d["length"] = 3 if words >= 350 else round(3 * words / 350, 1)
    notes.append(f"{words} words")

    body, _, sources_block = report.partition("## Sources")
    cited = {int(n) for n in re.findall(r"\[(\d{1,2})\]", body)}
    listed = {int(n) for n in re.findall(r"^\s*\[?(\d{1,2})[\].\)]\s", sources_block, re.M)}
    if cited:
        resolved = cited & listed
        d["citations_resolve"] = round(6 * len(resolved) / len(cited), 1)
        dangling = sorted(cited - listed)
        if dangling:
            notes.append(f"inline citations with no source entry: {dangling}")
    else:
        d["citations_resolve"] = 0
        notes.append("no inline citations at all")

    blob = "\n".join(results).lower()
    urls = _urls(sources_block)
    if urls:
        grounded = sum(1 for u in urls if u.lower().rstrip("/") in blob or _domain(u) in blob)
        d["citations_grounded"] = round(4 * grounded / len(urls), 1)
        if grounded < len(urls):
            notes.append(f"{len(urls) - grounded}/{len(urls)} source URLs appear in NO tool result — fabricated")
    else:
        d["citations_grounded"] = 0
        notes.append("Sources section contains no URLs")

    d["prose_judged"] = 0
    notes.append("prose quality: JUDGED — max 3, fill in by hand")
    return d, notes, ["prose_judged"]


SCORERS = {"t1": score_t1, "t2": score_t2, "t3": score_t3, "t4": score_t4}
MAX = {"t1": 25, "t2": 25, "t3": 25, "t4": 25}


def _rel(run: Path) -> str:
    """Path relative to this directory, so scores.json is portable.

    It used to store the absolute path, which baked the author's home directory into a
    file that gets committed and published — meaningless on anyone else's machine, and
    not something a published artefact should carry.
    """
    try:
        return str(run.resolve().relative_to(HERE))
    except ValueError:
        return run.name


def score_run(run: Path) -> dict:
    answer, meta, trace, results = _load(run)

    # No parseable meta.json: the run is unscoreable, which is NOT the same as scoring 0.
    # rank.sh writes into results/ while a roll-up may be reading it, so a directory can
    # be caught mid-write. Returning a 0 row here would let a half-written rep collapse
    # that model's pass^k total, inventing a reliability failure out of a race.
    if not meta:
        return None

    task = meta.get("task", run.name.split("_")[0])
    meta["_run_dir"] = str(run)

    if task not in SCORERS:
        # t0 gate probes and the parameter-isolation diagnostics live in the same tree but
        # are not part of the 100-point battery. Skip them rather than crashing the roll-up.
        return None

    rep = _rep_of(run)
    status = meta.get("status")

    # A run that produced no answer did not complete, whatever `status` says. Trusting the
    # field alone was wrong for 50 of the 135 scored runs in the banked campaign.
    #
    # `run_one.py` arms SIGALRM to raise RunTimeout, but `agentic/cli.py` catches bare
    # `Exception` around run_agent — a deliberate guard so one bad turn cannot kill a session —
    # so the timeout never reaches the harness. `status` stays "ok", `answer.txt` holds the six
    # characters "ERROR:", and this function used to score it as a completed run. It is scored
    # on the artifact, so a model that wrote report.md and then ran out of clock collected up to
    # 25/25: t4 blanks averaged 20.1 against 12.1 for runs that actually finished, which inverts
    # what the task measures. Under pass^k — the minimum across reps — that silently propped up
    # the ranking in §10.
    #
    # The root cause is fixed in run_one.py (RunTimeout now derives from BaseException, so the
    # catch-all cannot swallow it). This stays as well, and not merely as belt-and-braces: the
    # 168 banked runs are already on disk with `status: "ok"` and re-running them costs hours,
    # so the only way to re-score the existing campaign correctly is to detect the blank here.
    blank = not (answer or "").strip() or (answer or "").strip().startswith("ERROR")
    if status != "ok" or blank:
        why = status if status != "ok" else "timed out or crashed: no answer was produced"
        return {"run": _rel(run), "model": meta.get("model"), "task": task, "rep": rep,
                "status": "timeout" if blank and status == "ok" else status,
                "total": 0, "max": MAX.get(task, 25), "parts": {},
                "notes": [f"run did not complete: {why}"],
                "judged_pending": [], "seconds": meta.get("seconds"),
                "n_tool_calls": meta.get("n_tool_calls")}

    parts, notes, pending = SCORERS[task](answer, meta, trace, results)

    # Fold in the hand-scored items from judged.json, so the totals are complete and the
    # judgements stay reviewable in version control rather than living in someone's head.
    #
    # Lookup order is per-rep first, then the legacy model-level key. The legacy form
    # predates reps: it applies one hand score to every rep of a model, even though each
    # rep produced a different answer.txt. That is still honoured so the judgements made
    # before this change are not thrown away, but it is flagged in the notes, because an
    # inherited score is not evidence about the rep it is being applied to.
    jf = HERE / "judged.json"
    if jf.exists():
        judged = _read_json(jf, {})
        model = meta.get("model")
        for key in list(pending):
            table = judged.get(f"{task}.{key}", {})
            if not isinstance(table, dict):
                continue
            val = table.get(f"{model}#rep{rep}") if rep is not None else None
            if val is not None:
                parts[key] = val
                pending.remove(key)
                notes.append(f"{key} = {val} (manual, judged for this rep)")
                continue
            val = table.get(model)
            if val is not None:
                parts[key] = val
                pending.remove(key)
                notes.append(f"{key} = {val} (manual) — judged score inherited from "
                             f"legacy model-level key, not judged for this rep specifically")
    total = max(0, min(MAX[task], round(sum(parts.values()), 1)))
    return {"run": _rel(run), "model": meta.get("model"), "task": task, "rep": rep,
            "status": status, "total": total, "max": MAX[task], "parts": parts,
            "notes": notes, "judged_pending": pending, "seconds": meta.get("seconds"),
            "n_tool_calls": meta.get("n_tool_calls")}


TASK_ORDER = ["t1", "t2", "t3", "t4"]


def rollup(scored: list[dict]) -> list[dict]:
    """Aggregate the per-run scores into one pass^k row per (model, task).

    PLAN.md §1.3 follows tau-bench: reliability has to DECAY with repeats, so the
    headline number is the MINIMUM across reps, never the mean and never the best.
    A model that scores 25 on one rep and 0 on the next is not a 12.5 model, it is a
    0 model — you cannot build on something that only works sometimes. A rep that
    did not complete already scores 0 in score_run(), so a crash or a timeout in any
    rep collapses the pass^k total on its own, which is the intended behaviour.

    `mean_total` is carried for context and `spread` (max − min) because a pass^k of
    0 means two very different things at spread 0 (consistently bad) and at spread 25
    (bimodal, i.e. unreliable) — and that distinction is the entire point of reps.

    `provisional` is set when any contributing rep still owes a hand judgement. Such
    a total is a FLOOR, not a score: the unjudged item currently contributes 0, and
    filling in judged.json can only raise it. It must never be presented as final.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for s in scored:
        groups.setdefault((s["model"], s["task"]), []).append(s)

    rows = []
    for (model, task), runs in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        runs = sorted(runs, key=lambda r: (r.get("rep") or 0, r["run"]))
        totals = [r["total"] for r in runs]
        pending = sorted({f"{r['task']}.{k}#rep{r.get('rep')}"
                          for r in runs for k in r["judged_pending"]})
        rows.append({
            "model": model,
            "task": task,
            "max": runs[0]["max"],
            "n_reps": len(runs),
            "pass_k_total": min(totals),
            "mean_total": round(sum(totals) / len(totals), 2),
            "spread": round(max(totals) - min(totals), 1),
            "status_all_ok": all(r.get("status") == "ok" for r in runs),
            "provisional": bool(pending),
            "per_rep_totals": totals,
            "reps": [r.get("rep") for r in runs],
            "runs": [r["run"] for r in runs],
            "judged_pending": pending,
        })
    return rows


def rollup_by_model(rows: list[dict]) -> list[dict]:
    """Sum pass^k across t1..t4 into one ranked row per model.

    Summing minima is deliberately harsh: a model has to be reliable on every task to
    place well, which is the same principle as pass^k applied one level up.
    """
    per_model: dict[str, list[dict]] = {}
    for r in rows:
        per_model.setdefault(r["model"], []).append(r)

    out = []
    for model, rs in per_model.items():
        reps = sorted({r["n_reps"] for r in rs})
        out.append({
            "model": model,
            "pass_k_sum": round(sum(r["pass_k_total"] for r in rs), 1),
            "mean_sum": round(sum(r["mean_total"] for r in rs), 1),
            "max_possible": sum(r["max"] for r in rs),
            "tasks": sorted((r["task"] for r in rs), key=lambda t: TASK_ORDER.index(t)
                            if t in TASK_ORDER else 99),
            "n_tasks": len(rs),
            "n_reps": reps[0] if len(reps) == 1 else None,   # None => mixed across tasks
            "n_reps_range": reps,
            "status_all_ok": all(r["status_all_ok"] for r in rs),
            "provisional": any(r["provisional"] for r in rs),
            "per_task": {r["task"]: r["pass_k_total"] for r in rs},
        })
    return sorted(out, key=lambda r: -r["pass_k_sum"])


def _rep_marker(rows: list[dict]) -> tuple[int | None, str]:
    """The table's dominant rep count, and a legend line if anything differs from it."""
    counts: dict[int, int] = {}
    for r in rows:
        n = r["n_reps"]
        if n is not None:
            counts[n] = counts.get(n, 0) + 1
    if not counts:
        return None, ""
    dominant = max(counts, key=lambda k: (counts[k], k))
    odd = [r for r in rows if r["n_reps"] != dominant]
    if not odd:
        return dominant, ""
    return dominant, (
        f"\n  ‼ {len(odd)} row(s) marked ◆ have a rep count different from the "
        f"table's pass^{dominant}. Those rows are NOT comparable to the rest:\n"
        f"    a pass^1 score is a single observation, not a reliability measurement."
    )


def print_rollup(rows: list[dict], model_rows: list[dict]) -> None:
    print("\n\n=== pass^k by (model, task) — headline is the MIN across reps (PLAN.md §1.3) ===\n")
    dominant, legend = _rep_marker(rows)
    print(f"  {'model':48} {'task':4} {'k':>2} {'pass^k':>7} {'mean':>6} {'spread':>7}  per-rep")
    print(f"  {'-' * 48} {'-' * 4} {'--':>2} {'-' * 7} {'-' * 6} {'-' * 7}  {'-' * 12}")
    for r in rows:
        mark = "◆" if r["n_reps"] != dominant else " "
        flags = []
        if r["provisional"]:
            flags.append("PROVISIONAL")
        if not r["status_all_ok"]:
            flags.append("a rep did not complete")
        tail = ("  ← " + ", ".join(flags)) if flags else ""
        print(f"{mark} {str(r['model'])[:48]:48} {r['task']:4} {r['n_reps']:>2} "
              f"{r['pass_k_total']:>7} {r['mean_total']:>6} {r['spread']:>7}  "
              f"{r['per_rep_totals']}{tail}")
    if legend:
        print(legend)

    print("\n\n=== ranked by pass^k summed across t1..t4 ===\n")
    dom_m, legend_m = _rep_marker(model_rows)
    print(f"  {'#':>2} {'model':48} {'k':>3} {'pass^k sum':>11} {'mean sum':>9}  tasks")
    print(f"  {'--':>2} {'-' * 48} {'---':>3} {'-' * 11} {'-' * 9}  {'-' * 5}")
    for i, r in enumerate(model_rows, 1):
        mark = "◆" if r["n_reps"] != dom_m else " "
        k = str(r["n_reps"]) if r["n_reps"] is not None else "/".join(map(str, r["n_reps_range"]))
        tail = "  ← PROVISIONAL" if r["provisional"] else ""
        missing = "" if r["n_tasks"] == len(TASK_ORDER) else f"  (only {r['n_tasks']}/4 tasks)"
        print(f"{mark} {i:>2} {str(r['model'])[:48]:48} {k:>3} "
              f"{r['pass_k_sum']:>11} {r['mean_sum']:>9}  {r['n_tasks']}/4{tail}{missing}")
    if legend_m:
        print(legend_m)
    if any(r["provisional"] for r in model_rows):
        print("\n  PROVISIONAL = a contributing rep still owes a hand judgement. The unjudged\n"
              "  item scores 0 for now, so these totals are FLOORS and can only rise.")


def print_judgement_worklist(scored: list[dict]) -> None:
    """Every (task, item, model, rep) still needing a hand score, so the debt is visible."""
    owed = [(s["task"], key, s["model"], s.get("rep"), s["run"])
            for s in scored for key in s["judged_pending"]]
    print("\n\n=== hand-judgement worklist ===\n")
    if not owed:
        print("  none — every scored run has its judged items filled in.")
        return
    print(f"  {len(owed)} judgement(s) owed. Add them to judged.json under the per-rep key\n"
          f"  \"<model>#rep<n>\" (see _schema in that file); until then the totals above\n"
          f"  are floors, not scores.\n")
    print(f"  {'task.item':22} {'rep':>3}  {'model':44}  run")
    for task, key, model, rep, run in sorted(owed, key=lambda x: (x[0], x[1], str(x[2]), x[3] or 0)):
        print(f"  {task + '.' + key:22} {rep if rep is not None else '?':>3}  "
              f"{str(model)[:44]:44}  {run}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--all", action="store_true", help="score every run under path and roll up")
    args = ap.parse_args()
    root = Path(args.path).resolve()

    runs = sorted(p.parent for p in root.rglob("meta.json")) if args.all else [root]
    scored = [s for s in (score_run(r) for r in runs) if s is not None]

    # A directory whose meta.json will not parse is skipped rather than scored 0 (see
    # score_run). Say so out loud: silently dropping a run from a reliability table is
    # how a campaign ends up reporting pass^2 over one rep.
    unreadable = [r for r in runs
                  if (r / "meta.json").exists() and _read_json(r / "meta.json", None) is None]
    if unreadable:
        print(f"\n⚠ {len(unreadable)} run dir(s) have an unparseable meta.json and were "
              f"SKIPPED, not scored 0:")
        for r in unreadable:
            print(f"    {_rel(r)}")
        print("  If the campaign is still running these are simply half-written; re-run "
              "score.py when it finishes.")

    for s in scored:
        print(f"\n{s['model']}  [{s['task']}]  {s['total']}/{s['max']}   "
              f"{s['seconds']}s  {s['n_tool_calls']} tool calls")
        for k, v in s["parts"].items():
            print(f"    {k:22} {v:>6}")
        for n in s["notes"]:
            print(f"    · {n}")
        if s["judged_pending"]:
            print(f"    ⚠ awaiting manual judgement: {', '.join(s['judged_pending'])}")

    if args.all:
        (root / "scores.json").write_text(json.dumps(scored, indent=2))
        rows = rollup(scored)
        model_rows = rollup_by_model(rows)
        (root / "scores_rollup.json").write_text(json.dumps(
            {"by_model_task": rows, "by_model": model_rows}, indent=2))
        print_rollup(rows, model_rows)
        print_judgement_worklist(scored)
        print(f"\n\nwrote {root / 'scores.json'}  ({len(scored)} runs)")
        print(f"wrote {root / 'scores_rollup.json'}  "
              f"({len(rows)} model×task pairs, {len(model_rows)} models)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
