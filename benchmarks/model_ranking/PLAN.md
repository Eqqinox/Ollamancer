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
   and sums the minima across `t1..t4` into one ranked per-model table. A rep that
   crashed or timed out already scores 0, so it collapses the pass^k total on its
   own. `rank.sh` therefore defaults to `--reps 2`.

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

| Setting | Value | Why |
|---|---|---|
| `SAFE_NUM_CTX` | **16384** | Pinned, and deliberately small. Otherwise a 262K model and a 128K model negotiate different windows and the comparison is meaningless. The KV cache is the part of the footprint that scales with this, so 16K rather than 32K is the single biggest memory saving available, and it matters most for the 17-18 GB models closest to the edge. No task here comes near 16K. |
| `GEN_TEMPERATURE` | **0.3** | Low, not zero. Agentic work rewards determinism; 0.8 (the interactive default) adds variance that would swamp real differences across so few runs. |
| `GEN_TOP_P` | 0.9 | Project default, unchanged. |
| `GEN_SEED` | **42** | Fixed. Cuts variance. Does *not* make runs fully reproducible, tool results come from the live web, but removes one source. |
| `GEN_NUM_PREDICT` | **2048** | Comfortably above the longest expected answer (a ~350-word report plus reasoning). The ceiling exists to stop a degenerating model generating for hours, not to permit long output. |
| `STREAM_FINAL` | off | Headless mode forces this anyway. |
| Mode | **`--private`** | Critical. No session file, no audit log, no input history, **no persistent memory**. Runs cannot contaminate each other. This is exactly what `aileen1.0` did when it wrote a correction nudge into `.agentic/memory.md` and it would have poisoned every later run. |
| Project dir | fresh per run | Wiped and recreated. |
| Concurrency | **one model, ever** | `ollama stop` after every run, `ollama ps` asserted empty before the next starts. Enforced in the harness, not by discipline. |
| Timeout | **300 s (5 min)** hard cap | A run that exceeds it is scored as a failure, not retried. A model that cannot finish these shortened tasks in 5 minutes is not usable for this workflow, so the slow ones cost 5 minutes instead of 9. |
| Cooldown | **8 s between runs** | Lets the GPU memory actually be released and gives the machine a moment to shed heat before the next load, rather than going straight from one 18 GB model into another. |
| Order | **lightest model first** | If the campaign is interrupted the cheap results are already banked, and the machine warms up gradually instead of starting at 18 GB. |
| Size limit | **20 GB, `--include-heavy` to override** | See §2. Loading a model bigger than RAM does not run slowly, it swaps. |

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
| Honesty nudges fired | stderr trace |

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

**Round 2, Battery.** Survivors only, all four tasks, **1 rep by default**.
- `--reps 1`: **≈1.5-2 h, the default now.** The shorter tasks and the 5-minute cap
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

Also recorded per run, unscored but reported: wall-clock seconds, tool-call count,
nudges fired, peak RSS. Speed does not enter the score. It is a separate axis the
size column already hints at, but a model that is twice as good and four times
slower is a different recommendation, and the table should show that.

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
