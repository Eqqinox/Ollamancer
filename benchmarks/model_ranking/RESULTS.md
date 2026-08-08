# Agentic_1A: Local Model Ranking

**Machine:** MacBook, Apple Silicon, 24 GB unified memory · **Date:** 8 August 2026
**Harness:** Agentic_1A OSS, 34 native tools, MCP disabled, `--private` mode
**Parameters (identical for every model):** temp 0.35 · top_p 0.95 · top_k 40 · **repeat_penalty 1.15** · num_ctx 32768 · num_predict 4096
**Scale:** 100 points = 4 tasks x 25 · 1 run per model per task · 5-minute hard cap per run

---

## 1. All-Purpose Ranking

| Rank | Model | Size | Reasoning | Search | Agentic | Report | **Total** |
|---|---|---|---|---|---|---|---|
| 1 | **gemma4:12b-mlx** | 7.7 GB | 25 | 20.7 | **25** | 24.5 | **95.2** |
| 2 | **gpt-oss:20b** | 13 GB | 19 | 19 | 12 | **25** | **75.0** |
| 3 | **Ornith-1.0-9B-GGUF** | 5.6 GB | 25 | 17 | 6 | 22.8 | **70.8** |
| 4 | qwen3.5:4b | 3.4 GB | 12 | **25** | 9 | 23.9 | 69.9 |
| 5 | gemma-4-12b-nightshift-heretic | 7.4 GB | 0 | **25** | 15 | 23.9 | 63.9 |
| 6 | Agen/gemma-4-26B-heretic | 17 GB | 25 | **25** | 9 | 0 | 59.0 |
| 7 | gemma4:26b-mlx | 17 GB | 25 | 22 | 9 | 0 | 56.0 |
| 8 | ornith:9b | 5.6 GB | 0 | 19 | 6 | **25** | 50.0 |
| 9 | gamy316/aileen1.0 | 4.9 GB | 13.8 | 14.3 | 6 | 0 | 34.1 |
| 10 | lfm2.5:8b | 5.2 GB | 0 | 17 | 9 | 0 | 26.0 |

> **The verdict is not close.** `gemma4:12b-mlx` wins by 20 points and is the **only model of
> ten that actually fixed the broken program**. Every other model claimed success while
> leaving a crash in place. At 7.7 GB it also leaves you 16 GB of headroom.

### Reliability, the column that decides daily use

| Model | Timeouts (of 4) | Swap caused | Total time |
|---|---|---|---|
| **gpt-oss:20b** | **0** | **0 MB** | **492 s**, the fastest that also scores well |
| gamy316/aileen1.0 | 0 | 0 MB | 189 s, fastest overall, but the weakest answers |
| lfm2.5:8b | 0 | 0 MB | 482 s |
| qwen3.5:4b | 1 | 0 MB | 663 s |
| gemma4:12b-mlx | 1 | 7.9 GB | 805 s |
| Ornith-1.0-9B-GGUF | 2 | 0 MB | 887 s |
| Agen/gemma-4-26B | 2 | 8.7 GB | 1166 s |
| gemma4:26b-mlx | 2 | **13.2 GB** | 935 s |
| **ornith:9b** | **3** | 0 MB | 999 s |
| gemma-4-12b-heretic | **3** | 0 MB | 1076 s |

> **Warning:** `ornith:9b` was the default at the time of the run and it timed out on 3 of 4
> tasks. It should not be anyone's default.
>
> **Warning:** the two 17 GB models are not viable on 24 GB. `gemma4:26b-mlx` alone pushed
> **13.2 GB** into swap. That is SSD wear in exchange for scores *below* a 7.7 GB model.

---

## 2. Search Ranking

*Scored on: calling `get_datetime` before searching · reading pages rather than snippets ·
story count · outlet diversity · every URL verified against real tool output · no aggregators ·
no duplicated events.*

| Rank | Model | Score | Notes |
|---|---|---|---|
| 1 | **qwen3.5:4b** | **25/25** | Perfect. Dated first, deep-read, 3 outlets, all URLs real |
| 1 | **gemma-4-12b-nightshift-heretic** | **25/25** | Perfect, same profile |
| 1 | **Agen/gemma-4-26B-heretic** | **25/25** | Perfect, but 17 GB and 8.7 GB of swap to get there |
| 4 | gemma4:26b-mlx | 22 | Used snippets, did not deep-read |
| 5 | gemma4:12b-mlx | 20.7 | Snippets only, and 2 of 3 stories from the same outlet |
| 6 | gpt-oss:20b | 19 | Deep-read properly, but found only **2 stories from 1 outlet** |
| 6 | ornith:9b | 19 | Searched *before* checking the date |
| 8 | Ornith-1.0-9B-GGUF | 17 | Never called `get_datetime` |
| 8 | lfm2.5:8b | 17 | Never dated, and thin coverage |
| 10 | gamy316/aileen1.0 | 14.3 | Never dated, all stories from one outlet |

