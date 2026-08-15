# Model ranking campaign: protocol

Ranks the locally installed Ollama models on the four things this agent is actually
used for: **reasoning**, **web search**, **complex agentic work**, and **report
writing**. The output is a decision aid for which models to keep and which to delete.

Written 2026-08-08. Nothing here runs until explicitly started.

---

## 1. Why this protocol looks the way it does

Public tool-use benchmarks were surveyed before designing this (BFCL, τ-bench,
T-Eval, ToolBench, MCP-Bench; plus the practitioner write-ups from promptquorum,
localaimaster, webscraft and the r/LocalLLaMA consensus). Four findings shaped the
design:

1. **Shortlist from public benchmarks, then test on your own tasks.** Every serious
   source says the same thing: leaderboard position does not predict behaviour
   inside a specific harness. So this campaign uses *this agent's real tools and
   real prompts*, not a synthetic function-calling suite.
2. **Hold the harness constant so failures attribute to the model.** promptquorum's
   methodology note, "same MCP client, same servers, same prompts", is the reason
   §3 pins every generation parameter and the context size. An unpinned `num_ctx`
   alone would have made a 262K-context model incomparable to a 128K one.
3. **`pass^k`, not best-of-k.** τ-bench's reliability metric *decays* with repeats:
   a model scores only if it passes *every* run. A model that succeeds once in three
   is not a model you can build on. Where repeats are affordable, that is the rule.

   This is now what the code actually computes. `score.py --all` groups runs by
   `(model, task)` and reports the **minimum** of the per-rep totals as
   `pass_k_total`, with `mean_total` and `spread` (max − min) alongside for context,
   and sums the minima across `t1..t4` into one ranked per-model table. A rep that crashed or
   timed out scores 0, so it collapses the pass^k total on its own. `rank.sh` defaults to
   `--reps 2`.

   > **That last sentence was false for the whole of the first campaign, and is true only as of
   > 2026-08-15.** A timed-out rep used to record `status: "ok"`, and `score.py` skipped only
   > runs whose status was *not* `ok`, so a run that produced nothing was scored on whatever
   > artifact it had left behind — up to 25/25. Both halves are now fixed (`RunTimeout` derives
   > from `BaseException` so the agent's catch-all cannot swallow it; `score.py` scores a blank
   > answer 0 regardless of status). Re-scoring the banked campaign on that basis moved **42 of
   > 135 runs** and cost fifteen of eighteen models points, the largest by 50. Full account in
   > the note under §3.

   > **Results produced before 2026-08-11 are `pass^1`.** They are single
   > observations, not reliability measurements, and are *not* directly comparable to
   > `pass^2` rows. The printed tables mark any row whose rep count differs from the
   > rest of the table with `◆` rather than letting the two silently mix.

   One caveat the metric cannot fix on its own: the two hand-judged items
   (`t1.d_judged`, `t4.prose_judged`) were originally keyed by model alone, so every
   rep of a model shared one judgement. `judged.json` now takes a per-rep key
   (`<model>#rep<n>`); the legacy model-only key still resolves, but any total
   relying on one is flagged as inherited, and any total with an unjudged item is
   reported `PROVISIONAL` — a floor that can only rise, never a final score.
4. **The function-calling configuration is part of the score, not a separable
   variable.** So §3 is reported alongside the results, and no per-model tuning is
   allowed, a model that needs a different temperature to work is a model that
   scores worse here.

Sources are listed at the bottom.

---

## 2. Candidates

`ollama show` capability check first, a model without a `tools` capability cannot
be scored on three of the four categories, so this is the entry gate.

