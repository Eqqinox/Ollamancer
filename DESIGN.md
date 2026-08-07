# Agentic_1A — Design & engineering history

> How this agent is built, why it is built that way, and what nine months of running local
> models against real tasks actually taught us.
>
> This is a condensed English edition of the project's engineering log. It keeps the
> reasoning, the measurements and the failures; it drops the day-by-day changelog (a
> condensed version history lives in the [manual's appendix](./Agentic_Manual.md#appendix--version-history)).

**The short version:** most of the engineering in this project is not about making a model
smarter. It is about the fact that small local models fail in specific, repeatable ways —
they fabricate under pressure, they declare success without doing anything, and the
inference server underneath them has real bugs. Each of those got a deterministic
counter-measure, and each counter-measure got a test.

---

## 1. Origin and the from-scratch decision

The project began as part of a fully local AI stack (Ollama for inference, Open WebUI for a
web front end, SearXNG for private search) and grew out of wanting something the web UI could
not give: **an agent that acts on its own** — searching, reading and writing files, running
commands — directly in the terminal.

Three options were evaluated: a custom Python agent, [Smolagents](https://github.com/huggingface/smolagents),
and a LangChain ReAct agent. **The custom agent won**, for total control, no hidden magic, a
readable codebase, and immediate startup.

That decision was re-validated repeatedly. A large share of the fixes documented below —
retry branches keyed on specific upstream error strings, a nudge injected between a model's
final answer and the user, sequential model loading to fit 24 GB — required line-level control
over the request/response loop that a framework abstraction would have hidden. The cost is
real, but the tradeoff has paid for itself. The code is now split into fourteen modules
under `agentic/`, which cost nothing in control: the boundaries follow the layering that was
already implicit — settings, session state, interface strings, safety rails, tools, the loop.

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
JSON schemas exist in this project. This was verified directly in `ollama/_utils.py` — which
matters, because it means **improving a docstring measurably improves tool-calling
reliability** (see §4.4).

### Project root confinement

The agent takes a project root at startup, `chdir`s into it, and tells the model about it in
the system prompt. Every file operation is resolved relative to that root — and, since
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
suppress what the model produced. This is deliberate — a censoring layer would hide the
failure mode instead of surfacing it, and would make the agent's behaviour unauditable.

---

## 3. Reliability engineering, part 1 — the plumbing

Before you can study whether a model is *honest*, you have to eliminate the cases where the
model never got a fair chance. Four distinct **upstream failure signatures** were found by
running real workloads, each requiring its own retry branch — they are not interchangeable,
and a single generic "retry on error" would have masked what was actually happening.

| Signature | Root cause | Handling |
|---|---|---|
| `Unable to generate parser for this template` | Ollama registry bug ([ollama/ollama#16988](https://github.com/ollama/ollama/issues/16988)) on hf.co GGUFs with an auto-generated tool-call parser. Reproducibly mid-session, not just on the first call | `MAX_TEMPLATE_PARSER_RETRIES` — retry the identical request |
| `XML syntax error` while parsing a tool call | Ollama generated a parser correctly, but the **model** drifts from its own documented tool-call format (Qwen3.5/3.6 family — [#14834](https://github.com/ollama/ollama/issues/14834), [#16383](https://github.com/ollama/ollama/issues/16383), [#16810](https://github.com/ollama/ollama/issues/16810)). Registry maps these models to the Hermes-JSON parser while they were trained on Qwen3-Coder's XML format | `MAX_XML_PARSE_RETRIES` — no upstream fix exists; a retry is the only client-side option |
| `unexpected end of JSON input` | The raw JSON of a tool call's arguments is **truncated mid-generation** by llama-server before the closing braces. Found on a `write_file` of a ~14 KB file in one call | `MAX_JSON_TRUNCATION_RETRIES`, plus the `append_file` tool and a system-prompt rule to write large files in ≤80-line chunks — attacking the cause, not just the symptom |
| A pseudo tool call emitted as **plain text** | The model writes `<function=search_in_files> <parameter=…> … </tool_call>` as its answer instead of invoking the tool-calling API. Confirmed on two unrelated model families | `_looks_like_fake_tool_call()` detects the pattern and retries; previously it slipped through entirely, because `msg.content` was not empty |

**Why this matters beyond this project:** three of these four were initially mistaken for
model incompetence. In the benchmark campaign (§5), two models "failed" tasks purely because
of the plain-text pseudo-tool-call bug — the task was never attempted, the file never touched.
Attributing that to the model would have been wrong. Measuring local models honestly requires
first knowing which failures belong to the plumbing.

When retries for any of these are exhausted, a configurable **one-time model failover**
(`/failover-model`, off by default) switches to a backup model rather than losing the turn.

### Empty final answers — two distinct causes

- **Context silently capped at 16,384 tokens.** No `ollama.chat()` call passed `options.num_ctx`, so Ollama fell back to its default regardless of the model's real maximum. Verified by inspecting the `-c` flag of the actually-running `llama-server` process: 16384 before, 32768 after. With a "thinking" model (reasoning blocks count against context) and a dozen tool rounds, the window fills and context-shift produces empty or incoherent output. Fixed by reading the real maximum via `ollama.show()` and passing it explicitly, capped at `SAFE_NUM_CTX` so a 1M-context model doesn't exhaust RAM.
- **Thinking without concluding.** `ollama.Message` exposes `.thinking` separately from `.content`. A model can produce a full internal reasoning trace and then stop, without ever converting it into an answer or a tool call — with plenty of context left. Fixed with `MAX_EMPTY_RETRIES`: re-prompt up to twice with an explicit "you produced nothing, finish your answer now", logging a preview of `.thinking` to the audit log for diagnosis.

Both were **verified deterministically with simulated models** rather than by hoping to
reproduce them live: one that fails twice then recovers (proving the retry gives it the chance
it needs), and one that fails forever (proving the agent stops cleanly instead of looping).
Under no circumstance does the user get a silently empty panel.

---

## 4. Reliability engineering, part 2 — honesty

This is the part of the project with the least prior art in comparable tools, and the part
with the most negative results worth reporting.

### 4.1 The escalation ladder

Fabrication was not one bug. It appeared as a sequence of increasingly narrow cases, each
found by a real task, each patched, each partially working:

1. **Search returned nothing usable → the model invented plausible headlines.** Real cause found by digging: `search_web` passed no `categories` to SearXNG, so it fell back to `general`, which legitimately ranks hub/category pages ("BBC News World") first for a broad query like "top news today". Not a SearXNG bug — normal general-search behaviour. Fixed by routing news-intent queries to `categories=news` **internally and invisibly**, mirroring how Anthropic's own server-side `web_search` exposes one tool with no category parameter. Verified against the exact query that had made four models fabricate.
2. **The user asked for more items than the search found.** ("That's a top 5, not a top 10.") The model added five invented items with **no additional tool call**, presented identically to the five real ones. Countered with a system-prompt rule: search again for real items, or state honestly how many you actually verified.
3. **A single generic search used to justify three categories.** An "uncensored" model ran one `search_web` scoped to mainstream media, then produced three lists of ten. Countered with a rule requiring a separate search per requested category/source/viewpoint.
4. **Structure fabricated around a thin result** — a bare URI dressed up as an invented table or JSON.
5. **Describing a hypothetical tool result without ever calling the tool** — "returns something like this", followed by precise invented values.

**Cases 1–3 are prompt mitigations, and the log is explicit that this is a weaker class of
fix.** Unlike the plumbing fixes, no code can distinguish a real fact from an invented one, so
effectiveness depends on the model obeying — which measurably degrades on smaller models and
on models uncensored by classic abliteration.

### 4.2 The deterministic layers (v3.0)

Cases 4 and 5 motivated moving from *asking the model to behave* to *checking the output
without a model*:

- **`_grounding_check`** — after the final answer, extract its **hard tokens** (numbers with ≥2 digits, ISO dates, URLs, quoted proper nouns) and substring-search each one in the raw tool results **from that turn**. Anything present in the answer but in no tool result gets flagged and the model is re-prompted once.
- **The claim-vs-action nudge** — if the answer claims "fixed"/"verified" but the turn contains no successful edit (`write_file`/`append_file`/`edit_file` returning its success prefix) and no verification (`lint_file`/`run_tests`/`run_command`), re-prompt once.
- **`_duplicate_items`** — two list items describing the *same event* as if they were two. Every other check compares the answer to its **sources**; this one compares the answer to **itself**, a gap the others structurally cannot cover. Observed from `gpt-oss:20b`: item 1 said "seven people were killed" at a named school and item 5 said "nine people were killed, including the shooter" at the same school — one event, two death tolls, four rows apart. Both passed `_grounding_check`, because both figures genuinely appeared in tool results (one from BBC, one from a Wikipedia portal). Detection is a shared **rare multi-word proper noun** between two items.

Both run without an LLM, both are capped at 1 re-prompt, and **both are honest about their
limits**: legitimately derived values (sums, unit conversions) and paraphrased content can
false-positive, which is exactly why they are nudges with a cap of 1 rather than gates. They
do not cover paraphrased structure. They are a layer, not a guarantee.

### Measuring a heuristic before shipping it

`_duplicate_items` is worth recording as a *method*, not just a feature. The first instinct was
that it could not be done deterministically — separating "seven killed" and "nine killed,
including the shooter" from two genuinely different casualty figures looks like it needs
semantics. Rather than argue the point, the rule was measured against **six real answers** from
a cross-model comparison, two of which contained a known duplicate:

| Signal | Real duplicates caught | False positives (4 clean answers) |
|---|---|---|
| Shared rare multi-word proper noun | 1 / 2 | **0** |
| Shared source URL | 2 / 2 | **1** — a live-blog page legitimately sourcing two unrelated stories |

The URL signal was **rejected despite catching more**. A roundup or live-blog page covers many
stories, so a shared link means nothing. The entity signal shipped: it catches roughly half of
real duplicates and, on this corpus, none of the false ones.

That asymmetry is the design rule behind every nudge in this module — **a silent miss costs
nothing; a false alarm teaches the user to ignore the warnings.** Worth noting the predicted
false positive did *not* materialise: an answer mentioning "Strait of Hormuz" in two separate
items stayed quiet, because the second item shared no multi-word entity with the first.

Limitation, stated plainly: six answers is a small corpus and all of them are news-shaped.
Entity density differs in code or research output, and that has not been tested.

The claim-vs-action nudge exists because of two specific measured events: a model that
declared a bug fixed on a file that was **bit-for-bit identical to the original** (confirmed by
`diff` and by running it), and another that reported "citations added" having performed no
write at all.

### 4.3 "A clean lint is not proof"

A controlled comparison of four models on one real bug: **all three that attempted a fix
declared themselves "verified" after a clean lint, and every one of them shipped at least one
guaranteed crash.**

The root cause is categorical, and was confirmed by direct diagnostic testing:

- **Inconsistent dict keys between functions** are invisible to linters *and* to static analysis (Pyright) on untyped dicts. Only real execution finds them.
- **Possibly-unbound variables** are caught perfectly by Pyright when it is invoked — but **no tested model ever invoked it spontaneously.**

Two changes followed: the self-check nudge stopped presenting `lint_file` as sufficient and
started pushing toward actually running the code, and `run_command` was promoted to count as
real verification. Later, `write_file`/`edit_file` gained an automatic `ast.parse` check that
warns (without blocking) when the resulting `.py` is syntactically invalid — motivated by a
model that truncated its own output across 8 full-file rewrites over ~25 minutes while
`write_file` cheerfully reported "File written" every time.

### 4.4 Tool descriptions as a reliability lever

Repeated failures where models invented argument names (`lines_to_add`, `directory_path`,
`file_name`) prompted research into tool-description quality. Anthropic's guidance cites
detailed descriptions (3–4+ sentences: what, when, when *not* to, a concrete example) as the
single most important factor for tool-calling reliability; this project's descriptions were
one sentence with one-word arguments. After confirming the Ollama SDK really does forward the
docstring `Args:` block into the schema, the four implicated tools were rewritten with full
descriptions and inline examples.

**Result: partial.** A follow-up test disproved the tempting hypothesis that abliteration
caused it — the official, non-abliterated `mistral-small3.2` reproduced the identical failure
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

~15 models were run through four identical tasks on the same machine (Apple Silicon M4 Pro,
24 GB): **factual research** (with real external fact-checking of each individual claim, not a
re-read of the answer), **pure reasoning** (a closed-form puzzle), **code** (a real bug,
verified objectively by `pytest` rather than by the model's say-so), and a **multi-step task**.

### What the campaign found

**Reasoning capacity is not the differentiator.** Every remaining model solved the reasoning
task. Differentiation came entirely from **tool-calling reliability and factual honesty under
pressure**. A model that codes and reasons as well as any other can still fabricate an entire
answer on an open-ended research task.

**Size did not buy quality on this hardware.** In the final ranking, the smallest model tested
(`qwen3.5:4b`, 4B) produced the most reliable output, while the two largest (26B and 30B)
gained no net advantage — one failed outright. Separately, **5 of 8 Heavy/Very-heavy models
produced zero output in 8 minutes** on a simple tool-free question: not a quality problem, a
pure latency problem that makes them unusable interactively regardless of competence.

**Fact-checking changed the conclusions in both directions.** Two claims initially judged
fabricated turned out to be **correct** on verification, and the assessment was corrected.
Conversely, models that looked fine on a read-through had real errors (a casualty figure of 15
instead of 21; an EU AI Act provision described as active when it is deferred to 2027/2028).
Reading an answer is not evaluating it.

**Uncensoring method matters more than uncensoring.** Models uncensored by classic abliteration
(`huihui_ai/*`) fabricated repeatedly under pressure. Models uncensored via the **Heretic**
method (measured KL divergence) included two of the project's best performers. The plausible
explanation — untested — is that abliteration optimises for maximal compliance at the cost of
adherence to system-prompt constraints.

**A methodological limit worth recording:** heavy models (17+ GB) could not be benchmarked as
background tasks — the harness killed them 2–5 minutes in, during load/inference. Three
different fixes aimed at output-inactivity timeouts all failed, while a bare `sleep 300` was
also killed and a pure output-producing bash loop survived 10 minutes. The common variable is
a large `llama-server` child process (14–19 GB RSS), i.e. a **resource** limit, not an
inactivity timeout. Heavy models must be benchmarked in the foreground, one at a time.

---

## 6. The open problem — end-to-end multi-bug fixing

**Status: NOT SOLVED.** This is the project's most significant negative result, and it is
documented as an open problem rather than a conclusion.

### The fixture

A ~200-line menu-driven text game reconstructed from a real user incident, preserved as
`benchmarks/game_py_bugfix_original.py` with a verified reference solution alongside it. It
contains four known bugs plus a fifth **that was only discovered by actually playing the
game** — never by linting, and never by the two most careful models.

### The result

Five full attempts, with explicit scaffolding (activate the project → run Pyright diagnostics
→ fix → actually execute → don't declare done until both are clean):

| Model | Outcome |
|---|---|
| `gpt-oss:20b` | Used both diagnostic tools correctly, then produced a file **bit-for-bit identical to the buggy original** — and declared the bug fixed. False, confirmed by `diff` and execution |
| `Agen/gemma-4-26B…heretic` | **Corrupted the file**: 8 full-rewrite attempts over ~25 minutes, each truncated mid-generation, final file cut at line 50 with 155 lines lost — `write_file` reporting success every time |
| `qwen3.5:4b` | The only model to run real verification unprompted. On the full task it *deleted* a needed assignment while fixing something else, making things worse. After the syntax-check fix, it caught its own damage 5 times and kept iterating instead of declaring false success — a real, measurable improvement — but hit the 25-round safety limit still mid-progress, file still broken |

**Only a fix applied by hand produced a genuinely working file**, verified by playthroughs
covering every menu option.

### Reading of the result

The limiting factors appear to be (a) an insufficient tool-round/context budget for a
multi-bug task attempted in one shot, (b) a tendency to lose track of some bugs while fixing
others, and (c) at least one case of frankly false self-assessment.

Note the honest asymmetry: **the v2.9.20 fix worked exactly as designed on its narrow goal**
(preventing silent corruption — confirmed, measurable), while **the underlying task remained
unsolved.** Those are separate claims and the project keeps them separate.

Untried leads, in priority order: decompose into one bug at a time with validation between
each; raise `MAX_TOOL_ROUNDS` for this task class (one run was cut off mid-progress); retest
`qwen3-coder:30b` with the current tooling; use cross-model review (`/review-by`, since
implemented) as an adversarial second opinion; and establish whether this fixture — a state
machine with many shared dict keys — is structurally harder than a representative real task.

---

## 7. Feature design notes

**Local RAG (`search_semantic`).** bge-m3 embeddings in a stdlib SQLite index with incremental
re-indexing. Deliberately **no ChromaDB, no FAISS** — zero added dependencies, at the cost of
a brute-force cosine scan that is entirely adequate at single-project scale.

**Architect/editor (`/architect`).** Model A plans with read-only tools, model B executes with
all tools, **strictly sequentially loaded** so two models are never resident at once — a hard
24 GB constraint that shaped the design. Live testing surfaced a failure the design hadn't
anticipated: a small architect model burned all 25 rounds retrying write tools it wasn't
allowed to have. Hence `MAX_READONLY_REFUSALS` — after N refusals, push it to write the plan
as prose.

**Context compaction.** Two stages: lossless cleanup of old bulky tool results first (free, no
model call), then a structured summary of older turns, with the system prompt and the last 3
turns kept verbatim and never cut mid-tool-call. Triggered on Ollama's **real**
`prompt_eval_count`, not an estimate. **Auto-compaction ships OFF by default** — the dominant
community complaint about this feature elsewhere is auto-compaction destroying working context
by surprise, so nothing compacts until you opt in.

**Git checkpoints (`/undo`).** A shadow git repository snapshots the project before each turn's
first write. It works in non-git projects and never touches your own history — replacing an
earlier all-or-nothing in-memory undo.

**Search failover.** When SearXNG returns nothing usable, `search_web` fails over invisibly to
a `duckduckgo` MCP server. The model never chooses — same principle as the news routing:
one tool, hidden routing.

**Skills.** Reusable `SKILL.md` workflows with three-level progressive disclosure (name +
description always in the prompt; full instructions loaded on demand; referenced files read as
needed). The format is the open standard, so skills are portable to and from Claude Code,
Cursor and Codex.

---

## 8. Known limitations

- **Structure fabrication around a thin result — not solved, probably not solvable by prompt rules alone.** An active 2026 research area; confabulation is a structural property of probabilistic generation, not a deliberate lie. The real but unimplemented lead is a second verification pass comparing the final answer literally against raw tool output, rather than relying on the model to self-censor.
- **End-to-end multi-bug fixing — not solved** (§6).
- **Semantic citation verification is out of scope.** `_grounding_check` verifies that cited tokens *appear* in a tool result. Whether a claim faithfully reflects its source is not checked; `/review-by` is the partial mitigation.
- **MCP `taskSupport` capability negotiation is not implemented.** Tools requiring it fail cleanly rather than crashing.
- **macOS-centric.** `termios`, `ollama stop`, and several paths assume Unix/macOS.
- **Ollama-only — by design, permanently.** This is the one entry here that is not a gap. The
  project exists so that everything stays on your machine: no API keys, no data leaving the
  computer. A remote endpoint would break that guarantee rather than extend the tool.
- **No tree-sitter repo-map**, which remains Aider's clearest advantage for code editing.
- **No packaging yet** — `launch.sh` and a venv rather than `pip install`.

The last four are the active roadmap.

---

## 9. How this project verifies things

Three working rules, all of which were adopted after being violated:

1. **Never claim something works from reading the code.** Every feature ships with a deterministic test. The suite runs offline — no Ollama, no network, no writes to real config — using monkeypatched `ollama.chat` and temp directories, each test in its own process because several deliberately mutate module globals.
2. **Prefer simulated models to lucky reproductions.** The empty-response and failover fixes were validated with fake models scripted to fail a specific number of times, which is reproducible; waiting for a real model to misbehave is not.
3. **Distinguish "the fix worked" from "the problem is solved."** They are logged as separate claims throughout this document, because conflating them is how a project convinces itself it is finished.

The corollary is that this document reports negative results at the same volume as positive
ones. A local-agent project that only documented its wins would be describing a different
piece of software than the one in this repository.
