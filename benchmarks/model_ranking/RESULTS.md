# Agentic_1A — Local Model Ranking

**Machine:** MacBook, Apple Silicon, 24 GB unified memory · **Date:** 8 August 2026
**Harness:** Agentic_1A OSS, 34 native tools, MCP disabled, `--private` mode
**Parameters (identical for every model):** temp 0.35 · top_p 0.95 · top_k 40 · **repeat_penalty 1.15** · num_ctx 32768 · num_predict 4096
**Scale:** 100 points = 4 tasks × 25 · 1 run per model per task · 5-minute hard cap per run

---

## 🏆 1. All-Purpose Ranking

| # | Model | Size | Reasoning | Search | Agentic | Report | **Total** |
|---|---|---|---|---|---|---|---|
| 🥇 | **gemma4:12b-mlx** | 7.7 GB | 25 | 20.7 | **25** | 24.5 | **95.2** |
| 🥈 | **gpt-oss:20b** | 13 GB | 19 | 19 | 12 | **25** | **75.0** |
| 🥉 | **Ornith-1.0-9B-GGUF** | 5.6 GB | 25 | 17 | 6 | 22.8 | **70.8** |
| 4 | qwen3.5:4b | 3.4 GB | 12 | **25** | 9 | 23.9 | 69.9 |
| 5 | gemma-4-12b-nightshift-heretic | 7.4 GB | 0 | **25** | 15 | 23.9 | 63.9 |
| 6 | Agen/gemma-4-26B-heretic | 17 GB | 25 | **25** | 9 | 0 | 59.0 |
| 7 | gemma4:26b-mlx | 17 GB | 25 | 22 | 9 | 0 | 56.0 |
| 8 | ornith:9b | 5.6 GB | 0 | 19 | 6 | **25** | 50.0 |
| 9 | gamy316/aileen1.0 | 4.9 GB | 13.8 | 14.3 | 6 | 0 | 34.1 |
| 10 | lfm2.5:8b | 5.2 GB | 0 | 17 | 9 | 0 | 26.0 |

> **The verdict is not close.** `gemma4:12b-mlx` wins by 20 points and is the **only model of ten that actually fixed the broken program** — every other model claimed success while leaving a crash in place. At 7.7 GB it also leaves you 16 GB of headroom.

### Reliability (the column that decides daily use)

| Model | Timeouts (of 4) | Swap caused | Total time |
|---|---|---|---|
| **gpt-oss:20b** | **0** ✅ | **0 MB** ✅ | **492 s** — fastest that also scores well |
| gamy316/aileen1.0 | 0 ✅ | 0 MB ✅ | 189 s — fastest overall, but weakest answers |
| lfm2.5:8b | 0 ✅ | 0 MB ✅ | 482 s |
| qwen3.5:4b | 1 | 0 MB ✅ | 663 s |
| gemma4:12b-mlx | 1 | 7.9 GB | 805 s |
| Ornith-1.0-9B-GGUF | 2 | 0 MB ✅ | 887 s |
| Agen/gemma-4-26B | 2 | 8.7 GB ⚠️ | 1166 s |
| gemma4:26b-mlx | 2 | **13.2 GB** 🚨 | 935 s |
| **ornith:9b** | **3** 🚨 | 0 MB | 999 s |
| gemma-4-12b-heretic | **3** 🚨 | 0 MB | 1076 s |

> 🚨 **`ornith:9b` is your current default and it timed out on 3 of 4 tasks.** Change it.
> 🚨 **The two 17 GB models are not viable on 24 GB.** `gemma4:26b-mlx` alone pushed **13.2 GB** into swap. That is SSD wear for scores *below* a 7.7 GB model.

---

## 🔍 2. Search Ranking

*Scored on: calling `get_datetime` before searching · reading pages vs. snippets · story count · outlet diversity · every URL verified against real tool output · no aggregators · no duplicated events.*

| # | Model | Score | Notes |
|---|---|---|---|
| 🥇 | **qwen3.5:4b** | **25/25** | Perfect. Dated first, deep-read, 3 outlets, all URLs real |
| 🥇 | **gemma-4-12b-nightshift-heretic** | **25/25** | Perfect, same profile |
| 🥇 | **Agen/gemma-4-26B-heretic** | **25/25** | Perfect — but 17 GB and 8.7 GB of swap to get there |
| 4 | gemma4:26b-mlx | 22 | Used snippets, didn't deep-read |
| 5 | gemma4:12b-mlx | 20.7 | Snippets only; 2 of 3 stories from same outlet |
| 6 | gpt-oss:20b | 19 | Deep-read properly but only found **2 stories from 1 outlet** |
| 6 | ornith:9b | 19 | Searched *before* checking the date |
| 8 | Ornith-1.0-9B-GGUF | 17 | ❌ **Never called `get_datetime`** |
| 8 | lfm2.5:8b | 17 | ❌ Never dated; thin coverage |
| 10 | gamy316/aileen1.0 | 14.3 | Never dated; all stories from one outlet |