| Model | Size | tools | In? |
|---|---|---|---|
| `oamazonasgabriel/qwen2.5-coder.1.5b-mlx:f16-8gbGPU` | 3.1 GB | yes | yes |
| `htunnthuthutech/gemma-4-e2b-aiops` | 3.4 GB | yes | yes |
| `qwen3.5:4b` | 3.4 GB | yes | yes |
| `gamy316/aileen1.0` | 4.9 GB | yes | yes |
| `lfm2.5:8b` | 5.2 GB | yes | yes |
| `MHKetbi/DeepSeek-R1-Distill-Llama-8B-NexaQuant` | 5.3 GB | yes | yes |
| `ornith:9b` | 5.6 GB | yes | yes |
| `hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M` | 5.6 GB | yes | yes |
| `studiobrn/modCoderMLX` | 7.4 GB | yes | yes |
| `jikepjikep_16HEX/gemma-4-12b-nightshift-heretic…` | 7.4 GB | yes | yes |
| `gemma4:12b-mlx` | 7.7 GB | yes | yes |
| `gpt-oss:20b` | 13.8 GB | yes | yes |
| `gemma4:26b-mlx` | 17.6 GB | yes | yes |
| `Agen/gemma-4-26B-A4B-it-uncensored-heretic` | 18.0 GB | yes | yes |
| `qwen3-coder:30b` | 18.6 GB | yes | yes |
| `rafw007/Qwen3.6-35B-A3B-mlx-claude-coder-abliterated` | 23.9 GB | yes | yes (heavy) |
| `charaf/Qwen3.6-27B-OBLITERATED-mlx-q8` | 28.6 GB | yes | yes (heavy) |
| `translategemma:27b` | 17.4 GB | no **no tools** | **excluded** |
| `bge-m3` | 1.2 GB | embedder | **excluded** |

**17 candidates.**

Three notes for the delete decision, independent of any score:

- **The two >20 GB models are measured, not assumed.** On-disk size says
  `charaf/Qwen3.6-27B-OBLITERATED-mlx-q8` (28.6 GB) exceeds this machine's total 24 GB
  of unified memory, and `rafw007/…-35B-A3B` (23.9 GB) leaves nothing for the OS. But
  their model cards claim a real working set below the on-disk figure, and for the A3B
  that is plausible: it is a **mixture-of-experts activating ~3B parameters per token**,
  so most of those weights are cold and can stay paged out without much cost. Guessing
  is pointless, so both run by default and the harness samples `vm.swapusage` either
  side of every run. A large swap delta, a timeout or a crash is then a **recorded
  result** that goes into the analysis, not a harness error. `--skip-heavy` drops them.
- `ornith:9b` and `hf.co/…/Ornith-1.0-9B-GGUF:Q4_K_M` are the same base model at the
  same size, different builds (different blob IDs). Both are tested; unless they
  diverge, one is 5.6 GB of redundancy.
- `translategemma:27b` cannot call tools at all, so it can never work as an agent
  model. It is only worth keeping if translation is a use case in its own right,
  that is a judgement call, not something this campaign can score.

---

## 3. Controls

Identical for every model, every run. No per-model tuning.

> **Corrected 2026-08-15.** Every numeric value in this table was wrong: it described the
> controls as first drafted on 2026-08-08 and was never updated when the `repeat_penalty`
> investigation (`RESULTS.md` §6) changed them. `RESULTS.md` line 5 has always stated the real
> values, so no published result is affected — but §1.4 of this document says the configuration
> "is reported alongside the results" and is "part of the score", which makes a controls table
> that describes a configuration never run the worst single error in this file. The values below
> are now read from `run_one.py::_pinned_params()`, which is the only place they actually live.

