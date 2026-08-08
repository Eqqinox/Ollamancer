#!/usr/bin/env python3
"""Score one run directory produced by run_one.py.

Every check here is deterministic and re-runnable from the artefacts on disk, so a
score can be audited afterwards rather than taken on trust. The two judged items
(T1d and T4 prose quality) are left at 0 and filled in by hand — they are flagged
in the output as `judged_pending` so they cannot be silently forgotten.

    python3 score.py results/qwen3.5_4b/t1_rep1
    python3 score.py --all results/          # rolls everything up into a table
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


def _load(run: Path) -> tuple[str, dict, list, list]:
    answer = (run / "answer.txt").read_text(errors="replace") if (run / "answer.txt").exists() else ""
    meta = json.loads((run / "meta.json").read_text()) if (run / "meta.json").exists() else {}
    trace = json.loads((run / "tool_trace.json").read_text()) if (run / "tool_trace.json").exists() else []
    # Grounding evidence: prefer the full per-call capture. `tool_results.json` (from
    # state._last_turn_tool_results) only ever holds the final ReAct round, so on its own
    # it makes a model that cited real URLs early in the run look like a fabricator.
    outs = (run / "tool_outputs.json")
    if outs.exists():
        results = [o["output"] for o in json.loads(outs.read_text())]
    else:
        rf = run / "tool_results.json"
        results = json.loads(rf.read_text()) if rf.exists() else []
    return answer, meta, trace, results


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
    task = meta.get("task", run.name.split("_")[0])
    meta["_run_dir"] = str(run)

    if task not in SCORERS:
        # t0 gate probes and the parameter-isolation diagnostics live in the same tree but
        # are not part of the 100-point battery. Skip them rather than crashing the roll-up.
        return None

    if meta.get("status") != "ok":
        return {"run": _rel(run), "model": meta.get("model"), "task": task,
                "total": 0, "max": MAX.get(task, 25), "parts": {},
                "notes": [f"run did not complete: {meta.get('status')}"],
                "judged_pending": [], "seconds": meta.get("seconds"),
                "n_tool_calls": meta.get("n_tool_calls")}

    parts, notes, pending = SCORERS[task](answer, meta, trace, results)

    # Fold in the hand-scored items from judged.json, so the totals are complete and the
    # judgements stay reviewable in version control rather than living in someone's head.
    jf = HERE / "judged.json"
    if jf.exists():
        judged = json.loads(jf.read_text())
        for key in list(pending):
            val = judged.get(f"{task}.{key}", {}).get(meta.get("model"))
            if val is not None:
                parts[key] = val
                pending.remove(key)
                notes.append(f"{key} = {val} (manual, see judged.json)")
    total = max(0, min(MAX[task], round(sum(parts.values()), 1)))
    return {"run": _rel(run), "model": meta.get("model"), "task": task,
            "total": total, "max": MAX[task], "parts": parts, "notes": notes,
            "judged_pending": pending, "seconds": meta.get("seconds"),
            "n_tool_calls": meta.get("n_tool_calls")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--all", action="store_true", help="score every run under path and roll up")
    args = ap.parse_args()
    root = Path(args.path).resolve()

    runs = sorted(p.parent for p in root.rglob("meta.json")) if args.all else [root]
    scored = [s for s in (score_run(r) for r in runs) if s is not None]

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
        print(f"\nwrote {root / 'scores.json'}  ({len(scored)} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