> ✅ **Zero fabricated URLs across all ten models.** Every citation matched real retrieved content. The honesty layer is doing its job.
> 💡 **Best value:** `qwen3.5:4b` — a perfect search score from a **3.4 GB** model with zero swap.

---

## 📄 3. Search + Report Ranking

*Combined T2 + T4 (50 pts). The report task: research a live topic, write `report.md` with 4 mandated sections in order, 350+ words, every claim carrying a citation that resolves to a real retrieved URL.*

| # | Model | Search | Report | **Total /50** |
|---|---|---|---|---|
| 🥇 | **qwen3.5:4b** | 25 | 23.9 | **48.9** |
| 🥇 | **gemma-4-12b-nightshift-heretic** | 25 | 23.9 | **48.9** |
| 🥉 | **gemma4:12b-mlx** | 20.7 | 24.5 | **45.2** |
| 4 | gpt-oss:20b | 19 | **25** | 44.0 |
| 4 | ornith:9b | 19 | **25** | 44.0 |
| 6 | Ornith-1.0-9B-GGUF | 17 | 22.8 | 39.8 |
| 7 | Agen/gemma-4-26B | 25 | **0** ❌ | 25.0 |
| 8 | gemma4:26b-mlx | 22 | **0** ❌ | 22.0 |
| 9 | lfm2.5:8b | 17 | **0** ❌ | 17.0 |
| 10 | gamy316/aileen1.0 | 14.3 | **0** ❌ | 14.3 |

> ❌ **Four models never wrote the file at all.** They searched, talked about the report, and produced nothing. Both 17 GB models are in that group — they ran out of the 5-minute budget before writing.

**Best prose quality (judged by hand):** `gpt-oss:20b`, `ornith:9b`, `Ornith-1.0-9B-GGUF` — all 3/3.
`ornith:9b` produced the richest report (778 words, correctly picked up the August 2026 CHAINDROP/keyv wave).
`qwen3.5:4b` cited `CVE-2026-45321` — **verified as genuinely retrieved, not invented.**

---

## 🤖 4. Agentic Ranking

*The hardest test: a deliberately broken Python game with two real crash bugs. Read it, fix it, **run it to prove the fix**. Graded by an automated playthrough that exercises every menu action — pass/fail, no opinion involved.*

| # | Model | Playthrough | Bug 1 | Bug 2 | Ran the code | Tool calls | **Score** |
|---|---|---|---|---|---|---|---|
| 🥇 | **gemma4:12b-mlx** | ✅ **PASS** | ✅ | ✅ | ✅ | 13 | **25/25** |
| 🥈 | gemma-4-12b-heretic | ❌ | ✅ | ✅ | ✅ | 10 | 15 |
| 🥉 | gpt-oss:20b | ❌ | ✅ | ✅ | ❌ | **25** | 12 |
| 4 | qwen3.5:4b | ❌ | ✅ | ❌ | ✅ | 13 | 9 |
| 4 | Agen/gemma-4-26B | ❌ | ❌ | ✅ | ✅ | 3 | 9 |
| 4 | gemma4:26b-mlx | ❌ | ❌ | ✅ | ✅ | 4 | 9 |
| 4 | lfm2.5:8b | ❌ | ❌ | ✅ | ✅ | 11 | 9 |
| 8 | Ornith-1.0-9B-GGUF | ❌ | ❌ | ✅ | ❌ | 1 | 6 |
| 8 | ornith:9b | ❌ | ❌ | ✅ | ❌ | 1 | 6 |
| 8 | gamy316/aileen1.0 | ❌ | ❌ | ✅ | ❌ | **0** | 6 |

> 🥇 **Only `gemma4:12b-mlx` passed.** One model in ten.
> 📊 **Tool calls predict everything here.** The top four made 10–25 calls; the bottom three made 0–1 and simply *asserted* the code was fixed. `aileen1.0` made **zero tool calls** and declared victory.
> ⚠️ `gpt-oss:20b` fixed both bugs and made the most tool calls of anyone (25) but never executed the result — great planner, doesn't verify.

---

## 🧭 5. `/architect` — Best Model Pairings

`/architect` runs a **planner** (read-only) and an **executor** (full tools), loaded **one at a time** — so combined size never has to fit in RAM at once, only the larger of the two.

### 🔧 Agentic / coding work

| Role | Model | Why |
|---|---|---|
| **Architect** | `gpt-oss:20b` | Best planner measured: 25 tool calls, found *both* bugs, **0 timeouts, 0 swap** |
| **Editor** | `gemma4:12b-mlx` | The only model that produced a genuinely working fix (25/25) |

> Plays to each one's strength: `gpt-oss` diagnoses but won't verify; `gemma4:12b` verifies. Peak resident 13 GB.
> **Lighter variant:** architect `qwen3.5:4b` (3.4 GB) + editor `gemma4:12b-mlx` — peak 7.7 GB, barely slower.