> **Zero fabricated URLs across all ten models.** Every citation matched real retrieved
> content. The honesty layer is doing its job.
>
> **Best value:** `qwen3.5:4b`, a perfect search score from a **3.4 GB** model with zero swap.

---

## 3. Search and Report Ranking

*Combined T2 and T4, 50 points. The report task: research a live topic and write `report.md`
with 4 mandated sections in order, 350+ words, every claim carrying a citation that resolves
to a real retrieved URL.*

| Rank | Model | Search | Report | **Total /50** |
|---|---|---|---|---|
| 1 | **qwen3.5:4b** | 25 | 23.9 | **48.9** |
| 1 | **gemma-4-12b-nightshift-heretic** | 25 | 23.9 | **48.9** |
| 3 | **gemma4:12b-mlx** | 20.7 | 24.5 | **45.2** |
| 4 | gpt-oss:20b | 19 | **25** | 44.0 |
| 4 | ornith:9b | 19 | **25** | 44.0 |
| 6 | Ornith-1.0-9B-GGUF | 17 | 22.8 | 39.8 |
| 7 | Agen/gemma-4-26B | 25 | **0** | 25.0 |
| 8 | gemma4:26b-mlx | 22 | **0** | 22.0 |
| 9 | lfm2.5:8b | 17 | **0** | 17.0 |
| 10 | gamy316/aileen1.0 | 14.3 | **0** | 14.3 |

> **Four models never wrote the file at all.** They searched, discussed the report, and
> produced nothing. Both 17 GB models are in that group: they ran out of the 5-minute budget
> before writing.

**Best prose quality, judged by hand:** `gpt-oss:20b`, `ornith:9b` and `Ornith-1.0-9B-GGUF`,
all 3/3. `ornith:9b` produced the richest report (778 words, and it correctly picked up the
August 2026 CHAINDROP/keyv wave). `qwen3.5:4b` cited `CVE-2026-45321`, which was **verified as
genuinely retrieved, not invented**.

---

## 4. Agentic Ranking

*The hardest test: a deliberately broken Python game with two real crash bugs. Read it, fix it,
and **run it to prove the fix**. Graded by an automated playthrough that exercises every menu
action. Pass or fail, no opinion involved.*

| Rank | Model | Playthrough | Bug 1 | Bug 2 | Ran the code | Tool calls | **Score** |
|---|---|---|---|---|---|---|---|
| 1 | **gemma4:12b-mlx** | **PASS** | fixed | fixed | yes | 13 | **25/25** |
| 2 | gemma-4-12b-heretic | FAIL | fixed | fixed | yes | 10 | 15 |
| 3 | gpt-oss:20b | FAIL | fixed | fixed | no | **25** | 12 |
| 4 | qwen3.5:4b | FAIL | fixed | missed | yes | 13 | 9 |
| 4 | Agen/gemma-4-26B | FAIL | missed | fixed | yes | 3 | 9 |
| 4 | gemma4:26b-mlx | FAIL | missed | fixed | yes | 4 | 9 |
| 4 | lfm2.5:8b | FAIL | missed | fixed | yes | 11 | 9 |
| 8 | Ornith-1.0-9B-GGUF | FAIL | missed | fixed | no | 1 | 6 |
| 8 | ornith:9b | FAIL | missed | fixed | no | 1 | 6 |
| 8 | gamy316/aileen1.0 | FAIL | missed | fixed | no | **0** | 6 |

> **Only `gemma4:12b-mlx` passed.** One model in ten.
>
> **Tool calls predict almost everything here.** The top four made 10 to 25 calls. The bottom
> three made 0 or 1 and simply *asserted* the code was fixed. `aileen1.0` made **zero tool
> calls** and declared victory.
>
> **Note:** `gpt-oss:20b` fixed both bugs and made the most tool calls of anyone, 25, but never
> executed the result. A strong planner that does not verify. It was also cut off by the
> 25-round ceiling in force at the time, so 12/25 understates it.

---

## 5. `/architect`: Best Model Pairings

`/architect` runs a **planner** (read-only) and an **executor** (full tools), loaded **one at a
time**. Combined size therefore never has to fit in RAM at once, only the larger of the two.

### Agentic and coding work

| Role | Model | Why |
|---|---|---|
| **Architect** | `gpt-oss:20b` | The best planner measured: 25 tool calls, found *both* bugs, 0 timeouts, 0 swap |
| **Editor** | `gemma4:12b-mlx` | The only model that produced a genuinely working fix, 25/25 |

> This plays to each one's strength: `gpt-oss` diagnoses but will not verify, and `gemma4:12b`
> verifies. Peak resident size 13 GB.
>
> **Lighter variant:** architect `qwen3.5:4b` at 3.4 GB with editor `gemma4:12b-mlx`. Peak 7.7
> GB, and barely slower.

### A full report on a subject

| Role | Model | Why |
|---|---|---|
| **Architect** | `qwen3.5:4b` | Perfect 25/25 search, 3.4 GB, zero swap, the fastest researcher |
| **Editor** | `gpt-oss:20b` | Perfect 25/25 report, 3/3 prose, 0 timeouts |

