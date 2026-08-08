#!/usr/bin/env python3
"""Run ONE task against ONE model, in full isolation, and record everything.

This is the only place the ranking campaign talks to the agent. It deliberately does
not shell out to `agent.py`: it imports the package and patches `config` *before*
`cli.main()` reads anything, which is what lets it

  * pin every generation parameter identically for all models (see PLAN.md §3), and
  * guarantee the run cannot touch the user's real `~/.agentic_1a_*` files —
    every config path is redirected into the run directory first.

That second point is not paranoia. A test once wrote the real params file and left
every setting one step off, which silently broke the user's models until it was
traced back. Redirecting the paths makes that failure mode unreachable rather than
merely unlikely.

Usage (normally driven by rank.sh, not by hand):

    python3 run_one.py --model qwen3.5:4b --task t1 --outdir results/qwen3.5_4b/t1_rep1
"""

import argparse
import json
import os
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))


class RunTimeout(Exception):
    pass


def _swap_mb() -> float:
    """Swap currently in use, in MB.

    Recorded either side of a run so that "this model does not fit" becomes a measured
    claim rather than an impression. Several of the large MLX builds advertise a real
    working set well below their on-disk size (an A3B mixture-of-experts activates ~3B
    parameters per token), so the only honest way to settle it is to run them and watch
    whether the machine starts paging.
    """
    try:
        out = subprocess.run(["sysctl", "-n", "vm.swapusage"],
                             capture_output=True, text=True, timeout=5).stdout
        # Note the comma: sysctl formats these using the system locale, so on a
        # French-locale Mac this reads "used = 4994,44M", not "4994.44M".
        m = re.search(r"used\s*=\s*([\d.,]+)([MGK])", out)
        if not m:
            return -1.0
        val = float(m.group(1).replace(",", "."))
        return {"K": val / 1024, "M": val, "G": val * 1024}[m.group(2)]
    except Exception:                                          # noqa: BLE001
        return -1.0


_OVERRIDES: dict = {}
_SEED = 1


def _pinned_params() -> dict:
    """The controls from PLAN.md §3. Identical for every model — no per-model tuning."""
    return dict({
        # 32K. Measured: a bare session's prompt (system prompt + 34 tool schemas) is
        # ~8,200 tokens, so this leaves ~4x headroom while costing half the KV cache of
        # the 64K the author runs interactively.
        "SAFE_NUM_CTX": 32768,
        # These four are the author's real interactive settings, deliberately. An earlier
        # version of this file pinned temp 0.3 / top_p 0.9 / repeat_penalty 1.1 "for
        # determinism" and that control set MANUFACTURED FAILURES: at repeat_penalty 1.1,
        # qwen3.5:4b emitted malformed tool calls in 9 runs out of 11; at 1.15, changing
        # nothing else, it passed 9 out of 9. Temperature, top_p, seed and num_ctx were
        # each isolated and ruled out. Benchmark the configuration people actually run.
        "GEN_TEMPERATURE": 0.35,
        "GEN_TOP_P": 0.95,
        "GEN_TOP_K": 40,
        "GEN_REPEAT_PENALTY": 1.15,
        # Varies per rep (rep1 -> 1, rep2 -> 2). A single fixed seed would make repeats
        # near-identical samples, which would make any pass^k claim meaningless.
        "GEN_SEED": _SEED,
        "GEN_NUM_PREDICT": 4096,
        "STREAM_FINAL": "off",
    }, **_OVERRIDES)


def _isolate_config(cfg, run_dir: Path, model: str) -> None:
    """Point every persisted path at run_dir, so the real config is untouchable."""
    scratch = run_dir / "config"
    scratch.mkdir(parents=True, exist_ok=True)

    params_file = scratch / "params.json"
    params_file.write_text(json.dumps(_pinned_params(), indent=2))

    cfg.PARAMS_FILE = params_file
    cfg.HISTORY_FILE = scratch / "history"
    cfg.MODELS_CONFIG_FILE = scratch / "models.json"      # no failover/architect/vision model
    cfg.SKILLS_GLOBAL_DIR = scratch / "skills"            # no user skills leaking in
    cfg.DEFAULT_MODEL_FILE = scratch / "default_model.txt"  # absent -> falls back to DEFAULT_MODEL
    cfg.DEFAULT_MODEL = model

    # MCP off. Not just for speed: the user's real ~/.agentic_1a_mcp.json adds ~25 extra
    # tools to what the model is offered, and "how well does it cope with a 60-tool list"
    # is a different question from the one being asked. Every model must see the same 34.
    cfg.MCP_CONFIG_FILE = scratch / "mcp.json"


