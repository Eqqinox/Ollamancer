# Ollamancer: Design & engineering history

> How this agent is built, why it is built that way, and what running local models against
> real tasks actually taught us.
>
> This is a condensed English edition of the project's engineering log. It keeps the
> reasoning, the measurements and the failures; it drops the day-by-day changelog (a
> condensed version history lives in the [manual's appendix](./Agentic_Manual.md#appendix--version-history)).

**The short version:** most of the engineering in this project is not about making a model
smarter. It is about the fact that small local models fail in specific, repeatable ways,
they fabricate under pressure, they declare success without doing anything, and the
inference server underneath them has real bugs. Each of those got a deterministic
counter-measure, and each counter-measure got a test.

---

## 1. Origin and the from-scratch decision

The project began as part of a fully local AI stack (Ollama for inference, Open WebUI for a
web front end, SearXNG for private search) and grew out of wanting something the web UI could
not give: **an agent that acts on its own**, searching, reading and writing files, running
commands, directly in the terminal.

A browser front end also costs something on hardware where the model is already the
bottleneck. It adds a round trip and re-sends the rendered conversation each turn, which is
overhead you feel on a 24 GB machine running a local model, and none of which a terminal
process pays.

Three options were evaluated: a custom Python agent, [Smolagents](https://github.com/huggingface/smolagents),
and a LangChain ReAct agent. **The custom agent won**, for total control, no hidden magic, a
readable codebase, and immediate startup.

That decision was re-validated repeatedly. A large share of the fixes documented below,
retry branches keyed on specific upstream error strings, a nudge injected between a model's
final answer and the user, sequential model loading to fit 24 GB, required line-level control
over the request/response loop that a framework abstraction would have hidden. The cost is
real, but the tradeoff has paid for itself. The code is now split into twelve modules
under `agentic/` plus nine in `agentic/tools/`, which cost nothing in control: the boundaries follow the layering that was
already implicit, settings, session state, interface strings, safety rails, tools, the loop.

---

## 2. Architecture

### The ReAct loop

```
User → message
  ↓
Model reasons → calls tool(s) → gets results → reasons again … → final answer → User
```

```python
while True:
    response = ollama.chat(model, messages, tools=TOOLS)
    msg = response.message

    if not msg.tool_calls:
        return msg.content              # ← final answer

    messages.append({assistant + tool_calls})
    for tc in msg.tool_calls:
        result = execute(tc.function.name, tc.function.arguments)
        messages.append({role: "tool", content: result})
    # the model sees the results and goes round again
```

The whole conversation lives in memory as a `messages` list and is re-sent every turn.

### Tool schemas come from the code, not from JSON

The Ollama Python SDK extracts each tool's JSON schema from the **function name**, the
**parameter type hints**, and the **docstring** (including its `Args:` block). No hand-written
JSON schemas exist in this project. This was verified directly in `ollama/_utils.py`, which
matters, because it means **improving a docstring measurably improves tool-calling
reliability** (see §4.4).

### Project root confinement

The agent takes a project root at startup, `chdir`s into it, and tells the model about it in
the system prompt. Every file operation is resolved relative to that root, and, since
v2.9.16, **confined** to it (§4.5).

### Key technical decisions

| Decision | Why |
|---|---|
| No framework (LangChain, Smolagents) | Total control, zero hidden magic, readable code, fewer dependencies |
| Messages as plain dicts, not SDK objects | Guaranteed compatibility across SDK versions |
| Docstrings as tool descriptions | The SDK extracts them automatically → better reliability |
| Bilingual system prompt (EN default, `/lang`) | The interface and the model's instructions switch together |
| A timeout on every tool | Prevents hangs on long commands or unreachable URLs |
| An isolated venv | PEP 668 forbids system pip installs on Homebrew Python |
| Nudge, never gate | The agent re-prompts the model; it never silently rewrites or blocks the model's output |

That last row is the project's central UX principle. Every honesty mechanism described below
is a **nudge**: it adds a message and re-runs the loop. None of them censor, rewrite, or
suppress what the model produced. This is deliberate, a censoring layer would hide the
failure mode instead of surfacing it, and would make the agent's behaviour unauditable.

---

## 3. Reliability engineering, part 1: the plumbing

Before you can study whether a model is *honest*, you have to eliminate the cases where the
model never got a fair chance. Five distinct **upstream failure signatures** were found by
running real workloads, each requiring its own retry branch. They are not interchangeable,
and a single generic "retry on error" would have masked what was actually happening.

| Signature | Root cause | Handling |
|---|---|---|
| `Unable to generate parser for this template` | Ollama registry bug ([ollama/ollama#16988](https://github.com/ollama/ollama/issues/16988)) on hf.co GGUFs with an auto-generated tool-call parser. Reproducibly mid-session, not just on the first call | `MAX_TEMPLATE_PARSER_RETRIES`, retry the identical request |
| `XML syntax error` while parsing a tool call | Ollama generated a parser correctly, but the **model** drifts from its own documented tool-call format (Qwen3.5/3.6 family, [#14834](https://github.com/ollama/ollama/issues/14834), [#16383](https://github.com/ollama/ollama/issues/16383), [#16810](https://github.com/ollama/ollama/issues/16810)). Registry maps these models to the Hermes-JSON parser while they were trained on Qwen3-Coder's XML format | `MAX_XML_PARSE_RETRIES`, no upstream fix exists; a retry is the only client-side option |
| `unexpected end of JSON input` | The raw JSON of a tool call's arguments is **truncated mid-generation** by llama-server before the closing braces. Found on a `write_file` of a ~14 KB file in one call | `MAX_JSON_TRUNCATION_RETRIES`, plus the `append_file` tool and a system-prompt rule to write large files in ≤80-line chunks, attacking the cause, not just the symptom |
| A pseudo tool call emitted as **plain text** | The model writes `<function=search_in_files> <parameter=…> … </tool_call>` as its answer instead of invoking the tool-calling API. Confirmed on two unrelated model families | `_looks_like_fake_tool_call()` detects the pattern and retries; previously it slipped through entirely, because `msg.content` was not empty |
| `No user query found in messages` | **Not an Ollama bug — a context overflow.** When the prompt exceeds `num_ctx`, Ollama makes room by dropping the *oldest* messages, and after the system prompt the oldest thing is the user's own instruction. Templates that assert a user message is present then refuse. Reproduced deterministically: identical messages succeed at `num_ctx 8192` and raise at `1024` | A retry cannot help, the prompt has to shrink: one forced compaction, then a message naming the real cause. `_guard_context_overflow` also compacts *before* sending, for every model |

**The fifth one is the one worth reading twice.** Only two of the eighteen models benchmarked carry the assertion, both hf.co GGUFs shipping their own chat template. Every other model answers the question normally — from a conversation the request has been silently deleted from. The refusal is the *good* outcome, because it is the only visible one, and it was initially misdiagnosed as "this model is broken in architect mode". The honest model looked like the faulty one. That is why the guard now runs for every model rather than routing around the ones that complain.

**Why this matters beyond this project:** three of these five were initially mistaken for
model incompetence. In the benchmark campaign (§5), two models "failed" tasks purely because
of the plain-text pseudo-tool-call bug, the task was never attempted, the file never touched.
Attributing that to the model would have been wrong. Measuring local models honestly requires
first knowing which failures belong to the plumbing.

When retries for any of these are exhausted, a configurable **one-time model failover**
(`/failover-model`, off by default) switches to a backup model rather than losing the turn.

### Empty final answers: two distinct causes

- **Context silently capped at 16,384 tokens.** No `ollama.chat()` call passed `options.num_ctx`, so Ollama fell back to its default regardless of the model's real maximum. Verified by inspecting the `-c` flag of the actually-running `llama-server` process: 16384 before, 32768 after. With a "thinking" model (reasoning blocks count against context) and a dozen tool rounds, the window fills and context-shift produces empty or incoherent output. Fixed by reading the real maximum via `ollama.show()` and passing it explicitly, capped at `SAFE_NUM_CTX` so a 1M-context model doesn't exhaust RAM.
- **Thinking without concluding.** `ollama.Message` exposes `.thinking` separately from `.content`. A model can produce a full internal reasoning trace and then stop, without ever converting it into an answer or a tool call, with plenty of context left. Fixed with `MAX_EMPTY_RETRIES`: re-prompt up to twice with an explicit "you produced nothing, finish your answer now", logging a preview of `.thinking` to the audit log for diagnosis.

Both were **verified deterministically with simulated models** rather than by hoping to
reproduce them live: one that fails twice then recovers (proving the retry gives it the chance
it needs), and one that fails forever (proving the agent stops cleanly instead of looping).
Under no circumstance does the user get a silently empty panel.

---

## 4. Reliability engineering, part 2: honesty

This is the part of the project with the least prior art in comparable tools, and the part
with the most negative results worth reporting.

### 4.1 The escalation ladder

Fabrication was not one bug. It appeared as a sequence of increasingly narrow cases, each
found by a real task, each patched, each partially working:

1. **Search returned nothing usable → the model invented plausible headlines.** Real cause found by digging: `search_web` passed no `categories` to SearXNG, so it fell back to `general`, which legitimately ranks hub/category pages ("BBC News World") first for a broad query like "top news today". Not a SearXNG bug, normal general-search behaviour. Fixed by routing news-intent queries to `categories=news` **internally and invisibly**, mirroring how Anthropic's own server-side `web_search` exposes one tool with no category parameter. Verified against the exact query that had made four models fabricate.
2. **The user asked for more items than the search found.** ("That's a top 5, not a top 10.") The model added five invented items with **no additional tool call**, presented identically to the five real ones. Countered with a system-prompt rule: search again for real items, or state honestly how many you actually verified.
3. **A single generic search used to justify three categories.** An "uncensored" model ran one `search_web` scoped to mainstream media, then produced three lists of ten. Countered with a rule requiring a separate search per requested category/source/viewpoint.
4. **Structure fabricated around a thin result**, a bare URI dressed up as an invented table or JSON.
5. **Describing a hypothetical tool result without ever calling the tool**, "returns something like this", followed by precise invented values.

**Cases 1-3 are prompt mitigations, and the log is explicit that this is a weaker class of
fix.** Unlike the plumbing fixes, no code can distinguish a real fact from an invented one, so
effectiveness depends on the model obeying, which measurably degrades on smaller models and
on models uncensored by classic abliteration.

### 4.2 The deterministic layers (v3.0)

Cases 4 and 5 motivated moving from *asking the model to behave* to *checking the output
without a model*:

- **`_grounding_check`**: after the final answer, extract its **hard tokens** (numbers with ≥2 digits, ISO dates, URLs, quoted proper nouns) and substring-search each one in the raw tool results **from that turn**. Anything present in the answer but in no tool result gets flagged and the model is re-prompted once.
- **The claim-vs-action nudge**: if the answer claims "fixed"/"verified" but the turn contains no successful edit (`write_file`/`append_file`/`edit_file` returning its success prefix) and no verification (`lint_file`/`run_tests`/`run_command`), re-prompt once. The "verified" half stands down on a turn made of research tools alone — see [4.2b](#42b-a-nudge-is-only-as-good-as-its-premise).
- **`_duplicate_items`**: two list items describing the *same event* as if they were two. Every other check compares the answer to its **sources**; this one compares the answer to **itself**, a gap the others structurally cannot cover. Observed from `gpt-oss:20b`: item 1 said "seven people were killed" at a named school and item 5 said "nine people were killed, including the shooter" at the same school, one event, two death tolls, four rows apart. Both passed `_grounding_check`, because both figures genuinely appeared in tool results (one from BBC, one from a Wikipedia portal). Detection is a shared **rare multi-word proper noun** between two items.

Both run without an LLM, both are capped at 1 re-prompt, and **both are honest about their
limits**: legitimately derived values (sums, unit conversions) and paraphrased content can
false-positive, which is exactly why they are nudges with a cap of 1 rather than gates. They
do not cover paraphrased structure. They are a layer, not a guarantee.

### Measuring a heuristic before shipping it

`_duplicate_items` is worth recording as a *method*, not just a feature. The first instinct was
that it could not be done deterministically, separating "seven killed" and "nine killed,
including the shooter" from two genuinely different casualty figures looks like it needs
semantics. Rather than argue the point, the rule was measured against **six real answers** from
a cross-model comparison, two of which contained a known duplicate:

| Signal | Real duplicates caught | False positives (4 clean answers) |
|---|---|---|
| Shared rare multi-word proper noun | 1 / 2 | **0** |
| Shared source URL | 2 / 2 | **1**, a live-blog page legitimately sourcing two unrelated stories |

The URL signal was **rejected despite catching more**. A roundup or live-blog page covers many
stories, so a shared link means nothing. The entity signal shipped: it catches roughly half of
real duplicates and, on this corpus, none of the false ones.

That asymmetry is the design rule behind every nudge in this module, **a silent miss costs
nothing; a false alarm teaches the user to ignore the warnings.** Worth noting the predicted
false positive did *not* materialise: an answer mentioning "Strait of Hormuz" in two separate
items stayed quiet, because the second item shared no multi-word entity with the first.

Limitation, stated plainly: six answers is a small corpus and all of them are news-shaped.
Entity density differs in code or research output, and that has not been tested.

The claim-vs-action nudge exists because of two specific measured events: a model that
declared a bug fixed on a file that was **bit-for-bit identical to the original** (confirmed by
`diff` and by running it), and another that reported "citations added" having performed no
write at all.

### 4.2b A nudge is only as good as its premise

The claim-vs-action nudge shipped with a false premise in one of its three shapes, and it took
a user report to find it. `had_verification` is set only by `_VERIFY_TOOLS`, so on a turn made
of `search_web` and `read_file` it is **structurally False** — nothing was executable, so
nothing could have been executed. Any research answer containing "verified" or "confirmed
that" therefore tripped the check, and was told it had claimed to run tests it never ran.

Reported on `gemma-4-26B-A4B-it-uncensored-heretic`, on a `search_web` / `search_web_deep`
turn. The model obeyed, and answered the nudge instead of the user:

> I have not run any automated verification tools (such as `run_tests` or `lint_file`) during
> this turn to verify the accuracy of my answer. The "verification" I referred to was a manual
> comparison of my generated response against the text contained in the search results…

True, cooperative, and useless. The model had not lied, the check had: "verified against the
sources" is the correct use of the word on a search turn. What the user lost was the research
answer the retraction replaced.

**Why this is worse than a missed catch.** §4.2 sets the rule that a silent miss costs nothing
while a false alarm costs trust. This one cost more than trust: correct-to-incorrect flips
outnumber the reverse under self-correction, and a prompt that *asserts* the error before
asking ("You state this was verified, but…") drives the flip rather than prompting a check
— "prompt bias" in [Understanding the Dark Side of LLMs' Intrinsic Self-Correction
(ACL 2025)](https://aclanthology.org/2025.acl-long.1314.pdf). The same survey work that
justifies this whole layer says why: self-correction helps when there is **reliable external
feedback**, and [degrades output without it](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00713/125177/When-Can-LLMs-Actually-Correct-Their-Own-Mistakes).
An edit turn has that oracle. A research turn asked the same question has none, so the nudge
degenerates into exactly the intrinsic self-correction the design set out to avoid. Nudge
pressure is also the documented route to an empty answer here (four nudges in one turn emptied
`qwen-heretic` twice), so a nudge on a false premise spends the budget that a true one needs.

The fix is one clause: the verification half stands down when research tools ran and nothing
was edited. Gating on `had_edit` alone was the first shape considered and **rejected**, because
it loses the most brazen case of the three — a turn with no tool calls whatsoever that says "I
tested it". The premise is true there, and the nudge belongs. Three shapes, all with a premise
that holds:

| Turn | Claim | Behaviour |
|---|---|---|
| edited, no `run_tests` | "tested it" | **nudge** — the oracle exists and went unused |
| no tool calls at all | "I tested it" | **nudge** — nothing happened |
| search/read only, no edit | "verified against the sources" | **silent** — `_grounding_check` covers provenance here, and names the specific unsupported values instead of asking for a wholesale recant |

`test_claim_action_research` pins all three, and pins that the flag can only ever *silence* a
nudge: it subtracts a firing condition, so it cannot cost anyone an answer they would otherwise
have received. The `fix` and `both` branches are untouched — a fix claimed with no edit is
unbacked whether or not the turn did research.

**What this costs, stated rather than buried.** The change removes coverage, and the honest
description is not "the layer got stronger". A model that writes *"I verified this against the
sources"* on a search turn without having compared anything is no longer caught by this check.
`_grounding_check` catches such an answer only where the fabrication surfaces as a hard token —
a number, date, URL or quote. A purely paraphrased claim of diligence now passes both. That is
the same class of hole as the bare `owner/repo` slug in §4.2, and it is a real one.

The defence is that it was never coverage. The check fired on *every* research answer using the
word, whether or not the model had cross-checked anything, so its output carried no information
about the thing it claimed to measure. A detector with no precision does not detect; it emits.
What was lost is a signal that was already noise — but strictly fewer answers are flagged than
before, and the docs should not imply otherwise.

**And the cost is asymmetric in a way the "nudge, never gate" slogan hides.** A nudge does not
suppress an answer, but it re-runs the loop, so what reaches the screen is the second answer;
the first is superseded with nothing announcing it. It survives in the conversation and the
session JSON (not under `--private`), yet no command prints it — `/details` records tool calls,
not answers. So a false-positive nudge does not merely add noise, it *spends a correct answer*,
which is why §4.2's "a silent miss costs nothing" applies here with more force than usual.

Worth recording as a general lesson, since the same trap is set for every check in this module:
a deterministic signal is only deterministic about *what it measures*. `had_verification`
faithfully measured "no verification tool ran" and was never wrong about that; the error was
reading it as "the model did not check its work". Keyword matching a **speech act** while
proving a **fact** is a splice, and the splice is where the false premise hides. The
[Heretic](https://github.com/p-e-w/heretic) project's own refusal detector has the same shape
and, by a published comparison, roughly 11% precision — it counts an answer that complies with
a disclaimer attached as a refusal, because it matches on the phrase rather than the outcome.
The tool that produced the model which surfaced this bug carries a version of the same bug.

### 4.2c A check that never fires: calibrated, or dead?

`_grounding_check` fired **zero times in 264 benchmark runs** — 168 in the model ranking, 96 in
the honesty A/B. `RESULTS.md` §2 originally read that as the layer "doing its job." It does not
follow. But neither does the opposite, and the opposite is the one worth worrying about:
**silence is the same observation for a check that is perfectly calibrated and for one that is
broken.** A deterministic honesty layer that has never been shown to work is a claim, not a
control.

Distinguishing them needs three separate facts, and only the first was covered:

1. **Reachable at runtime.** `test_a56` already drove a fabricated number and date through the
   real `run_agent` and asserted both the injected nudge and the audit record. Not dead code.
2. **Not defeated by volume.** The live hypothesis was that the check is *effectively* dead
   where it matters: it substring-matches against every tool result of the turn concatenated,
   and a real search turn produces ~20 KB of that, so perhaps a haystack that large matches
   anything by coincidence. **False, and by a wide margin.** Injecting an invented URL and
   figure into real banked answers, against their real tool results, was caught **91 of 91**. A
   random 4-digit value collides with the concatenated digit-soup only ~3% of the time; five
   digits 0.3%; six or more, never.
3. **Sensitive to a *realistic* fabrication.** Appending an obviously fake domain is a straw
   man. The failure that actually occurs is a plausible one-digit change to a figure the model
   really did retrieve. On answers verified clean first: **73 of 78 (94%) would have nudged**, 5 stayed silent (measured 2026-08-15 on the banked corpus; this fraction moves as runs are added — the reproducible figure is the 91/91 injection sweep in the test).

So the zero means *nothing needed flagging* — not that the check is broken, and not that the
check is why. `tests/test_grounding_sensitivity.py` pins all of it.

Two methodological notes worth keeping, since both nearly produced a wrong answer:

**The measurement instrument was wrong before the code was.** An early sweep reported that 20
real answers "would already have been flagged", which implied a wiring bug — the function
working in unit tests but starved of data in the loop. It was reading `answer.txt`, which is a
run's whole **stdout**: the agent's own XML-fallback warning (carrying Ollama issue numbers
14834/16383/16810), echoed tool-call JSON, banner. The runtime check sees only `msg.content`.
No bug. When a measurement says the code is broken, check the measurement first.

**A synthetic fixture can flatter or frame the thing it tests.** The first haystack built for
the sensitivity test was almost entirely numbers and showed a **17.8%** four-digit collision
rate against the real corpus's **2.8%**. It would have "demonstrated" that the matcher is
vacuous, by testing a haystack no search turn produces. The fixture is now matched to the
corpus on size *and* digit density, and asserts its own density so it cannot drift — the prose
padding is the control, not filler.

**What remains unverified, and is not hidden by the above:** every positive is synthetic. No
model has been observed fabricating and being caught in the wild, so this measures the
detector, never the deterrent. Paraphrase is uncovered by construction (§4.2, and the blind
spot pinned in `test_grounding_recheck`), and the ~6% that slip silently are unanalysed.

### 4.3 "A clean lint is not proof"

A controlled comparison of four models on one real bug: **all three that attempted a fix
declared themselves "verified" after a clean lint, and every one of them shipped at least one
guaranteed crash.**

The root cause is categorical, and was confirmed by direct diagnostic testing:

- **Inconsistent dict keys between functions** are invisible to linters *and* to static analysis (Pyright) on untyped dicts. Only real execution finds them.
- **Possibly-unbound variables** are caught perfectly by Pyright when it is invoked, but **no tested model ever invoked it spontaneously.**

Two changes followed: the self-check nudge stopped presenting `lint_file` as sufficient and
started pushing toward actually running the code, and `run_command` was promoted to count as
real verification. Later, `write_file`/`edit_file` gained an automatic `ast.parse` check that
warns (without blocking) when the resulting `.py` is syntactically invalid, motivated by a
model that truncated its own output across 8 full-file rewrites over ~25 minutes while
`write_file` cheerfully reported "File written" every time.

### 4.4 Tool descriptions as a reliability lever

Repeated failures where models invented argument names (`lines_to_add`, `directory_path`,
`file_name`) prompted research into tool-description quality. Anthropic's guidance cites
detailed descriptions (3-4+ sentences: what, when, when *not* to, a concrete example) as the
single most important factor for tool-calling reliability; this project's descriptions were
one sentence with one-word arguments. After confirming the Ollama SDK really does forward the
docstring `Args:` block into the schema, the four implicated tools were rewritten with full
descriptions and inline examples.

**Result: partial.** A follow-up test disproved the tempting hypothesis that abliteration
caused it, the official, non-abliterated `mistral-small3.2` reproduced the identical failure
against the improved descriptions, guessing wrong argument names even after reading an error
message that named the correct ones. Several abliterated Gemma models never showed the problem
at all. The common variable is the Mistral Small family itself, not censorship. **Description
quality helps; it does not override a model's training.**

### 4.5 A real security bug, found by adversarial testing

A 10-test MCP suite built from external research (MCP-Bench, 2026 developer reports, the tool-poisoning literature) found that `write_file`, `edit_file`, `read_file`, `lint_file`,
`create_directory` and `/add` had **never verified that a path stayed inside the project
folder**. An absolute path pointing anywhere on the machine was accepted without complaint.

Fixed with canonicalization plus `Path.relative_to` confinement, and covered by 8 test cases
including the exact escape that was observed. This is the clearest argument in the project's
history for adversarial testing over code review: the code had been read many times.

---

## 5. The benchmark campaign

18 models were run through four identical tasks on the same machine (Apple Silicon M4 Pro,
24 GB): **factual research** (with real external fact-checking of each individual claim, not a
re-read of the answer), **pure reasoning** (a closed-form puzzle), **code** (a real bug,
verified objectively by `pytest` rather than by the model's say-so), and a **multi-step task**.

Since 11 August 2026 the reported score is `pass^k`: **the minimum across repeats**, so a model
counts only what it delivers *every* time. That single change is the campaign's most useful
result, and it is written up below.

### What the campaign found

**Reasoning capacity is not the differentiator.** Every remaining model solved the reasoning
task. Differentiation came entirely from **tool-calling reliability and factual honesty under
pressure**. A model that codes and reasons as well as any other can still fabricate an entire
answer on an open-ended research task.

**Size did not buy quality on this hardware.** In the final ranking the two largest dense
models (26B) gained no net advantage; one failed outright. Separately, **5 of 8 Heavy/Very-heavy
models produced zero output in 8 minutes** on a simple tool-free question: not a quality
problem, a pure latency problem that makes them unusable interactively regardless of competence.

The `pass^2` re-run sharpened this into a mechanism rather than a slogan. The two 26B models
**beat every other model on pure reasoning** — a perfect 25/25 against the eventual winner's
17 — and still finished 31 points behind, because they paged **16–19 GB** and never completed
the report task. The winner, a 9B at 7.0 GB, never touched swap once across 8 runs. On 24 GB,
*memory headroom dominates capability*: it is not that the big models are worse, it is that
they cannot finish. A 35B mixture-of-experts that activates ~3B per token was the control —
it fits, swaps nothing, times out less often than the winner does, and still loses, which
locates the remaining gap in agentic tool use rather than in memory.

**One run per model is not a measurement, and this campaign proved it on itself.** Every model
was given a second rep on 11 August. Eight of the ten re-run models scored *lower*, the worst
by 17 points, and the ranking changed at the top: the leader had passed the agentic task on one
run and failed it on the next (`[25, 9]`), while the new leader passed it twice (`[25, 25]`).
The old leader still has the highest *mean* in the file. It is simply not the most dependable
model, and for an agent that runs unattended, dependability is the property that matters.
Two models held their score exactly across both reps — `gpt-oss:20b` and `gemma4:26b-mlx` —
which is a stronger result than their rank suggests.

One honest caveat on that story, found while auditing the write-up rather than while running
it: for the ten models carried over from the first campaign, the two reps were executed three
days and eight commits apart, so their rep-to-rep deltas mix model variance with harness drift.
The five models added last ran both reps on a single build and are unaffected. The lesson
survives — a second run moved almost everything — but the *size* of each individual drop is not
a clean measurement, and the ranking says so.

**Fact-checking changed the conclusions in both directions.** Two claims initially judged
fabricated turned out to be **correct** on verification, and the assessment was corrected.
Conversely, models that looked fine on a read-through had real errors (a casualty figure of 15
instead of 21; an EU AI Act provision described as active when it is deferred to 2027/2028).
Reading an answer is not evaluating it.

**Uncensoring method matters more than uncensoring.** Models uncensored by classic abliteration
(`huihui_ai/*`) fabricated repeatedly under pressure. Models uncensored via the **Heretic**
method (measured KL divergence) included two of the project's best performers. The plausible
explanation, untested, is that abliteration optimises for maximal compliance at the cost of
adherence to system-prompt constraints.

**A methodological limit worth recording:** heavy models (17+ GB) could not be benchmarked as
background tasks, the harness killed them 2-5 minutes in, during load/inference. Three
different fixes aimed at output-inactivity timeouts all failed, while a bare `sleep 300` was
also killed and a pure output-producing bash loop survived 10 minutes. The common variable is
a large `llama-server` child process (14-19 GB RSS), i.e. a **resource** limit, not an
inactivity timeout. Heavy models must be benchmarked in the foreground, one at a time.

---

## 6. The open problem: end-to-end multi-bug fixing

**Status: NOT SOLVED.** This is the project's most significant negative result, and it is
documented as an open problem rather than a conclusion.

### The fixture

A ~200-line menu-driven text game reconstructed from a real user incident, preserved as
`benchmarks/game_py_bugfix_original.py` with a verified reference solution alongside it. It
contains four known bugs plus a fifth **that was only discovered by actually playing the
game**, never by linting, and never by the two most careful models.

### The result

Five full attempts, with explicit scaffolding (activate the project → run Pyright diagnostics
→ fix → actually execute → don't declare done until both are clean):

| Model | Outcome |
|---|---|
| `gpt-oss:20b` | Used both diagnostic tools correctly, then produced a file **bit-for-bit identical to the buggy original**, and declared the bug fixed. False, confirmed by `diff` and execution |
| `Agen/gemma-4-26B…heretic` | **Corrupted the file**: 8 full-rewrite attempts over ~25 minutes, each truncated mid-generation, final file cut at line 50 with 155 lines lost, `write_file` reporting success every time |
| `qwen3.5:4b` | The only model to run real verification unprompted. On the full task it *deleted* a needed assignment while fixing something else, making things worse. After the syntax-check fix, it caught its own damage 5 times and kept iterating instead of declaring false success, a real, measurable improvement, but hit the 25-round safety limit still mid-progress, file still broken |

**Only a fix applied by hand produced a genuinely working file**, verified by playthroughs
covering every menu option.

### Reading of the result

The limiting factors appear to be (a) an insufficient tool-round/context budget for a
multi-bug task attempted in one shot, (b) a tendency to lose track of some bugs while fixing
others, and (c) at least one case of frankly false self-assessment.

Note the honest asymmetry: **the v2.9.20 fix worked exactly as designed on its narrow goal**
(preventing silent corruption, confirmed, measurable), while **the underlying task remained
unsolved.** Those are separate claims and the project keeps them separate.

Untried leads, in priority order: decompose into one bug at a time with validation between
each; raise `MAX_TOOL_ROUNDS` for this task class (one run was cut off mid-progress); retest
`qwen3-coder:30b` with the current tooling; use cross-model review (`/review-by`, since
implemented) as an adversarial second opinion; and establish whether this fixture, a state
machine with many shared dict keys, is structurally harder than a representative real task.

---

## 7. Feature design notes

**Local RAG (`search_semantic`).** bge-m3 embeddings in a stdlib SQLite index with incremental
re-indexing. Deliberately **no ChromaDB, no FAISS**, zero added dependencies, at the cost of
a brute-force cosine scan that is entirely adequate at single-project scale.

**Architect/editor (`/architect`).** Model A plans with read-only tools, model B executes with
all tools, **strictly sequentially loaded** so two models are never resident at once, a hard
24 GB constraint that shaped the design. Live testing surfaced a failure the design hadn't
anticipated: a small architect model burned all 25 rounds retrying write tools it wasn't
allowed to have. Hence `MAX_READONLY_REFUSALS`, after N refusals, push it to write the plan
as prose.

**Context compaction.** Two stages: lossless cleanup of old bulky tool results first (free, no
model call), then a structured summary of older turns, with the system prompt and the last 3
turns kept verbatim and never cut mid-tool-call. Triggered on Ollama's **real**
`prompt_eval_count`, not an estimate. **Auto-compaction ships OFF by default**, the dominant
community complaint about this feature elsewhere is auto-compaction destroying working context
by surprise, so nothing compacts until you opt in.

**Git checkpoints (`/undo`).** A shadow git repository snapshots the project before each turn's
first write. It works in non-git projects and never touches your own history, replacing an
earlier all-or-nothing in-memory undo.

**Search failover.** When SearXNG returns nothing usable, `search_web` fails over invisibly to
a `duckduckgo` MCP server. The model never chooses, same principle as the news routing:
one tool, hidden routing.

**Skills.** Reusable `SKILL.md` workflows with three-level progressive disclosure (name +
description always in the prompt; full instructions loaded on demand; referenced files read as
needed). The format is the open standard, so skills are portable to and from Claude Code,
Cursor and Codex.

**One skill is auto-loaded, and that is a deliberate hole in tier 2.** `web-answer-format`
(sections planned from the question, answer first, a date and a source per item) is injected
code-side, as an already-completed `load_skill` call, when the user's message carries
recency/news wording or an explicit "look it up" verb. The reasoning is the one behind the
forced search and the news routing: tier 2 assumes the model *chooses* to load, and a small
local model mostly does not — it answers from the first result in one flat, undated list. A
prompt rule is a suggestion; this is not. The trigger is deliberately narrow (an ordinary coding
question does not match) and it does not re-inject while the body is still in the last 24
messages. `latest` is the one loose term — it also fires on "upgrade to the latest pandas" — and
is kept because a false positive costs 1,287 tokens, 2% of the default 64K window, not a wrong
answer. That was the prediction; the run below tested it and came out better than predicted, the
false positive produced a *better-organised* dependency answer rather than a distorted one. On a
window shrunk to 4K in `/parameters` that same body is a third of the budget and will trip the
overflow guard; the test stub at `num_ctx=4096` shows exactly that.

Measured live on `gemma4:12b-mlx` before shipping, six runs, one turn each:

| Run | Result |
|---|---|
| "latest international news today" **with** the skill | Three themed sections, bold headline + date + real source per item, closing coverage note |
| Same question worded to miss the trigger (**no** skill) | Flat bullet list, no sections, no per-item dates, a **2023** Reuters piece inside a "past 24 hours" roundup, no coverage note |
| Same question in French | Sections, items and coverage note **all in French** — an English skill body injected as a tool result does not pull the answer into English |
| Interactive + `--private` | Auto-load fires on the interactive call site too, and `_audit` no-ops cleanly with no log |
| "should I upgrade this project to the latest pandas?" (the loose-trigger case) | Not a news brief: sections by breaking change, a what-breaks/the-fix pair each, an incremental-upgrade recommendation, sources throughout, and **no** dates on items — the date rule was not misapplied to a question that isn't time-sensitive |
| "compare SearXNG and Whoogle" (forced-search prefix **and** auto-load on one message) | The comparison template, not the news one: sections by criterion, an explicit `## Verdict` with a choose-X-if recommendation, coverage note |

Two real defects came out of those runs and were fixed in the skill, which is the argument for
running them: the model reformatted a sourced `2026/07/13` into `Jul 13, 2026`, which
`_grounding_check` matches by substring or digit-run and therefore flagged — a nudge, and a
wasted generation, caused by the skill's own "date every item" rule. It now says to copy the
date in the form the source gives it. And the French answer closed on a literal English
`Coverage:` label, a leaked template; the skill now says to translate the label too.

**The planning step needed code, and the cheap version was the right one.** Seven live runs in,
the model wrote its section plan every time and searched *once* every time, so the skill was
describing coverage it never produced. Prompt rewrites had already been spent on it. Surveying
how the field solves this (LangChain's MultiQueryRetriever, RAG-Fusion, GPT-Researcher, Open
Deep Research) turns up one shared answer: the model emits a *list* of queries in a single
output and **code** fans out, map/reduce style, rather than the agent choosing to make N
sequential tool calls.

The version that fits here is cheaper still, because the material was already being paid for and
thrown away — twice. `_fetch_rss_headlines` pulled every feed in `NEWS_RSS_FEEDS` and filtered
locally, so splitting it into `_rss_pool` (fetch once, cache for `SEARCH_CACHE_TTL`) and
`_match_rss` (pure local filtering) makes a second angle cost nothing; and the search itself
requests nine results, reads three, and discarded six. `search_web_deep(query, sections=[...])`
sends exactly **one** query upstream and gets its breadth from what has already arrived. The
fan-out considered first would have charged seven HTTP requests per angle — twenty-one for three
sections — which is precisely what gets a self-hosted SearXNG rate-limited, and why it was
dropped rather than built.

The `sections` argument alone was not enough. Ollama's schema converter emits the array as
`"items": null` and marks every parameter required regardless of default, and across live runs
the model passed the argument about half the time while writing `Sections: A, B, C` in prose
every time. So `_route_planned_sections` reads that line and fills the argument in — the model
states intent, the code carries it out, exactly as with news-category routing and the forced
search. Its premise is the model's own declaration from this turn, not an inference about what
it should have wanted, which is what makes it safe under §4.2b. **Not yet exercised live**: in
both runs since it was added the model supplied the argument itself, so only the unit tests have
seen it fire.

**The first version labelled each source with its section in code, and that was the wrong half
of the problem to automate.** Lexical matching mis-filed something in every one of three live
runs: `east` inside `southeast` put an Indonesian earthquake in the Middle East; requiring both
words emptied "Asia-Pacific" over a story that says Asia and never Pacific; "east of Tokyo" then
put Japan in the Middle East while a full two-term match was available. Each fix was correct and
the next run found the next hole, which is the signature of automating a semantic job with a
lexical tool. The model, meanwhile, had corrected one of those mis-filings *unprompted* — it
knows Japan is in Asia — and the worst symptom was code emitting "no matching headline for this
section" while the pool held two Japanese stories, an absence asserted as fact that no honesty
layer can catch because it did come from a tool result.

So the division of labour inverted: **code guarantees breadth, the model does the filing.** And
breadth turned out to be free twice over. `search_web_deep` asks SearXNG for nine results, reads
three, and used to discard the other six — title, URL and snippet, already downloaded in the
same response. Returning them as "Further result — not opened" gives a sectioned answer its
material on **any** topic, not just news, where the RSS pool happens to supply the same thing.
That closed the real gap in the first design, which only ever worked for news; a model
comparison or a how-to got one query, three pages, and no section coverage at all.

Selection and labelling then had to be told apart, because removing the labelling removed the
selection with it and a Europe section came back empty while the pool held European stories.
Lexical matching is right for "is this item about Europe" and wrong for "which heading does this
belong under". Section names now *select* items into one **unlabelled** pool; the model files
them.

**Free breadth turned out to have a news-shaped hole in it.** Returning the results the search
already had was safe for every other topic, but SearXNG's news category answers "international
news today" with Reuters pieces from 2023 and an undated 2025 page, and the model wrote them up
as today's news — the exact failure `_NEWS_INTENT_RE` routing exists to prevent, reintroduced by
a change that had nothing to do with news. `_freshness_filter` drops results a news query dates
older than 30 days, and undated ones too, since undated is indistinguishable from stale for a
"today" question. The fallback needed two attempts: "read a stale page rather than nothing"
sounds prudent, but on this instance *every* result was stale, so it fired every time and the
model preferred those full-text pages to the dated RSS summaries. Stale pages are now a fallback
only when there is no RSS either.

**The all-purpose half needed its own guarantee.** Widening the auto-load trigger to open
questions ("how do I build…", "what are the best…", "compare X vs Y") made the skill load for
"how do I build a web scraper?" — and the model still answered from memory, with **four
fabricated source URLs**. The grounding check caught the URLs; nothing was asking why there were
no real ones. So a nudge, on a premise deterministic on both sides: the skill was auto-loaded
(code judged this a web question) and no read or search tool ran all turn. It reads the marker
`load_skill` itself writes, so it cannot drift from the auto-load's definition. Live, it fired
once and the rewritten answer cited realpython, geeksforgeeks and dev.to — real pages, and one
extra generation spent only in the failing case.

The method worth keeping is not the feature. Three of my own mis-matches survived into three
separate nine-minute runs, and every one was reproducible in seconds by calling `_match_rss`
against the real `_rss_pool()` in a REPL. Fixtures prove the rules you thought of; live data
proves the ones you did not.

Honest limits: n=1 per condition on one model, not a benchmark campaign, and the two news
conditions differ slightly in wording because the trigger had to be avoided. Adherence is
partial — the *shape* held in all six runs, the "one deep search per section" planning step did
not; the model ran a single search and derived its sections from what came back. The last two
runs are also the only ones made against the final skill text: the date-form and
answer-in-the-user's-language rules were added between, so the news and French answers above
were produced by a slightly earlier body.

**Thinking Mode (`THINK_MODE`).** The agent never passed `think` at all, so every thinking
model ran with reasoning on. That was
measured as expensive long before it was addressed — `qwen-heretic` spends most of its output
on a trace the user never sees — but it stayed unimplemented because the obvious fix, defaulting
it off, trades an unknown amount of quality for a known amount of speed. `THINK_MODE` ships as
an opt-in with `default` meaning *send nothing*, so the prior behaviour and the entire benchmark
campaign remain exactly as measured.

**Detection is the whole design.** A top-level `think` sent to a model without the capability is
an Ollama 400 that kills the turn, and it is the most reported bug in every other client that
shipped this feature (openclaw #80332, Continue #11265, crush #2713, claude-code-router
#972/#1046, qwen-code #1377). In all of them the trigger is identical: a thinking setting that
outlives a model switch. `/model` makes that reachable here, so the capability is checked per
call, from `ollama.show().capabilities` — the same source and the same one-lookup-per-model
economy as the tool check beside it. Nothing is hardcoded, so a model pulled tomorrow answers
for itself.

**What `capabilities` cannot tell you, measured 2026-08-20 on this machine:**

| Model | `off` | `low` → `high` |
|---|---|---|
| `gemma4:12b-mlx` | works — 391 → 5 output tokens, 9.8 s → 0.8 s | no effect (923 vs 933 chars) |
| `gpt-oss:20b` | **ignored** — reasoned *more* than default (955 vs 699 chars) | works — 120 → 1762 chars |
| `qwen-heretic:latest` | works — 600 → 6 tokens, 22.8 s → 0.4 s | no effect (byte-identical traces) |

Ollama exposes thinking as one boolean capability and never says whether a model reads a bool
(`enable_thinking`, the Qwen family) or a level (`Reasoning: <level>`, gpt-oss). So `off` on a
level-only model is a documented silent no-op, and a level on a bool-only model switches
thinking on rather than sizing it. Neither is detectable in advance. Guessing from the chat
template was considered and dropped: it is a heuristic, and it is wrong on exactly the model
that matters most here — `gemma4:12b-mlx`, the default, is an MLX build whose Ollama template
is a bare `{{ .Prompt }}` passthrough with no reasoning branch, and it honours `think` anyway.
The prediction from reading the template would have been the opposite of the measurement.
(`qwen3.5:4b` has the same passthrough template and was not probed, so it is untested rather
than known.) What
the code does instead is send what was asked, gate what would error, and remember what got
refused (`state._think_rejected`, one retry without the argument) — the same shape as the other
plumbing signatures in `run_agent`, and the only one whose retry *changes* the request rather
than repeating it.

**Speed is not the interesting number.** On the same arithmetic question `gemma4:12b-mlx`
answered correctly with thinking on and wrongly with it off. A wider sweep (3 tasks × 3 seeds)
put thinking-on at 5/9 and off at 4/9, but that comparison is not trustworthy and is recorded
here as unresolved rather than as a finding: it ran at `num_predict` 600 against a shipped
default of 4096, and the tight cap manufactured its own failure mode — thinking-on returned an
empty answer on 4 of 9 runs by exhausting the budget mid-trace. Settling it means re-running T1
and T3 under the real protocol, which has not been done. Until then the honest claim is that
`off` is a large, measured speed win of unmeasured cost, which is why it is not the default.

---

## 8. Known limitations

- **Structure fabrication around a thin result, not solved, probably not solvable by prompt rules alone.** An active 2026 research area; confabulation is a structural property of probabilistic generation, not a deliberate lie. The real but unimplemented lead is a second verification pass comparing the final answer literally against raw tool output, rather than relying on the model to self-censor.
- **End-to-end multi-bug fixing, not solved** (§6).
- **Semantic citation verification is out of scope.** `_grounding_check` verifies that cited tokens *appear* in a tool result. Whether a claim faithfully reflects its source is not checked; `/review-by` is the partial mitigation.
- **An unbacked claim of having checked the sources is not caught on a research turn.** The claim-vs-action nudge stands down there deliberately (§4.2b), because `had_verification` cannot be true on a turn with nothing to execute, so the check was firing on every research answer that used the word "verified". `_grounding_check` still covers such a turn wherever the fabrication surfaces as a number, date, URL or quote; a purely paraphrased claim of diligence passes both.
- **A superseded answer is not shown anywhere.** Nudges never rewrite or block output, but they re-prompt, so the answer you read is the one after the nudge. The one before it is kept in the conversation and the session JSON (not under `--private`) and no command prints it — `/details` records tool calls, not answers.
- **MCP `taskSupport` capability negotiation is not implemented.** Tools requiring it fail cleanly rather than crashing.
- **macOS-centric.** `termios`, `ollama stop`, and several paths assume Unix/macOS.
- **Ollama-only, by design, permanently.** This is the one entry here that is not a gap. The
  project exists so that everything stays on your machine: no API keys, no data leaving the
  computer. A remote endpoint would break that guarantee rather than extend the tool.
- **The repo map is shallower than Aider's.** `repo_map` ranks files with PageRank over a
  name-usage graph, but it derives definitions from a keyword-and-suffix match on
  tree-sitter node types rather than per-language query files, so it extracts names and
  parameter lists rather than full typed signatures. Verified on JavaScript, Go, Rust,
  Java, C and Ruby; other grammars are untested and may yield nothing.
- **No packaging yet**: `launch.sh` and a venv rather than `pip install`.

The last four are the active roadmap.

---

## 9. How this project verifies things

Three working rules, all of which were adopted after being violated:

1. **Never claim something works from reading the code.** Every feature ships with a deterministic test. The suite runs offline, no Ollama, no network, no writes to real config, using monkeypatched `ollama.chat` and temp directories, each test in its own process because several deliberately mutate module globals.
2. **Prefer simulated models to lucky reproductions.** The empty-response and failover fixes were validated with fake models scripted to fail a specific number of times, which is reproducible; waiting for a real model to misbehave is not.
3. **Distinguish "the fix worked" from "the problem is solved."** They are logged as separate claims throughout this document, because conflating them is how a project convinces itself it is finished.

The corollary is that this document reports negative results at the same volume as positive
ones. A local-agent project that only documented its wins would be describing a different
piece of software than the one in this repository.
