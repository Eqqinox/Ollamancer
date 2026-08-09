#!/usr/bin/env python3
"""Repeat-action playthrough harness for the game_py_bugfix fixture (Ollamancer benchmark B10).

Why this exists
---------------
The dungeon-crawler fixture has no "quit" action — it only ends when the player dies — and its
prompts are dynamic (the [1..5] menu, plus a conditional y/n "descend" prompt after action 4).
Hand-piping a fixed stdin script therefore constantly misaligns and dies with an EOFError the
moment the game asks for one more line than the script provided. That EOFError twice hijacked the
v2.9.24 search-web nudge during model tests (it looked like a recurring "bug" but was just the
exhausted pipe). This harness makes the playthrough deterministic and classifies outcomes honestly:

  * every menu action (1 Attack, 2 Heal, 3 Use Item, 4 Go Deeper, 5 Info) is exercised >= 3 times;
  * a hang (e.g. the Heal-enters-combat infinite loop, bug 4) is caught as a TIMEOUT failure;
  * a real crash (any traceback whose final exception is NOT EOFError) is a CRASH failure;
  * running out of scripted input (final exception IS EOFError) is treated as a benign, expected
    end for this quit-less game — NOT a failure.

Usage
-----
    python3 benchmarks/play_verify.py [path/to/game.py] [--timeout SECONDS]

Defaults to the reference solution next to this file (which should PASS). Point it at a model's
attempt to score that attempt. Exit code 0 = pass, 1 = fail (crash / timeout / missing action).
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_GAME = HERE / "game_py_bugfix_reference_solution.py"

# Character pick, then each action >= 3x (each "4" is followed by "n" to answer the descend
# sub-prompt), then a run of attacks to push toward a natural death / end of input.
INPUT_LINES = (
    ["1"]                              # choose_character
    + ["5", "5", "5"]                  # Info x3
    + ["3", "3", "3"]                  # Use Item x3
    + ["2", "2", "2"]                  # Heal x3
    + ["4", "n", "4", "n", "4", "n"]   # Go Deeper x3 (decline descent each time)
    + ["1"] * 30                       # Attack until death or input runs out
)

# stdout markers proving each action actually ran (shared by original + reference).
ACTION_MARKERS = {
    "5 Info":     [r"adventurer\."],
    "3 Use Item": [r"Picked up", r"Used ", r"Health potion heals", r"Health Potion"],
    "2 Heal":     [r"rest and heal"],
    "4 Go Deeper":[r"Descend to the next floor"],
    "1 Attack":   [r"You fight the"],
}

_EXC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Interrupt))\b", re.MULTILINE)


def run_playthrough(game_path: Path, timeout: float = 15.0) -> dict:
    """Drive the game once with the scripted input. Returns a report dict."""
    stdin_data = "\n".join(INPUT_LINES) + "\n"
    report = {"game": str(game_path), "outcome": None, "detail": "", "counts": {}, "passed": False}
    try:
        proc = subprocess.run(
            [sys.executable, str(game_path)],
            input=stdin_data, capture_output=True, text=True, timeout=timeout,
        )
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        report["outcome"] = "TIMEOUT"
        report["detail"] = (f"No exit within {timeout}s — likely an infinite loop "
                             f"(e.g. an action that enters combat but never resolves).")
        report["counts"] = _count_actions(e.stdout or "")
        return report

    report["counts"] = _count_actions(stdout)

    excs = _EXC_RE.findall(stderr)
    if excs and excs[-1] != "EOFError":
        report["outcome"] = "CRASH"
        report["detail"] = f"Uncaught {excs[-1]} (last of {len(excs)} exception line(s))."
    elif excs and excs[-1] == "EOFError":
        report["outcome"] = "OK (input exhausted)"
        report["detail"] = ("Game asked for more input than the script provided — expected for "
                            "this quit-less game; not a crash.")
    else:
        report["outcome"] = f"OK (clean exit, rc={rc})"
        report["detail"] = "Game ended on its own (player death / game over)."

    missing = [a for a, pats in ACTION_MARKERS.items() if report["counts"].get(a, 0) < 3]
    no_crash_no_hang = report["outcome"].startswith("OK")
    report["passed"] = no_crash_no_hang and not missing
    if missing:
        report["detail"] += f"  Actions not exercised >=3x: {', '.join(missing)}."
    return report


def _count_actions(stdout: str) -> dict:
    counts = {}
    for action, patterns in ACTION_MARKERS.items():
        counts[action] = sum(len(re.findall(p, stdout)) for p in patterns)
    return counts


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    timeout = 15.0
    if "--timeout" in argv:
        i = argv.index("--timeout")
        timeout = float(argv[i + 1])
        del argv[i:i + 2]
    game = Path(argv[0]).expanduser().resolve() if argv else DEFAULT_GAME
    if not game.exists():
        print(f"Game file not found: {game}")
        return 2

    report = run_playthrough(game, timeout=timeout)
    print(f"▶ Playthrough: {report['game']}")
    print(f"  Outcome: {report['outcome']}")
    print(f"  {report['detail']}")
    print("  Actions exercised (need >=3 each):")
    for action in ACTION_MARKERS:
        n = report["counts"].get(action, 0)
        print(f"    {'✅' if n >= 3 else '❌'} {action:<12} {n}x")
    print(f"  RESULT: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