def _instrument_tools(tools_mod, trace: list, outputs: list) -> None:
    """Wrap every tool so we get a call trace, without changing what the model sees.

    Ollama's tool schemas are generated from `TOOLS` (the function objects); the loop
    dispatches through the `TOOL_MAP` dict. Rewriting the dict's values in place
    therefore records calls while leaving the advertised schema byte-identical — the
    model cannot tell it is being measured.

    It also captures every tool's OUTPUT into `outputs`. That is the only reliable
    grounding evidence: `state._last_turn_tool_results` holds just the final ReAct
    round, so on a task that ends by writing a file (T4) the earlier search results are
    gone by the time the run finishes — which made a model that cited five real URLs
    look like it had fabricated all five.
    """
    for name, fn in list(tools_mod.TOOL_MAP.items()):
        def make(name=name, fn=fn):
            def wrapper(*a, **kw):
                t0 = time.time()
                entry = {"tool": name,
                         "args": {k: str(v)[:300] for k, v in kw.items()},
                         "ok": False, "result_len": 0, "seconds": 0.0}
                trace.append(entry)
                try:
                    out = fn(*a, **kw)
                except Exception as exc:                       # noqa: BLE001
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                    raise
                else:
                    entry["ok"] = True
                    text = str(out)
                    entry["result_len"] = len(text)
                    outputs.append({"tool": name, "output": text[:40000]})
                    return out
                finally:
                    entry["seconds"] = round(time.time() - t0, 2)
            return wrapper
        tools_mod.TOOL_MAP[name] = make()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True, help="t0 | t1 | t2 | t3 | t4")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--timeout", type=int, default=540)
    ap.add_argument("--seed", type=int, default=1,
                    help="generation seed; rank.sh passes the rep number so repeats are "
                         "independent samples rather than the same one twice")
    ap.add_argument("--param", action="append", default=[],
                    help="override a pinned param for diagnostics, e.g. --param GEN_TEMPERATURE=0.8. "
                         "Recorded in meta.json so an overridden run can never be mistaken for a "
                         "campaign run.")
    args = ap.parse_args()

    global _OVERRIDES, _SEED
    _SEED = args.seed
    for kv in args.param:
        k, _, v = kv.partition("=")
        _OVERRIDES[k] = json.loads(v) if v[:1] in "0123456789-[{\"" else v

    out = Path(args.outdir).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # Fresh, empty project folder for this run. Nothing carries over between runs.
    project = out / "project"
    project.mkdir()

    task_file = next(HERE.glob(f"tasks/{args.task}_*.txt"))
    prompt = task_file.read_text().strip()

    # T3 needs the buggy fixture in place; T0 needs a couple of files to count.
    if args.task == "t3":
        shutil.copy(REPO / "benchmarks/game_py_bugfix_original.py", project / "game.py")
    elif args.task == "t0":
        (project / "alpha.txt").write_text("a\n")
        (project / "beta.txt").write_text("b\n")

    from agentic import config as cfg
    _isolate_config(cfg, out, args.model)

    from agentic import tools as tools_mod
    trace: list = []
    outputs: list = []
    _instrument_tools(tools_mod, trace, outputs)

    from agentic import cli, state

    sys.argv = ["agent.py", str(project), "--private", "--run", prompt]

    def _on_alarm(signum, frame):
        raise RunTimeout()

    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(args.timeout)

    answer_path = out / "answer.txt"
    stderr_path = out / "trace.log"

    swap_before = _swap_mb()
    t0 = time.time()
    status = "ok"
    real_stdout, real_stderr = sys.stdout, sys.stderr
    try:
        with open(answer_path, "w") as so, open(stderr_path, "w") as se:
            sys.stdout, sys.stderr = so, se
            try:
                cli.main()
            except SystemExit:
                pass          # headless main() exits with the task's success code
    except RunTimeout:
        status = "timeout"
    except KeyboardInterrupt:
        status = "interrupted"
    except Exception as exc:                                   # noqa: BLE001
        status = f"crash: {type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        sys.stdout, sys.stderr = real_stdout, real_stderr

    elapsed = round(time.time() - t0, 1)
    swap_after = _swap_mb()

    # `state` is still live in this process, so the grounding evidence the agent
    # already collects can be read straight off it, no reparsing of the transcript.
    try:
        tool_results = [str(r)[:20000] for r in state._last_turn_tool_results]
    except Exception:                                          # noqa: BLE001
        tool_results = []

    meta = {
        "model": args.model,
        "task": args.task,
        "status": status,
        "seconds": elapsed,
        "timeout": args.timeout,
        "tool_calls": [t["tool"] for t in trace],
        "n_tool_calls": len(trace),
        "prompt_tokens": getattr(state, "_LAST_PROMPT_TOKENS", None),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1 << 20), 1),
        "swap_before_mb": swap_before,
        "swap_after_mb": swap_after,
        "swap_delta_mb": round(swap_after - swap_before, 1) if swap_before >= 0 else None,
        "params": _pinned_params(),
        "param_overrides": dict(_OVERRIDES) or None,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    (out / "tool_trace.json").write_text(json.dumps(trace, indent=2))
    (out / "tool_results.json").write_text(json.dumps(tool_results, indent=2))
    (out / "tool_outputs.json").write_text(json.dumps(outputs, indent=2))

    # T3/T4 artefacts the scorer needs, lifted out before the project dir is reused.
    for artefact in ("game.py", "report.md"):
        src = project / artefact
        if src.exists():
            shutil.copy(src, out / artefact)

    swap_note = ""
    if swap_before >= 0 and swap_after - swap_before > 512:
        swap_note = f"  ⚠ swap +{round(swap_after - swap_before)}MB"
    print(f"{args.model}  {args.task}  {status}  {elapsed}s  "
          f"{len(trace)} tool calls{swap_note}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