| Setting | Value | Why |
|---|---|---|
| `SAFE_NUM_CTX` | **32768** | Pinned. Otherwise a 262K model and a 128K model negotiate different windows and the comparison is meaningless. 32K leaves ~4x headroom over the measured bare-session prompt (~8,200 tokens: system prompt plus tool schemas) while costing half the KV cache of the 64K used interactively. No task here comes near it. |
| `GEN_TEMPERATURE` | **0.35** | Low, not zero. Agentic work rewards determinism, and high temperature adds variance that would swamp real differences across so few runs. This is a *measured* choice, not a tidy one: see `GEN_REPEAT_PENALTY` below for what happened when these were picked for looking deterministic rather than for working. Note `run_one.py` describes this as "the author's real interactive setting" — true when written and still the value `RESULTS.md` §6 recommends, but the live `~/.agentic_1a_params.json` now reads **0.2**, so the benchmark and the author's own session have drifted apart. The benchmark value is the one that matters for comparability; the comment is what is stale. |
| `GEN_TOP_P` | 0.95 | The author's real interactive setting, and still matches the live config. |
| `GEN_TOP_K` | 40 | The author's real interactive setting, and still matches the live config. |
| `GEN_REPEAT_PENALTY` | **1.15** | **The single most important control here, and it was missing from this table until 2026-08-15.** At 1.10, tool calling breaks: 2 successes out of 11, against 9 out of 9 at 1.15, with temperature, top_p, seed and context size each isolated and ruled out. Tool-call syntax is repetitive — braces, quotes, repeated keys — so too weak a penalty lets the sampler loop mid-JSON. This first appeared disguised as "these four models cannot call tools". Full account in `RESULTS.md` §6. **Do not lower it.** |
| `GEN_SEED` | **the rep number** (1, 2, …) | Not a fixed seed. A single seed across reps would make repeats near-identical samples, which would make any `pass^k` claim meaningless — the metric needs independent draws. Runs are still not fully reproducible, since tool results come from the live web. |
| `GEN_NUM_PREDICT` | **4096** | Comfortably above the longest expected answer (a ~350-word report plus reasoning). The ceiling exists to stop a degenerating model generating for hours, not to permit long output. |
| `STREAM_FINAL` | off | Headless mode forces this anyway. |
| Mode | **`--private`** | Critical. No session file, no audit log, no input history, **no persistent memory**. Runs cannot contaminate each other. This is exactly what `aileen1.0` did when it wrote a correction nudge into `.agentic/memory.md` and it would have poisoned every later run. |
| Project dir | fresh per run | Wiped and recreated. |
| Concurrency | **one model, ever** | `ollama stop` after every run, `ollama ps` asserted empty before the next starts. Enforced in the harness, not by discipline. |
| Timeout | **300 s (5 min)** hard cap | A run that exceeds it scores 0 and is not retried. A model that cannot finish these shortened tasks in 5 minutes is not usable for this workflow, so the slow ones cost 5 minutes instead of 9. **True only since 2026-08-15** — for the first campaign a timed-out run was scored on the artifact it had left behind, see the note below. |
| Cooldown | **8 s between runs** | Lets the GPU memory actually be released and gives the machine a moment to shed heat before the next load, rather than going straight from one 18 GB model into another. |
| Order | **lightest model first** | If the campaign is interrupted the cheap results are already banked, and the machine warms up gradually instead of starting at 18 GB. |
| Size limit | **20 GB, `--include-heavy` to override** | See §2. Loading a model bigger than RAM does not run slowly, it swaps. |