### 📰 Full report on a subject

| Role | Model | Why |
|---|---|---|
| **Architect** | `qwen3.5:4b` | Perfect 25/25 search, 3.4 GB, zero swap, fastest researcher |
| **Editor** | `gpt-oss:20b` | Perfect 25/25 report, 3/3 prose, **0 timeouts** |

> Cheap, fast research phase; the strongest writer for the actual document.
> **All-in-one alternative:** `gemma-4-12b-nightshift-heretic` scored 25 search + 23.9 report solo — but timed out 3 times out of 4.

### ♟️ Strategic / long-horizon missions

| Role | Model | Why |
|---|---|---|
| **Architect** | `Ornith-1.0-9B-GGUF` | 25/25 reasoning, only 5.6 GB, zero swap |
| **Editor** | `gemma4:12b-mlx` | Best overall executor; 25/25 reasoning too |

> Both perfect on reasoning, both small, so switching is quick. Avoid the 17 GB models here — they scored 25/25 reasoning too but cost 8–13 GB of swap to do it.

### ⚡ Everyday quick questions (single model, no architect)

**`qwen3.5:4b`** — 3.4 GB, zero swap, perfect search, ~70/100 overall. The best speed-to-quality ratio you own.

### 🔒 Uncensored work

**`gemma-4-12b-nightshift-heretic`** — 25/25 search, 23.9 report, second-best agentic. 7.4 GB, no swap.
Ignore `Agen/gemma-4-26B-heretic`: same uncensored capability, 17 GB, 8.7 GB swap, and it never finished the report.

---

## ⚙️ 6. Recommended Settings

```
Default model        gemma4:12b-mlx        (was ornith:9b — 3 timeouts of 4)
Architect model      gpt-oss:20b
Editor model         gemma4:12b-mlx
Embedding model      bge-m3                (keep — required for RAG)

Temperature          0.35    ✅ already correct
Top P                0.95    ✅ already correct
Repeat penalty       1.15    ✅ already correct — DO NOT LOWER (see below)
Max output tokens    4096
Context size         32768   (from 65536 — measured prompt is only ~8,200 tokens)
```

> ### 🔬 The one finding that changes everything
> **`repeat_penalty` at 1.10 breaks tool calling.** Holding every other setting fixed:
> **1.15 → 9 successes out of 9 · 1.10 → 2 out of 11.** Failures were malformed tool calls — XML syntax errors, or JSON printed as prose.
> Temperature, top_p, seed and context size were each isolated and **ruled out**. Tool-call syntax is highly repetitive (braces, quotes, repeated keys), so too weak a penalty lets the model fall into a loop mid-JSON.
> Your live config was already at 1.15. The **Agentic_1A code default was 1.1 and has been fixed.**

---

## 🗑️ 7. Deleted — 89 GB Reclaimed

| Model | Size | Reason |
|---|---|---|
| `charaf/Qwen3.6-27B-OBLITERATED-mlx-q8` | 28.6 GB | Ollama refuses to load it: *"requires 26.6 GiB, only 17.3 GiB available"* |
| `rafw007/Qwen3.6-35B-A3B` | 23.9 GB | Loaded (MoE), but timed out with 3.6 GB swap and empty output |
| `qwen3-coder:30b` | 18.6 GB | 180 s + 4.8 GB swap to answer "what's the date" |
| `studiobrn/modCoderMLX` | 7.4 GB | Outputs `**`. Nothing else, 4 attempts |
| `MHKetbi/DeepSeek-R1-Distill-Llama-8B` | 5.3 GB | Zero tool calls, then invents answers ("2023-10-16", "15 files") |
| `htunnthuthutech/gemma-4-e2b-aiops` | 3.4 GB | Prints `<tool_calls>` as literal text |
| `oamazonasgabriel/qwen2.5-coder.1.5b` | 3.1 GB | Prints tool calls inside a ```json fence |

**Kept:** `bge-m3` (RAG embedder, not a chat model) · `translategemma:27b` (no tool support, but works for translation — 17 GB, delete if you don't translate).

---

## ⚠️ 8. How Much to Trust This

- **One run per model per task.** Enough to separate 95 from 26; **not** enough to separate #4 from #5. Treat gaps under ~6 points as ties.
- **The 5-minute cap shapes the results.** 19 of 40 runs hit it. A model scoring 0 on the report often *would* have finished given 15 minutes — but that isn't a workflow you'd want.
- **My first attempt at this benchmark was wrong**, twice: a `repeat_penalty` of 1.1 manufactured four false "this model can't call tools" verdicts, and a parsing bug scored a *perfect* reasoning answer 2.2/25. Both were found by checking raw output against the score. Everything above is post-fix.
- **Live web** for the search and report tasks, so difficulty varies slightly between runs. Citations are therefore scored on *grounding* (does this URL appear in real retrieved content) rather than on truth.
- Full evidence — every answer, tool trace, and score — is in `benchmarks/model_ranking/results/`.
