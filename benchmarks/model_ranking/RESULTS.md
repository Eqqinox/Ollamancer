# Ollamancer: Local Model Ranking

**Machine:** MacBook, Apple Silicon, 24 GB unified memory · **Date:** 8 August 2026, extended 10 and 11 August
**Harness:** Ollamancer OSS, 34 native tools, MCP disabled, `--private` mode
**Parameters (identical for every model):** temp 0.35 · top_p 0.95 · top_k 40 · **repeat_penalty 1.15** · num_ctx 32768 · num_predict 4096
**Scale:** 100 points = 4 tasks x 25 · 5-minute hard cap per run

> ### Read [section 10](#10-pass2-the-authoritative-ranking-11-august-2026) first
>
> **Sections 1–9 are `pass^1`: one run per model per task.** On 11 August every model in the
> ranking was re-run for a second rep and scored under `pass^k`, the minimum across reps. Eight
> of the ten re-run models scored *lower*, one by 17 points, and the ranking changed at the top.
>
> Those sections are kept unedited because they are what a single run actually said, and the
> gap between them and section 10 is the most useful result in this file. **But they overstate
> every model in them.** Where the two disagree, section 10 is correct.

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

> Three models were added on 10 August and are **not** in the table above, which is left as
> it ran. See [section 9](#9-additions-10-august-2026) for the combined ranking.
>
> **This table is `pass^1` and is superseded.** Under `pass^2`, `gemma4:12b-mlx` falls to 79.2
> and second place. See [section 10](#10-pass2-the-authoritative-ranking-11-august-2026).

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
> content.
>
> **This measures the models, not the honesty layer** — corrected 2026-08-15. This block used
> to end "the honesty layer is doing its job", which does not follow. `_grounding_check` fired
> **zero times across all 168 runs** of this campaign, and zero times again across a separate
> 96-run A/B on the same battery. A check that never fires cannot be *why* nothing was
> fabricated: on this battery the models simply did not fabricate URLs.
>
> **It never fired, and we know it works anyway.** That is the useful claim, and it is now
> measured rather than assumed — because silence is the same observation for a check that is
> perfectly calibrated and for one that is dead, and the second reading is the one that should
> worry anyone. Three things had to be true, and `tests/test_grounding_sensitivity.py` plus
> `tests/test_a56.py` establish all three:
>
> | | |
> |---|---|
> | **Reachable at runtime**, not dead code | `test_a56` drives a fabricated number and date through the real `run_agent` and asserts both the injected nudge and the `AUTO_GROUNDING_CHECK_NUDGE` audit record |
> | **Not defeated by volume** | an invented URL and figure injected into real banked answers, against their real tool results: **caught 91 of 91**. The worry was that a 10-16 KB haystack matches anything by coincidence; a random 4-digit value collides with the concatenated digit-soup only **~3%** of the time, 5 digits 0.3%, 6+ never |
> | **Sensitive to a realistic fabrication** | not a straw-man fake domain but a plausible one-digit change to a figure the model genuinely retrieved: **71 of 78 (91%) would have nudged**, 7 stayed silent |
>
> So the correct reading of the zero is *"nothing needed flagging"*, not *"the check is
> broken"*, and not *"the check is why."*
>
> **Still not verified:** every positive above is synthetic. No model has yet been observed
> fabricating and being caught in the wild, so this measures the detector, never the deterrent.
> Paraphrase remains uncovered by construction (`test_grounding_recheck` pins that blind spot),
> and the 9% that slip silently are unanalysed.
>
> Worth stating plainly, because the original error is the one this project exists to
> criticise: a true observation ("zero fabricated URLs") was attributed to the wrong cause. The
> same shape appears in `PLAN.md` §3 (`status: "ok"` read as "the run answered") and
> `DESIGN.md` §4.2b (`had_verification` read as "the model did not check its work").
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
> much it matters. The Ollamancer code default was 1.1 and has been fixed.

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

**Also removed, 11 August:** `gamy316/aileen1.0`, `lfm2.5:8b` and `ornith:9b`. All three scored
in the bottom five under `pass^2` (21.3, 9.0 and 39.3). They were temporarily re-pulled that day
purely to give them a second rep, then deleted again — their run directories and scores remain,
so they stay in the ranking without occupying 15.7 GB.

---

## 8. How Much to Trust This

- **One run per model per task.** Enough to separate 95 from 26. **Not** enough to separate
  4th from 5th. Treat gaps under about 6 points as ties.
  **Superseded on 11 August:** this caution turned out to be understated. A second rep moved
  eight of ten models, the largest by 17 points — more than the 6-point tie band suggested was
  possible. See [section 10](#10-pass2-the-authoritative-ranking-11-august-2026).
- **The 5-minute cap shapes the results.** **14** of 40 runs hit it. A model scoring 0 on the
  report might well have finished given 15 minutes, but that is not a workflow anyone wants.
  *(Corrected 2026-08-15: this said 19, which contradicted §1's own per-model timeout column on
  the same page — that column reads 0+0+0+1+1+2+2+2+3+3 and sums to 14. Recomputed from
  `scores.json`: 14 of the 40 rep-1 runs reached the 300 s cap. No threshold reproduces 19
  (≥250 s gives 18, ≥298 s gives 14), so 19 appears to have been a miscount rather than a
  different definition. §1 was right.)*
  **And "hit the cap" understates what happens**, which is the more important correction: a
  capped run does not merely score badly, it returns the six characters `ERROR:` and is recorded
  as `status: "ok"`. See the warning under [`PLAN.md` §3](./PLAN.md).
- **This benchmark was wrong twice before it was right.** A `repeat_penalty` of 1.1
  manufactured four false "this model cannot call tools" verdicts. A parsing bug scored a
  *perfect* reasoning answer 2.2 out of 25. A third bug read grounding evidence from only the
  final tool round, which made a model that had cited five real URLs look like it had
  fabricated all five. All three were caught by checking raw output against the score rather
  than trusting the number. Everything above is post-fix.
- **The search and report tasks hit the live web,** so difficulty varies a little between runs.
  Citations are therefore scored on *grounding*, meaning whether a URL appears in real
  retrieved content, rather than on truth.
- **Per-run scores ship; raw run directories do not.** `results/scores.json` is committed and
  holds every sub-score, timing and tool-call count behind the tables above. The run
  directories beside it, with each model's answers and tool traces, are deliberately
  gitignored: they contain the full text of third-party news articles fetched during the
  search and report tasks, which is not ours to republish. Re-running the harness locally
  regenerates them.

---

## 9. Additions, 10 August 2026

Same harness, same pinned parameters, same 5-minute cap. Three models added; the ten above
were not re-run, so their numbers are unchanged.

| # | Model | Size | Reasoning | Search | Agentic | Report | **Total** |
|---|---|---|---|---|---|---|---|
| 1 | **gemma4:12b-mlx** | 7.7 GB | 25 | 20.7 | **25** | 24.5 | **95.2** |
| 2 | **gpt-oss:20b** | 13 GB | 19 | 19 | 12 | **25** | **75.0** |
| 2= | **gemma4:e4b-mlx** | **8.8 GB** | 21 | 20 | 12 | 22 | **75.0** |
| 4 | Ornith-1.0-9B-GGUF | 5.6 GB | 25 | 17 | 6 | 22.8 | 70.8 |
| 5 | qwen3.5:4b | 3.4 GB | 12 | **25** | 9 | 23.9 | 69.9 |
| 6 | gemma-4-12b-nightshift-heretic | 7.4 GB | 0 | **25** | 15 | 23.9 | 63.9 |
| 7 | Agen/gemma-4-26B-heretic | 17 GB | 25 | **25** | 9 | 0 | 59.0 |
| 8 | gemma4:26b-mlx | 17 GB | 25 | 22 | 9 | 0 | 56.0 |
| 9 | qwen2.5:7b | 4.7 GB | 9 | 18.7 | 6 | 20.2 | 53.9 |
| 10 | ornith:9b | 5.6 GB | 0 | 19 | 6 | **25** | 50.0 |
| 11 | gemma4:e4b-mlx-bf16 | 16 GB | 15 | **25** | 6 | 0 | 46.0 |
| 12 | gamy316/aileen1.0 | 4.9 GB | 13.8 | 14.3 | 6 | 0 | 34.1 |
| 13 | lfm2.5:8b | 5.2 GB | 0 | 17 | 9 | 0 | 26.0 |

`gemma4:e4b-mlx` enters joint 2nd at **8.8 GB**, matching a 13 GB model. `qwen2.5:7b` lands
mid-table with no niche of its own, though at 397 s it is the fastest model scoring above 34.

### 9.1 Full precision lost to 4-bit, by 29 points

The two `e4b` entries are the same Google model, same architecture, same MLX engine, differing
only in quantisation. That makes them the one controlled pair in this campaign.

| Task | `e4b-mlx` (8.8 GB, nvfp4) | `e4b-mlx-bf16` (16 GB, unquantised) | Delta |
|---|---|---|---|
| Reasoning | 21.0 (50 s) | 15.0 (56 s) | **+6.0** |
| Search | 20.0 (56 s) | **25.0** (149 s) | -5.0 |
| Agentic | 12.0 (300 s) | 6.0 (300 s) | **+6.0** |
| Report | 22.0 (300 s) | **0.0** (293 s) | **+22.0** |
| **Total** | **75.0** | **46.0** | **+29.0** |

The extra 7.2 GB bought no measurable quality. It bought swap. The bf16 build was **2.7x
slower on the search task** for an identical result, touched swap on both runs where it was
sampled (+1342 MB, +1066 MB), and on the report task spent 293 seconds to produce a single
tool call and no file at all.

> **The lesson is not "quantisation is free."** It is that on 24 GB of unified memory, memory
> headroom dominates precision. A 4-bit build that fits beats a full-precision build that
> swaps, and it is not close. Spend the budget on headroom first.

### 9.2 A reproducible blind spot in `gemma4:e4b-mlx`

The one task bf16 won was search, and the whole 5-point gap is a single sub-score:

```
e4b-mlx        datetime_first 0 · deep_read 4 · story_count 5 · diversity 4 · grounded 7.0
e4b-mlx-bf16   datetime_first 5 · deep_read 4 · story_count 5 · diversity 4 · grounded 7.0
```

Every other signal is identical. The quantised build never calls `get_datetime` before
searching. That looked like a coin flip, so the search task was re-run at four different
seeds: **0 out of 4**. It is a stable trait, not sampling noise.

The system prompt is explicit about this (`agentic/i18n.py`, "Never guess today's date ...
call `get_datetime` first"), so this is an instruction-following failure rather than a gap in
the agent.

**It already produces wrong answers, quietly.** Instead of resolving the date, the model puts
the relative phrase straight into the query -- `search_web_deep("geopolitics breaking news
last 24 hours")` -- and lets the search engine handle recency. In the run inspected on
2026-08-10, two of its three stories fell outside the requested window, including one about
events "last month". Story count, diversity and grounding all scored full marks, because none
of them checks recency. `datetime_first` is the only signal that catches it.

Grounding itself was flawless: **7.0/7.0 across all four reruns, zero fabricated URLs.**

> **Practical guidance.** For date-bounded questions, either use `qwen3.5:4b` (25/25 on
> search, 3.4 GB) or tell `gemma4:e4b-mlx` to check the date explicitly, which it then does.

---

## 10. `pass^2`: the authoritative ranking (11 August 2026)

Five models were added and, more importantly, **every model in the ranking was given a second
rep**. The reported score is now the **minimum across reps** (`pass^k`, PLAN.md §1.3): a model
scores only what it can produce *every* time. Same harness, same pinned parameters, same cap.

| # | Model | Size | Reas. | Search | Agentic | Report | **pass^2** | mean | was pass^1 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **qwen-heretic** ⁴ (Qwen3.5-9B) | 7.0 GB | 17.0 | 20.0 | **25** | **25** | **87.0** | 91.3 | *new* |
| 2 | gemma4:e4b-mlx ² | 8.8 GB | **25** | 18.7 | 12 | 24.0 | 79.7 | 80.7 | 75.0 ³ |
| 3 | **gemma4:12b-mlx** | 7.7 GB | **25** | 20.7 | 9 | 24.5 | **79.2** | 89.3 | 95.2 (−16.0) |
| 4 | **gpt-oss:20b** | 13 GB | 19.0 | 19.0 | 12 | **25** | **75.0** | 80.0 | 75.0 (=) |
| 5 | Qwen3.6-35B-A3B **IQ2_M** | 12.6 GB | 17.0 | 17.0 | 12 | 23.8 | 69.8 | 74.7 | *new* |
| 6 | Qwen3.6-35B-A3B **IQ3_M** | 16.3 GB | 16.0 | 22.0 | 6 | **25** | 69.0 | 76.5 | *new* |
| 7 | qwen3.5:4b | 3.4 GB | 12.0 | 22.0 | 9 | 23.9 | 66.9 | 71.7 | 69.9 (−3.0) |
| 8 | Ornith-1.0-9B-GGUF | 5.6 GB | **25** | 16.0 | 6 | 19.0 | 66.0 | 69.9 | 70.8 (−4.8) |
| 9 | qwen2.5:7b ² | 4.7 GB | 12.0 | 18.7 | 6 | 21.2 | 57.9 | 57.9 | 53.9 ³ |
| 10 | gemma-4-12b-nightshift-heretic | 7.4 GB | 0 | **25** | 9 | 23.3 | 57.3 | 60.6 | 63.9 (−6.6) |
| 11 | Agen/gemma-4-26B-heretic | 17 GB | **25** | 22.0 | 9 | 0 | 56.0 | 68.5 | 59.0 (−3.0) |
| 12 | gemma4:26b-mlx | 17 GB | **25** | 22.0 | 9 | 0 | 56.0 | 57.5 | 56.0 (=) |
| 13 | gemma4:e4b-mlx-bf16 ² | 16 GB | 18.0 | **25** | 6 | 0 | 49.0 | 49.0 | 46.0 ³ |
| 14 | ornith:9b | 5.6 GB | 0 | 14.3 | 6 | 19.0 | 39.3 | 53.6 | 50.0 (−10.7) |
| 15 | **qwen3.5:4b-mlx** | 4.0 GB | 0 | 4.0 | 6 | 18.0 | 28.0 | 44.9 | *new* |
| 16 | gamy316/aileen1.0 | 4.9 GB | 1.0 | 14.3 | 6 | 0 | 21.3 | 30.5 | 34.1 (−12.8) |
| 17 | **qwen3.5:9b-mlx** | 8.9 GB | 0 | 4.0 | 6 | 0 | 10.0 | 34.5 | *new* |
| 18 | lfm2.5:8b | 5.2 GB | 0 | 0 | 9 | 0 | 9.0 | 17.5 | 26.0 (−17.0) |

**Every total above is final.** All 26 outstanding hand judgements were completed on 11 August,
so no row is provisional and `score.py --all` reports an empty worklist.

² **Not `pass^2`** — never in the rep-2 scope. `qwen2.5:7b` and `gemma4:e4b-mlx-bf16` are single
observations throughout. `gemma4:e4b-mlx` is single-run on reasoning, agentic and report, but
has **four** reps on search from the §9.2 seed investigation, so its rep count is inconsistent
even within its own row. None of the three is comparable to the rest of the table; the scorer
marks them `◆`. **Rank 2 is therefore not a real second place** — it is a single run sitting in
a table of minimums.
³ These three rose (+4.7, +4.0, +3.0) purely because their hand judgements were completed, not
because they were re-run. Judging can only raise a score; reps can only lower it.
⁴ **`qwen-heretic:latest` is a local tag, not a pullable name.** The underlying build is
`Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-Q4_K_M.gguf`, imported into Ollama from a
local file: `ollama show --modelfile` resolves only to a blob hash, with no upstream repository
recorded. Everything else in this table can be pulled by the name given; **the top-ranked model
cannot**, so this row is the one result here that a reader cannot independently reproduce
without sourcing that GGUF themselves. `ollama show` confirms what it is — architecture
`qwen35`, 9.2B parameters, Q4_K_M, 262144 context — but not where it came from.

### 10.1 A second rep costs almost everyone points

Of the ten models re-run, **eight scored lower and two held exactly**:

| Held | Dropped a little | Dropped hard |
|---|---|---|
| `gpt-oss:20b` (=) | `qwen3.5:4b` −3.0 | `lfm2.5:8b` **−17.0** |
| `gemma4:26b-mlx` (=) | `Agen/gemma-4-26B` −3.0 | `gemma4:12b-mlx` **−16.0** |
| | `Ornith-1.0-9B` −4.8 | `gamy316/aileen1.0` **−12.8** |
| | `nightshift-heretic` −6.6 | `ornith:9b` **−10.7** |

The pass^1 table was flattering nearly everyone. `gpt-oss:20b` holding its 75.0 exactly across
both reps is, in this light, a stronger result than its rank suggests: **it is the most
repeatable model in the set**, with 0 timeouts and 0 swap across all 8 runs.

### 10.2 The top of the table changed, and why

`gemma4:12b-mlx` lost first place on **one task**:

```
gemma4:12b-mlx   agentic   [25, 9]    spread 16   ← passed the playthrough once, not twice
qwen-heretic     agentic   [25, 25]   spread  0   ← passed it both times
```

`gemma4:12b-mlx` remains the better model on a good day — its mean of 89.3 is second only to
`qwen-heretic`'s 91.3. It is not the more *dependable* one. That is the entire content of
`pass^k`, and it is why the metric exists.

> **The ordering was checked before it was trusted.** When the judged items were still
> outstanding the gap was only 2.8 points, smaller than the 7 points each model could still
> gain, so the result was published as provisional and the default was left alone. Completing
> the judgements *widened* the gap to 7.8: `qwen-heretic` gained 5.0 (a perfect 25/25 report on
> both reps) while `gemma4:12b-mlx`, already fully judged, could not move.
>
> **The default model has still not been changed.** One campaign on one machine is not grounds
> to re-point the documentation, and `gemma4:12b-mlx` is stronger on reasoning (25 vs 17).
>
> **And the comparison is confounded.** `gemma4:12b-mlx`'s two reps ran on *different builds of
> the harness* (see §10.6): rep 1 on 8 August, rep 2 after eight commits including a new tool
> and a change to three generation defaults. Its `[25, 9]` may be model variance, harness
> change, or both. `qwen-heretic` ran both reps on one build, so its own score is sound — but
> **the gap between them is not a clean measurement**, and no default should move on it.

### 10.3 Three controlled quantisation pairs

| Pair | Lower / smaller | Higher / larger | Result |
|---|---|---|---|
| Qwen3.5-**9B** | `qwen-heretic` Q4_K_M, 7.0 GB → **87.0** | `qwen3.5:9b-mlx` nvfp4, 8.9 GB → **10.0** | 8.7× gap, same base weights |
| Qwen3.5-**4B** | `qwen3.5:4b` Q4, 3.4 GB → **66.9** | `qwen3.5:4b-mlx` nvfp4, 4.0 GB → **28.0** | same direction |
| Qwen3.6-**35B-A3B** | `IQ2_M`, 12.6 GB → **69.8** | `IQ3_M`, 16.3 GB → **69.0** | +3.7 GB buys nothing |

The 9B pair is the cleanest controlled result in this campaign: **identical base model,
differing only in quantisation and runtime, and an 87.0 against a 10.0.** Neither nvfp4 build
touched swap, so this is not the memory story of §9.1. `qwen3.5:9b-mlx` timed out on **6 of 8
runs** — it simply does not finish. `qwen3.5:4b-mlx` timed out only 2 of 8 and still scored
28.0, so its weakness is genuine, not just slowness.

Both nvfp4 builds declare `requires 0.19.0`. **Treat this as a suspected runtime problem, not
a verdict on the weights** — it has not been isolated the way `repeat_penalty` was in §6.

The 35B pair repeats §9.1's lesson with the sign flipped, and it is the sharpest illustration
of `pass^k` in the file: **IQ3_M has the higher mean (76.5 vs 74.7) but the lower pass^2 (69.0
vs 69.8).** The larger quantisation is better on a good run and less dependable across runs —
its reasoning spread is 9.0 against IQ2_M's 1.0. It also touched swap where IQ2_M never did.
On any best-of or average-of metric IQ3_M wins and you buy the extra 3.7 GB; on the metric that
asks what you get *every* time, it loses.

### 10.4 Size still does not buy quality, but memory headroom explains most of it

| Model | Timeouts | Swap caused | pass^2 |
|---|---|---|---|
| `gemma4:26b-mlx` | 4/8 | **+18.9 GB** | 56.0 |
| `Agen/gemma-4-26B` | 4/8 | **+16.2 GB** | 56.0 |
| `gemma4:12b-mlx` | 3/8 | +7.9 GB | 79.2 |
| Qwen3.6-35B-A3B IQ2_M | **2/8** | **0 MB** | 69.8 |
| `qwen-heretic` | 4/8 | **0 MB** | 87.0 |

The two 26B models **beat every other model on pure reasoning** (25.0, a perfect score, against
`qwen-heretic`'s 15.0) and still finish 26 points behind, because they page 16–19 GB and never
complete the report task. Per PLAN.md §7, that is evidence about **this machine**, not about
those models.

The 35B A3B pair is the control that proves the point: as a mixture-of-experts activating ~3B
parameters per token, it **fits** — zero swap, and it timed out *less* than the winner did
(2 of 8 against 4 of 8) — and it still loses to `qwen-heretic` by 17.2 points. The gap there is
entirely agentic (12 and 6 against 25), not memory.

(Fewest timeouts overall belongs to `gpt-oss:20b`, `gamy316/aileen1.0` and `lfm2.5:8b`, all at
**0 of 8** — though for the latter two that reflects giving up quickly rather than working fast.)

> **The honest one-line summary.** On 24 GB, `qwen-heretic` is the best *agentic* model tested
> and the best all-rounder that never swaps. It does **not** out-reason the 26B models, which
> beat it 25 to 17 on the one task that isolates reasoning — they just cannot finish a job on
> this hardware.

### 10.5 What changed in the harness

- `score.py` now implements `pass^k`. It was previously documented in PLAN.md but not coded:
  N reps produced N unlinked rows and nothing compared them. It now emits a `(model, task)`
  roll-up (`pass_k_total`, `mean_total`, `spread`, `status_all_ok`) and a ranked per-model
  roll-up, to `results/scores_rollup.json` alongside the unchanged per-run `results/scores.json`.
- Rows whose rep count differs from the rest of the table are marked `◆` and excluded from
  comparison by the printed legend.
- `judged.json` accepts a per-rep key (`<model>#rep<n>`). It was keyed by model alone, so
  rep 2 silently inherited rep 1's hand score for the two judged items — the two items that
  could therefore never vary across reps, defeating the point of running them. Legacy
  model-only keys still resolve and are flagged as inherited in the run notes.
- A total with an unjudged item is reported `PROVISIONAL`, and `--all` prints a worklist of
  every `(task, item, model, rep)` still owed, so the debt cannot be quietly forgotten.
- `rank.sh` now defaults to `--reps 2`.

### 10.6 Additional limits, on top of section 8

- **Two reps is the floor for a `pass^k` claim, not a comfortable margin.** τ-bench uses more.
  Two reps catch a model that fails half the time; they do not catch one that fails 1 in 5.
- **The hand judgements are complete.** All 26 were scored on 11 August against the existing
  2026-08-08 judgements as calibration (rubric recorded in `judged.json` under
  `_schema.judged_2026_08_11`), so no total is a floor. They remain a *judgement*: two items,
  7 of the 100 points, rest on a human reading rather than on a deterministic check.
- **Three models are not `pass^2`** (`gemma4:e4b-mlx`, `qwen2.5:7b`, `gemma4:e4b-mlx-bf16`) and
  are marked `◆` by the scorer. Do not compare them across the line.
- **The 5-minute cap binds harder than in section 8.** 48 of 135 scored runs hit it, 36%. For
  the slowest models the ranking is measuring what fits in five minutes, which is the intended
  question but is not the same as model quality.
- **The two reps of the ten older models did not run on the same harness, and this is the
  most serious limitation on this page.** PLAN.md §1.2 makes "hold the harness constant so
  failures attribute to the model" a design principle, and for those ten it was not held:

  The ten older survivors ran **rep 1 on 8 August (14:52–17:14)** and **rep 2 on 10–11 August**.
  The five models added on 11 August ran **both reps on 11 August**, on one build.

  Eight commits landed on `agentic/` in between, including a **new tool** (`repo_map`, so the
  tool schema in every prompt grew), a change to **three generation defaults** described at the
  time as "quietly costing tool-call reliability", and two bug fixes. The effect is measurable
  rather than hypothetical: on `t1`, the zero-tool task where the prompt is just system +
  schema + question, **every** model whose rep 1 ran on 8 August shows a rep-2 prompt **195 to
  356 tokens larger**, while models with both reps on 11 August show a delta of 0.

  So for those ten, a rep-1-to-rep-2 difference is *model variance plus harness change*, and the
  two cannot be separated after the fact. **This directly touches the headline result:**
  `gemma4:12b-mlx` lost first place on a single task going `[25, 9]`, and those two runs were
  on different harnesses. The five models added on 11 August are unaffected — both of their
  reps ran on one build — so `qwen-heretic`'s 87.0 is clean, but the comparison *against*
  `gemma4:12b-mlx` inherits the problem.

  **This will not be fixed.** The remedy is to re-run rep 1 for those ten on the current build:
  40 runs, ~2.1 h of model time, ~3 h in practice once the memory interruptions and the re-pull
  of three since-deleted models are counted. That was judged not worth the machine time, so it
  is recorded here as a known limitation rather than a pending task. **Treat the ordering of
  ranks 1–3 as unresolved rather than as measured**, and do not quote the gap between
  `qwen-heretic` and `gemma4:12b-mlx` as a clean result.
- **The campaign was interrupted four times by memory exhaustion.** `gemma4:12b-mlx` on the
  report task spikes **+1.58 GB of swap** and repeatedly killed the driver process; the runs
  were completed after unloading resident models between attempts. No run in the table was
  produced under those degraded conditions — `rank.sh` re-runs anything without a `meta.json`.