> ### The timeout scoring bug, found and fixed 2026-08-15
>
> For the whole of the first campaign, **a timed-out run was scored as if it had succeeded.**
> This section records it rather than quietly correcting the numbers, because the ranking in
> `RESULTS.md` was published on the strength of it.
>
> **The mechanism.** `run_one.py` arms `SIGALRM` to raise `RunTimeout`, but `agentic/cli.py`
> catches bare `Exception` around `run_agent` — a deliberate guard so one bad turn cannot kill an
> interactive session. It swallowed the deadline. `RunTimeout()` carries no message, so the agent
> printed "Unexpected error:" with nothing after it, returned normally, and the harness recorded
> `status: "ok"` on a run that had produced nothing. `score.py` skipped only runs whose status was
> *not* `ok`, so those runs were scored on whatever artifact they had left behind.
>
> **The scale.** 50 of the 135 scored runs were blank in exactly this way, and 42 of those 50
> scored above zero. (53 of all 168 run directories are blank; the other three are `t0` gate
> probes, which are pass/fail screens and never scored.)
>
> **Why it was not obviously wrong.** T3 and T4 are graded on the *artifact* — `game.py`,
> `report.md` — not on the answer text. A model that wrote the report and then ran out of clock
> really had produced the deliverable. The scoring was defensible; it just was not what this
> document said, and not what `pass^k` needs in order to mean anything. As measured before the fix:
>
> | task | blank runs | mean score when blank | mean when answered |
> |---|---|---|---|
> | T1 | 5 | **0.0** | 18.0 |
> | T2 | 3 | 4.7 | 20.0 |
> | T3 | 22 | 10.9 | 10.2 |
> | T4 | 20 | **20.1** | **12.1** |
>
> T1 behaved as documented. T4 inverted: a run that timed out scored nearly twice what a run that
> finished scored, because writing the report early and never returning beat returning with a weak
> one.
>
> **The fix, both halves.** `RunTimeout` now derives from `BaseException`, so no catch-all
> intercepts it — the same reason `KeyboardInterrupt` and `SystemExit` live there. And `score.py`
> scores a blank or `ERROR:` answer 0 regardless of `status`, which is what makes the *already
> banked* runs re-scorable: re-running 168 runs costs hours, and the fix to `run_one.py` cannot
> retroactively change what is on disk.
>
> **What it cost.** Re-scoring moved 42 of 135 runs; runs scoring zero went from 17 to 59;
> fifteen of eighteen models lost points. `qwen-heretic`, ranked first at 87.0 and described as
> "best agentic *and* best report score tested, both perfect on both reps", **timed out on all
> four of its T3 and T4 runs** — every one at the 300 s cap. Both of its 25/25s came from
> artifacts left by runs that never finished. It is now eleventh.
>
> **The shape of the error, which is the part worth keeping.** `status` honestly measured "the
> harness caught no exception" and was read as "the run produced an answer". `_grounding_check`'s
> "zero fabrications" was read as "the layer works" (`RESULTS.md` §2). `had_verification`'s "no
> verification tool ran" was read as "the model did not check its work" (`DESIGN.md` §4.2b). Three
> files, one habit: a signal that is honest about what it measures, read as a proxy for something
> adjacent. None of the three was a wrong measurement. All three were wrong readings.

**Config safety.** The harness never touches `~/.agentic_1a_params.json` or
`~/.agentic_1a_default_model.txt`. It writes a scratch params file inside the run
directory and points `config.PARAMS_FILE` at it before `main()` loads anything.
The real files are checksummed before and after the campaign and the harness aborts
if either changed. This is a direct response to the incident where a test rewrote
the real config and broke every model.

---

## 4. The four tasks

### T1: Reasoning (no tools) · `tasks/t1_reasoning.txt`

Four items with exactly checkable answers, none of them a memorized classic:

- **(a)** a four-variable scheduling constraint puzzle with a unique solution
- **(b)** an exponential-backoff sum, an off-by-one trap (255 s, not 256 or 511)
- **(c)** a character count across a compound word (deterministic, and a known
  weak spot for tokenizer-bound models)
- **(d)** one open item: name the flaw in a p50-latency claim, judged, weighted low

Scored automatically on (a), (c). **Calling any tool is a penalty**, reaching for
`search_web` on a logic puzzle is a discipline failure, and it is the single most
common way a small model wastes a turn.

### T2: Web search · `tasks/t2_websearch.txt`

Current-events roundup with hard structural requirements: **3 stories, 3 topics,
3 distinct outlets**, one sentence each, a URL per story, no aggregators. Shortened
from five stories, three is enough to expose whether a model diversifies its sources
and grounds its URLs, and it cuts both the search time and the generation length.

Almost entirely auto-gradeable, because the agent already instruments what is needed:

