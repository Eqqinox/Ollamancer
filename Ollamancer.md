# Ollamancer: what it is, in detail

> A fully-local, terminal-first AI agent for Ollama, built from scratch in Python.
> Version **v3.1** · developed on macOS (M4 Pro, 24 GB) · docs in English · bilingual EN/FR interface.
>
> This document is the detailed presentation. See `README.md` for the quick front page,
> `Agentic_Manual.md` for the full user manual, `capabilities.md` for the exhaustive
> capability list, and `DESIGN.md` for the design rationale and engineering history.

---

## 1. In one paragraph

Ollamancer is a terminal AI agent that runs **entirely on your machine** through
[Ollama](https://ollama.com): no cloud, no API keys, no data leaving your computer. You
point it at a project folder and talk to it; it reasons and acts using **35 native tools**
(files, git, web search, code execution, RAG, vision…), plus any [MCP](https://modelcontextprotocol.io)
servers you configure, plus the full macOS shell. It was written **from scratch** (no
LangChain/Smolagents) for total control and transparency, and its design obsesses over three
things most local agents ignore: **honesty (not fabricating), reliability on small local
models, and privacy.**

---

## 2. Design philosophy

- **Local and private first.** Everything runs offline via Ollama. A `--private` mode makes a
  session fully ephemeral (nothing written to disk).
- **From scratch, no framework.** ~8,300 lines of readable Python across 21 focused modules —
  12 in `agentic/` plus 9 tool modules in `agentic/tools/` — auditable end-to-end.
  The decision was validated repeatedly: many fixes required line-level control a framework
  would have hidden. *(Corrected 2026-08-15: this read "~6,700 lines across fourteen focused
  modules". The line count had drifted with the code; "fourteen" counted the 12 `agentic/`
  modules plus `agent.py` and `imessage_bridge.py`, a basis that excluded the tool modules the
  line count included. The counting basis is now stated so the pair can be checked.)*
- **Nudge, never gate.** The agent warns and re-prompts the model; no code path rewrites,
  filters or blocks what the model produced. Honesty checks are *nudges*, not censors. Stated
  precisely, because the shorthand flatters it: a nudge re-prompts, and it is the **second**
  answer you see. The first is superseded on screen with nothing announcing it went. It is kept
  in the conversation and in the session JSON (not under `--private`, which writes nothing), but
  no command surfaces it — `/details` records tool calls, not answers. So nothing is censored,
  and something can still be lost from view. That is the cost of the design, not a bug in it.
- **Reliability over cleverness.** Small, quantized local models are fragile; the agent is
  engineered around their real failure modes (documented in a long benchmark campaign).
- **Verify, don't trust.** Every feature ships with a deterministic test; the docs never claim
  something works from reading the code alone.

---

## 3. Architecture

**ReAct loop** (`run_agent`): the model thinks → calls tools → reads results → repeats until it
can answer without a tool. The whole conversation is kept in memory and re-sent each turn.

```
User → message
  ↓
Model reasons → calls tool(s) → gets results → reasons again … → final answer → User
```

- **Tool schemas** are auto-extracted from Python type hints + docstrings (Ollama SDK), no
  manual JSON schemas.
- **Streaming** final answers (buffered on tool rounds), with a live RAM **and context**
  readout (`12.3 GB RAM · ~8.4k/49.2k (17%)`, a tilde marking an estimate), plus an exact
  `· context 12.4k/49.2k (25%) · generated 391` line under each answer, while the
  model works.
- **Safety rails**: a max-rounds guard, retry+fallback for five confirmed Ollama tool-call
  plumbing bugs, and a one-time **model failover** to a backup model when those retries exhaust.

---

## 4. The tool belt (35 native tools)

- **Web:** `search_web`, `search_web_deep` (reads the top pages), `fetch_url`,
  `fetch_url_rendered` (headless browser). SearXNG with automatic **DuckDuckGo-MCP failover**.
- **Files:** `read_file`, `read_file_lines`, `write_file`, `append_file` (chunked writes),
  `edit_file` (surgical), `create_directory`, `list_directory`.
- **Code navigation:** `search_in_files` (grep), `find_files`, `find_references` (AST-precise for
  Python), `repo_map` (**ranked outline** of the whole project, PageRank over a name-usage
  graph), `search_semantic` (**local RAG** via the bge-m3 embedding model), `load_skill`.
- **Git:** `git_status`, `git_diff`, `git_log`, `git_commit`.
- **Verification / execution:** `lint_file`, `run_tests`, `run_command`, `python_repl`
  (persistent interpreter).
- **Vision:** `analyze_image` (one-shot call to an installed multimodal model).
- **Task/memory:** `todo_write`/`todo_read` (session), `memory_write`/`memory_read` (persistent).
- **Background processes:** `run_background`, `check_process`, `kill_process`, `list_processes`.
- **Utility:** `get_datetime`.

Plus **`run_command`** exposes the entire shell, and **MCP** adds any third-party tool.

---

## 5. Flagship features

- **Architect / editor dual-model** (`/architect`), model A plans with read-only tools, model B
  executes with full tools; **strictly sequential loading** so two models are never resident at
  once (a 24 GB constraint).
- **Local RAG** (`search_semantic`), conceptual code search over the project using bge-m3
  embeddings in a stdlib SQLite index; incremental re-index on change. No heavy deps.
- **Context compaction**: when the conversation grows, deterministic lossless cleanup then a
  **structured** summary of old turns (system prompt + recent turns kept verbatim), triggered on
  the real Ollama token count. Off by default; `/compact` on demand; `/context` shows usage.
- **Git checkpoints** (`/undo`), a shadow git repo snapshots the project before each turn's first
  write; `/undo last` / `/undo <n>` revert.
- **Session persistence** (`/resume`), reload a previous conversation.
- **Cross-model review** (`/review-by <model>`), an independent second model critiques the diff.
- **Skills**: reusable **`SKILL.md`** workflows (the open standard, portable with Claude
  Code/Cursor/Codex), with progressive disclosure and a bundled 15-skill library. One of them,
  `web-answer-format`, is auto-loaded code-side on web-shaped questions (news, "latest", "look
  it up"), the same reasoning as the forced search: a small model rarely calls `load_skill`
  itself, so the answer's shape can't depend on it choosing to.
- **Honesty layers**: `_grounding_check` (flags numbers/dates/URLs/names in the answer that
  appear in no tool result this turn) and a claim-vs-action nudge ("fixed"/"verified" with no
  real edit/verification), both deterministic. The "verified" half stands down on a turn built
  from search and read calls, where the word means checked against the sources.
- **Graceful exhaustion**: hitting the tool-round limit, or an optional `TURN_BUDGET_SECONDS`
  wall clock, no longer discards the turn. The loop stops calling tools and spends one final
  generation answering from the evidence already gathered, labelled incomplete, with the
  grounding check still applied as a warning. Off by default for the timer; a slow local model
  is not misbehaving.
- **Headless / batch**: `--run "prompt"` and `--recipe file.md` (exit code = success) for
  cron/scripts.
- **Privacy**: `--private` ephemeral session; safe mode (`--safe`) approves risky calls; Docker
  sandbox (`--sandbox`) isolates shell/REPL.
- **Terminal UX**: slash-command autocomplete (type `/`), streamed answers, live RAM and
  context usage,
  Esc-to-stop, bilingual interface.

---

## 6. Reliability & honesty engineering (the differentiator)

Ollamancer treats the failure modes of small local models as first-class problems:

- **Anti-fabrication:** deterministic grounding checks, a hypothetical-tool-output nudge, an
  anti-structural-fabrication rule set, and citation nudges.
- **Anti-false-success:** the claim-vs-action nudge, and `run_command` counting as *real*
  verification (a clean lint is not proof of correctness).
- **Ollama plumbing bugs:** retry+fallback for five confirmed upstream failure signatures (#16988,
  #16383/#16810, mid-JSON truncation, plain-text pseudo tool calls, and a num_ctx overflow that
  silently deletes the user's request), plus a configurable **model failover**.
- **A documented benchmark campaign** (`benchmarks/`, `DESIGN.md`) comparing 18 models
  on factual, reasoning, code, and multi-step tasks, with a repeat-action playthrough harness.
  Scored `pass^k`: the **minimum** across repeats, so a model counts only what it delivers
  every time. Adding a second repeat cost eight of ten models points, one of them 17.

---

## 7. Configuration & control

- **`/parameters`**: a full-screen curses menu, **34 live-tunable settings** (generation params,
  context cap, safety/nudge limits, search tuning, streaming, compaction), persisted to
  `~/.agentic_1a_params.json`.
- **Models**: `/model` (session), `/default-model` (persisted), `/failover-model`,
  `/architect-models`, `/vision-model`.
- **`/help`** lists every slash command (37 total).

---

## 8. Requirements

- **[Ollama](https://ollama.com)** with at least one tool-capable model (e.g. a small Qwen/Gemma
  build; the bge-m3 embedding model for RAG).
- **Python 3.12+** in a virtualenv (the `launch.sh` script sets it up).
- Core Python deps: `ollama`, `requests`, `rich`, `trafilatura` (clean web extraction),
  `feedparser` (news RSS). Optional extras, each of which the agent starts and runs without,
  reporting the feature unavailable rather than failing: `playwright` (JS pages, `[browser]`),
  `mcp` (MCP servers, `[mcp]`), `prompt_toolkit` (fixes paste-submits-early on macOS libedit
  builds, `[prompt]`), `tree-sitter-language-pack` (`repo_map` beyond Python, `[treesitter]`).
- Optional services: **SearXNG** (Docker) for private web search; **Docker** for the sandbox.

---

## 9. Repository map

```
agent.py                  # thin entry point; the agent lives in agentic/
launch.sh                 # venv setup + launcher (flags: --safe --sandbox --private)
skills/                   # bundled SKILL.md workflows (15)
benchmarks/               # reusable model-reliability fixtures + playthrough harness
imessage_bridge.py        # optional: drive the agent from iPhone via iMessage
requirements.txt
README.md                 # public front page
Ollamancer.md             # this file, detailed presentation
Agentic_Manual.md         # full user manual
capabilities.md           # exhaustive capability list
DESIGN.md                 # design rationale & engineering history
tests/                    # deterministic offline test suite (44 tests)
```

---

## 10. Status & positioning

A mature **personal tool** (v3.1), not a funded product. It won't out-star OpenCode, but it
occupies a genuinely uncommon niche the 2026 market analysis says the field is missing:
**fully-local + deterministic honesty controls + small-model reliability engineering +
skills-beyond-MCP + privacy mode + a rich terminal UX.**