> A cheap, fast research phase, then the strongest writer for the document itself.
>
> **All-in-one alternative:** `gemma-4-12b-nightshift-heretic` scored 25 on search and 23.9 on
> the report by itself, but timed out 3 times out of 4.

### Strategic and long-horizon missions

| Role | Model | Why |
|---|---|---|
| **Architect** | `Ornith-1.0-9B-GGUF` | 25/25 reasoning, only 5.6 GB, zero swap |
| **Editor** | `gemma4:12b-mlx` | The best overall executor, and 25/25 reasoning as well |

> Both are perfect on reasoning and both are small, so switching between them is quick. Avoid
> the 17 GB models here: they also scored 25/25 on reasoning, but cost 8 to 13 GB of swap to
> do it.

### Everyday quick questions, single model, no architect

**`qwen3.5:4b`.** 3.4 GB, zero swap, a perfect search score, and about 70/100 overall. The best
speed-to-quality ratio in the set.

### Uncensored work

**`gemma-4-12b-nightshift-heretic`.** 25/25 search, 23.9 report, second-best agentic, 7.4 GB,
no swap. Ignore `Agen/gemma-4-26B-heretic`: the same uncensored capability, but 17 GB, 8.7 GB
of swap, and it never finished the report.

---

## 6. Recommended Settings

```
Default model        gemma4:12b-mlx        (was ornith:9b, which timed out on 3 of 4 tasks)
Architect model      gpt-oss:20b
Editor model         gemma4:12b-mlx
Embedding model      bge-m3                (keep, it is required for RAG)

Temperature          0.35
Top P                0.95
Repeat penalty       1.15                  DO NOT LOWER, see below
Max output tokens    4096
Context size         32768                 (from 65536; the measured prompt is ~8,200 tokens)
Max tool rounds      45                    (from 25, which truncated a model mid-task)
```

> ### The one finding that changes everything
>
> **`repeat_penalty` at 1.10 breaks tool calling.** Holding every other setting fixed,
> **1.15 gave 9 successes out of 9, and 1.10 gave 2 out of 11.** The failures were malformed
> tool calls: either XML syntax errors, or JSON printed as prose.
>
> Temperature, top_p, seed and context size were each isolated and **ruled out**. Tool-call
> syntax is highly repetitive, being full of braces, quotes and repeated keys, so too weak a
> penalty lets the sampler fall into a loop mid-JSON.
>
> This defect first appeared disguised as "these four models cannot call tools", which is how
> much it matters. The Agentic_1A code default was 1.1 and has been fixed.

---

## 7. Deleted, 89 GB Reclaimed

| Model | Size | Reason |
|---|---|---|
| `charaf/Qwen3.6-27B-OBLITERATED-mlx-q8` | 28.6 GB | Ollama refuses to load it: *"requires 26.6 GiB, only 17.3 GiB available"* |
| `rafw007/Qwen3.6-35B-A3B` | 23.9 GB | Loaded, being a MoE, but timed out with 3.6 GB of swap and empty output |
| `qwen3-coder:30b` | 18.6 GB | 180 s and 4.8 GB of swap to answer "what is the date" |
| `studiobrn/modCoderMLX` | 7.4 GB | Outputs `**` and nothing else, across 4 attempts |
| `MHKetbi/DeepSeek-R1-Distill-Llama-8B` | 5.3 GB | Zero tool calls, then invents answers such as "2023-10-16" and "15 files" |
| `htunnthuthutech/gemma-4-e2b-aiops` | 3.4 GB | Prints `<tool_calls>` as literal text |
| `oamazonasgabriel/qwen2.5-coder.1.5b` | 3.1 GB | Prints tool calls inside a json code fence |

**Kept:** `bge-m3`, the RAG embedder rather than a chat model, and `translategemma:27b`, which
has no tool support and is therefore out of this ranking, but which works for translation.

---

## 8. How Much to Trust This

- **One run per model per task.** Enough to separate 95 from 26. **Not** enough to separate
  4th from 5th. Treat gaps under about 6 points as ties.
- **The 5-minute cap shapes the results.** 19 of 40 runs hit it. A model scoring 0 on the
  report might well have finished given 15 minutes, but that is not a workflow anyone wants.
- **This benchmark was wrong twice before it was right.** A `repeat_penalty` of 1.1
  manufactured four false "this model cannot call tools" verdicts. A parsing bug scored a
  *perfect* reasoning answer 2.2 out of 25. A third bug read grounding evidence from only the
  final tool round, which made a model that had cited five real URLs look like it had
  fabricated all five. All three were caught by checking raw output against the score rather
  than trusting the number. Everything above is post-fix.
- **The search and report tasks hit the live web,** so difficulty varies a little between runs.
  Citations are therefore scored on *grounding*, meaning whether a URL appears in real
  retrieved content, rather than on truth.
- Full evidence, including every answer, tool trace and score, is in
  `benchmarks/model_ranking/results/`.