| Signal | How it's measured |
|---|---|
| Called `get_datetime` before searching | tool trace |
| Used `search_web_deep` (read pages) vs snippets only | tool trace |
| Story count / topic spread | parsed from the answer |
| Distinct source domains | parsed |
| **Citations grounded**, every URL really appears in a tool result | `state._last_turn_tool_results` |
| Duplicate event reported twice | the existing `_duplicate_items` check |
| Aggregator used as a primary source | domain blocklist |
| Honesty nudges fired | stderr trace — **not in `meta.json`**, see the note under §6 |

This is the task where the current default model has repeatedly failed by skipping
`get_datetime` and searching the wrong year, so it discriminates well.

### T3: Complex agentic · `tasks/t3_agentic.txt`

Reuses the existing `benchmarks/game_py_bugfix` fixture. Multi-step: read the file,
find real bugs, edit, **run the code to verify**. Graded by
`benchmarks/play_verify.py`, which exits 0/1, a genuinely binary outcome, no
rubric involved.

Sub-scores: bugs 1 and 2 fixed (the two real ones), `play_verify` PASS, and whether
the model actually executed the program rather than claiming it had.

The strongest test in the battery, because it cannot be passed by writing
convincing prose.

### T4: Report writing · `tasks/t4_report.txt`

Research a topic and write `report.md` with a mandated structure: **four** `##` sections
in a fixed order, **350-600 words**, every factual claim carrying an inline `[n]` citation
that resolves to a numbered URL. Trimmed from five sections and 600 words, the
structure-compliance and citation-grounding signals are unchanged, but the generation
is roughly half as long.

Auto-gradeable on: file written, all five sections present **and in order**, word
count, citation count, every `[n]` resolves, every URL grounded in a tool result,
no fabricated URLs. A small judged component covers whether the prose is actually
worth reading.

Topic is the 2025-26 npm supply-chain worm, recent enough to require real search,
and a subject where fabricated CVEs and dates are easy to spot.

---

## 5. Rounds

17 models × 4 tasks is still the bulk of the cost, so it stays tiered: a cheap gate
first, depth only on the survivors.

**Round 1, Gate.** All 17 models, one short tool-discipline probe each
(`tasks/t0_gate.txt`). Does it emit a well-formed tool call at all, and chain two of
them? A model that fails this cannot be scored on T2, T4 and is eliminated. With 17
candidates and several untested newcomers, and this is where most of the saving comes
from. *≈25-35 min.*

**Round 2, Battery.** Survivors only, all four tasks, **2 reps by default** (`rank.sh` sets
`REPS=2`; this paragraph said "1 rep by default" until 2026-08-15, contradicting §1.3 on the
same page — §1.3 was the correct one, since `pass^k` cannot be computed from a single rep).
- `--reps 1`: **≈1.5-2 h.** No longer the default. The shorter tasks and the 5-minute cap
  make a single pass affordable enough to be the normal choice.
- `--reps 2`: ≈3-4 h. Worth it only for the models still in contention at the end.

**Round 3, Tiebreak.** Rather than paying for a second rep across the board, re-run
just the top 3-4 models on the contested tasks:
`bash rank.sh battery --reps 2 --tasks t2,t3` with `survivors.txt` cut down to the
finalists. *≈30-45 min.* This is where the `pass^k` rule actually gets applied, and
it is the cheapest place to buy it.

Everything runs in the foreground, one call per run, heavy models get killed as
background tasks on this machine.

## 6. Scoring

100 points, 25 per category, as the four categories were named as equals.
`score.py` computes everything except the two judged items, which are entered by
hand.

| Category | Points | Breakdown |
|---|---|---|
| **Reasoning** (T1) | 25 | 9 for (a), 2.25 per correct pairing · 6 (b) · 6 (c) · 4 (d, judged) · −3 per unnecessary tool call |
| **Web search** (T2) | 25 | 5 `get_datetime` first · 4 `search_web_deep` · 5 story count (target 3) · 4 domain diversity (target 3) · 7 citations grounded · −4 duplicate event · −3 aggregator source |
| **Agentic** (T3) | 25 | 10 `play_verify` PASS · 6 bug 1 · 6 bug 2 · 3 actually ran the code |
| **Report** (T4) | 25 | 4 file written · 5 structure exact (4 sections, in order) · 3 word count (≥350) · 6 citations resolve · 4 citations grounded · 3 judged prose quality |

With `--reps ≥ 2` — now the default — the reported score is the **minimum** across
reps (`pass^k`), and the mean is recorded alongside so flakiness is visible rather
than hidden. At `--reps 1` no `pass^k` claim can be made at all; that is the price of
the cheaper campaign, and it is why every pre-2026-08-11 row is `pass^1`.

Also recorded per run, unscored but reported: wall-clock seconds, tool-call count and
peak RSS (plus swap delta either side of the run). Speed does not enter the score. It is a
separate axis the size column already hints at, but a model that is twice as good and four
times slower is a different recommendation, and the table should show that.

> **"Nudges fired" is not recorded, despite this paragraph and the §4 T2 table both listing
> it** — corrected 2026-08-15. `meta.json` carries no such field, so the only way to count a
> nudge after the fact is to grep `trace.log` for the exact UI string, which is what had to be
> done to establish that `_grounding_check` never fired (`RESULTS.md` §2). It is a genuinely
> useful signal and cheap to add — `run_agent` already increments a counter per nudge type —
> but until it is in `meta.json` this document should not claim it is captured.

---

## 7. Known limits of this campaign

Stated up front, in the spirit of the rest of this repo's benchmark write-ups:

- **One machine, one quantization tier.** Results are about *these builds on this
  M-series 24 GB Mac*, not about the underlying models in general. This cuts hardest
  for the two >20 GB models: a poor score from them is evidence about *this machine*,
  not about the model.
- **One rep is not a reliability measurement.** A single run tells you what a model
  did once. During harness validation `qwen3.5:4b` answered the same arithmetic item
  correctly on one run and gave nonsense on the next, with an identical seed, a
  6-point swing from nothing but sampling. Treat any two models within ~6 points as
  tied until Round 3 separates them.
- **The tasks were shortened to fit the hardware.** Three stories instead of five, a
  350-word report instead of 600. This tests the same behaviours (grounding, source
  diversity, structure compliance) but says less about stamina on long outputs.
- **T2 and T4 hit the live web,** so the difficulty is not identical across runs.
  This is unavoidable for a web-search benchmark and is why grounding is scored
  rather than factual correctness.
- **Pinning `num_ctx` to 32K disadvantages nothing measured here** (no task needs a
  long context) but does mean this says nothing about long-context ability.
- **Four tasks is a narrow slice.** It covers what this agent is used for, which is
  the point, but it is not a general capability ranking.

---

## Sources

- [Tool-Use Benchmarks 2026: BFCL, T-Eval, ToolBench, Tau-Bench Compared](https://benchmarkingagents.com/best-benchmarks-for-tool-use/)
- [Best Local Models for Tool Calling in 2026: Benchmarks & Methodology](https://www.promptquorum.com/power-local-llm/best-local-models-tool-calling-2026)
- [Best Ollama Model for Tool Calling Agent 2026](https://webscraft.org/blog/yaku-model-ollama-obrati-dlya-agenta-z-tool-calling-porivnyannya-i-benchmarki?lang=en)
- [Best Ollama Models for AI Agents 2026: 9 Tested & Ranked](https://localaimaster.com/blog/best-ollama-models-for-agents)
- [r/LocalLLaMA is the real benchmark of LLM usability](https://aashaysachdeva.substack.com/p/rlocalllama-is-the-real-benchmark)
- [AI Benchmarks 2026: Compare 300+ LLM Benchmarks](https://llm-stats.com/benchmarks)
