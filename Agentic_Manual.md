# Agentic_1A — User manual
> Local terminal AI agent · v3.0

> **Interface language.** The agent's interface (banner, `/help`, messages, `/model` table)
> is **English by default**. Use `/lang fr` to switch to French mid-session — the interface
> is fully bilingual EN/FR. This manual, and all other documentation, is English-only.

> **New to the project?** Read [`README.md`](./README.md) for the quick front page,
> [`Agentic_1A.md`](./Agentic_1A.md) for the detailed presentation,
> [`capabilities.md`](./capabilities.md) for the exhaustive capability list, and
> [`DESIGN.md`](./DESIGN.md) for the engineering history and the reasoning behind the
> reliability work. A condensed version history is in the [appendix](#appendix--version-history)
> at the end of this manual.

---

## Table of contents

- [Quick start](#quick-start)
- [The startup interface](#the-startup-interface)
- [Slash commands](#slash-commands)
- [Headless mode](#headless-mode)
- [What the agent can do](#what-the-agent-can-do)
- [Live settings (`/parameters`)](#live-settings-parameters)
- [Context management](#context-management)
- [Privacy & logs](#privacy--logs)
- [Skills](#skills--reusable-workflows)
- [Tool reference](#tool-reference)
- [Safety — checkpoints & undo](#safety--checkpoints--undo)
- [Code context — `/add` `/files` `/drop`](#code-context--add-files-drop)
- [Planning — `/plan`](#planning--plan)
- [A typical coding workflow](#a-typical-coding-workflow)
- [Switching models](#switching-models)
- [iMessage bridge](#imessage-bridge--control-from-an-iphone)
- [Troubleshooting](#troubleshooting)
- [Advanced tips](#advanced-tips)
- [Appendix — version history](#appendix--version-history)

---

## Quick start

### Requirements

1. **Ollama** running, with at least one **tool-capable** model installed.
2. **Python 3.12+** (a virtualenv is created for you by `launch.sh`).
3. Optional: **Docker** for SearXNG (private web search) and for the sandbox.

```bash
# A tool-capable model, plus the embedding model used by local RAG:
ollama pull qwen3:8b
ollama pull bge-m3
```

### Launching the agent

**From inside a project folder (the main use):**
```bash
cd ~/projects/my-project
bash /path/to/Agentic_1A/launch.sh
```

**Passing the folder as an argument:**
```bash
bash /path/to/Agentic_1A/launch.sh ~/projects/my-project
```

**Starting directly in safe mode:**
```bash
bash /path/to/Agentic_1A/launch.sh ~/projects/my-project --safe
# or, mid-session: /safe
```

**Without a specific project (current folder):**
```bash
cd /path/to/Agentic_1A
bash launch.sh
# or directly:
.venv/bin/python agent.py
```

`launch.sh` creates the Python environment if it is missing and installs the dependencies.

**Launch flags:** `--safe` (approve risky tool calls), `--sandbox` (Docker isolation),
`--private` (ephemeral, unlogged session; alias `--incognito`).

### Checking prerequisites

```bash
ollama list          # models installed
ollama serve         # start Ollama if it isn't running
curl "http://localhost:8080/search?q=test&format=json"   # is SearXNG up?
```

---

## The startup interface

```
────────────────────────────   Agentic_1A   ────────────────────────────
  Project : /Users/you/projects/my-project      ← the project root
  Model   : gemma4:12b-mlx
  Tools   : search_web, fetch_url, read_file, write_file, edit_file,
            create_directory, list_directory, run_command, get_datetime
  Help    : type /help
────────────────────────────────────────────────────────────────────────

You →
```

Type your message after `You →` and press Enter.

---

## Slash commands

> 💡 **Autocomplete.** Type **`/`** and a dropdown lists **every** command with its
> description; each extra character **filters** the list (e.g. `/c` → `/clear`, `/context`,
> `/compact`; `/co` → `/context`, `/compact`). Navigate with ↑/↓, accept with Tab or Enter.
> Descriptions follow the interface language (`/lang`). Requires `prompt_toolkit`; falls back
> silently to plain input if it is absent.

> ⏹ **Stopping the model.** Press **Esc** (or **Ctrl+C**) while the model is working to
> **stop it and return to the prompt** without leaving the session. It works during streaming
> (on by default); the stream to Ollama is genuinely cut. The partial conversation stays in
> context — type a new request, or `/clear` to start over. Esc detection only activates in an
> interactive terminal — it has no effect in headless mode.

> 🚪 **Quitting.** At the prompt, **Ctrl+C cancels the current line and does NOT quit**
> (consistent with "Ctrl+C = stop" during generation, and it avoids accidental exits). To
> quit, use **`/exit`** or **Ctrl+D**.

### Session

| Command | Description |
|---|---|
| `/help` | Show the list of commands |
| `/exit` | Quit the agent (saves the input history) |
| `/clear` | Clear the conversation history (the model starts fresh) |
| `/history` | Show the last messages of the conversation |
| `/resume` | List saved sessions; `/resume last` or `/resume <n>` reloads one |
| `/private` | Show whether this session is being logged (`--private` = no) |
| `/lang` | Show/change the interface language (interactive `en`/`fr` choice) |
| `/lang <en\|fr>` | Change the language directly, skipping the interactive choice |
| `/pwd` | Show the current project root |

### Context

| Command | Description |
|---|---|
| `/context` | Context usage: real tokens used vs the window cap, fill %, auto-compaction state |
| `/compact` | Compact the conversation now: losslessly clean old tool results, then summarise old turns while keeping the system prompt and the most recent turns verbatim |
| `/add <files>` | Inject one or more files into the model's context |
| `/files` | List the injected files |
| `/drop <file>` | Remove a file from context tracking |
| `/todo` | Show the task checklist the model maintains itself (`todo_write`/`todo_read`) |
| `/memory` | Show persistent memory (`memory_write`/`memory_read`) — survives restarts |
| `/forget` | Clear persistent memory (RAM + `.agentic/memory.md`) |

### Models

| Command | Description |
|---|---|
| `/model` | List installed Ollama models (number, size, params) and pick one |
| `/model <name>` | Switch model on the fly without restarting (skipping the list) |
| `/default-model` | Pick a model and save it as the default for all future sessions |
| `/failover-model [name\|off]` | Set the backup model used after retries are exhausted on an Ollama plumbing bug (disabled by default) |
| `/architect <task>` | Dual-model mode: model A plans (read-only tools), model B executes the plan (all tools) — strictly sequential loading |
| `/architect-models` | Configure the architect/editor pair (persisted) |
| `/review-by <model>` | A second model critiques the session's `/diff`, then your main model responds and can fix |
| `/vision-model [name\|auto]` | Set the multimodal model used by `analyze_image` (auto-detection by default) |

### Tools, skills & safety

| Command | Description |
|---|---|
| `/tools` | List every available tool with its description |
| `/skills` | List available skills (reusable workflows) with their descriptions |
| `/skill <name>` | Load a skill into context for your next request |
| `/mcp` | List connected MCP servers and their discovered tools |
| `/plan <task>` | Ask the model to plan a task **without** executing it |
| `/safe` | Toggle safe mode (`[y/N]` approval before every risky tool) |
| `/sandbox` | Toggle the Docker sandbox for `run_command`/`run_tests`/`python_repl` |
| `/parameters` (or `/params`) | Open the full-screen interactive settings menu — persists automatically |
| `/ps` | List background processes started this session (`run_background`) |
| `/kill <id>` | Stop a background process directly, without going through the model |

### Changes & audit

| Command | Description |
|---|---|
| `/diff` | Show this session's file changes |
| `/undo` | List git checkpoints; `/undo last` or `/undo <n>` restores the project to one |
| `/audit` | Show the last 20 entries of the audit log |

### Examples

```
You → /model
You → /model qwen3.5:4b
You → /architect fix every bug in game.py
You → /review-by gpt-oss:20b
You → /resume last
You → /undo last
You → /clear
You → /exit
```

---

## Headless mode

```bash
# A single prompt — exit code 0 on success, 1 otherwise (ideal for cron/scripts)
.venv/bin/python agent.py --run "summarise the README and write a CHANGELOG" ~/my/project

# A markdown recipe (## Constraints and ## Steps sections, or a plain list)
.venv/bin/python agent.py --recipe tasks.md ~/my/project
```

Only the final answer(s) go to stdout; progress goes to stderr.

---

## What the agent can do

The agent has **34 tools** it uses **automatically**. You never need to name a tool — the
model decides on its own. For the exhaustive list, see [`capabilities.md`](./capabilities.md).

### Highlighted tools

**`append_file(path, content)`** — write a long file in reliable chunks. The system prompt
guides the model: beyond ~80 lines, write the first chunk with `write_file` and continue with
`append_file` (each small call avoids Ollama's JSON-truncation bug on large arguments).
```
You → create a 300-line utils.py module with these functions: ...
  → the model writes the file in ≤80-line blocks (write_file, then append_file ×N)
```

**`search_semantic(query)`** — conceptual search across the project (local RAG). Embeddings
via `bge-m3`, SQLite index in `.agentic/`, re-indexed automatically when files change.
Complements `search_in_files` (exact) and `find_references` (symbols).
```
You → where is the retry logic for plumbing bugs handled?
  → search_semantic returns the closest chunks by meaning, with file:line
```

**`analyze_image(path, question)`** — understand an image.
```
You → take a screenshot and tell me why the button is misaligned
  → run_command("screencapture /tmp/s.png") then analyze_image("/tmp/s.png", "...")
```
Configure the model with `/vision-model` (otherwise an installed multimodal model is
auto-detected). Loading is sequential: the main model is unloaded for the duration of the
vision call, then reloaded.

**`python_repl(code)`** — persistent Python interpreter (state survives between calls).
```
You → load data.csv, show the columns then the mean of the price column
  → python_repl("import pandas as pd; df = pd.read_csv('data.csv'); df.columns")
  → python_repl("df['price'].mean()")   # df is still there
```
Same safety as `run_command`: dangerous-command filter, Docker sandbox under `/sandbox`,
approval under `/safe`.

### 🔁 Self-correction

If the model modifies a file and ends its reply **without** calling `lint_file` or
`run_tests` afterwards, the agent automatically re-prompts it (up to twice per turn) with a
message pushing it to verify. You will see `🔁 Auto-check: ...` when this fires — that is
normal, not an error.

Since v2.9.19 the reminder no longer presents `lint_file` as sufficient proof: it pushes the
model to actually run the script (`run_command`) for any non-trivial logic, and `run_command`
now counts as real verification alongside `lint_file`/`run_tests`.

### ✅ Task checklist (`todo_write` / `todo_read`)

For any task with more than 3 steps, the model is instructed to create a markdown checklist
(`todo_write`) before starting, then keep it updated (`- [x]` / `- [ ]`) rather than
re-deciding the plan every turn. It is plain in-memory text for the session — no imposed
format. `/todo` shows the current checklist. Empty at startup and after `/clear`.

### 🖥️ Background processes

`run_command` has a 30s timeout — useless for starting a dev server or a watcher that never
terminates. `run_background` starts the command without blocking and returns an id; the model
polls its output with `check_process(id)` and stops it with `kill_process(id)`. Limit: 5
simultaneous processes per session.

```
You → start npm run dev in the background, check it responds on port 3000, then stop it
```

**Safety/hygiene:**
- Every command goes through the same safety filter as `run_command` (blocks `rm -rf`, fork bombs, etc.).
- Output (stdout+stderr) is redirected to `.agentic/bg_logs/bg_<id>.log`.
- **Every process still alive at the end of the session is stopped automatically** (`/exit`, Ctrl+C, or crash) — no orphan server left running after you close the agent.
- `/ps` and `/kill <id>` give you direct control, without depending on the model.

### 🧠 Persistent memory (`memory_write` / `memory_read`)

Difference from `/todo`: the task checklist is **lost** at the end of the session (or on
`/clear`) — that is intended, it only concerns the current task. Memory is designed to
**survive**: written to `.agentic/memory.md` and reloaded automatically into the system prompt
every time the agent starts.

**When it is written (important):**
- **Only when the model calls the `memory_write` tool** — in practice, when **you ask it to
  remember something** ("remember that…", "keep this convention in mind"), or when it judges
  on its own that a durable fact is worth keeping. Nothing else writes it.
- **No automatic saving:** nothing is written on exit, nor each turn, nor when the agent edits
  files. The current conversation never goes there by itself.
- **Writing = full replacement:** every `memory_write` **overwrites** the previous content
  entirely (it is not an append). To modify or remove an item, ask the model to update the
  memory — it rewrites the whole text without that item.
- In a **`--private`** session, `memory_write` is a **no-op** (nothing is written to disk).

```
You → Remember that I prefer commit messages in English, under 50 characters
```
Then, in a **brand-new session** (agent restarted):
```
You → How do I want my commits again?
→ the agent answers correctly without you having to repeat it
```

**Caveats:**
- The model decides what to put there — if it records something false or outdated, it will persist until manually corrected. `.agentic/memory.md` is a plain text file: you can edit or delete it yourself at any time.
- `/forget` clears everything (RAM + disk file) in one command.
- No hard size limit, just a warning beyond ~3000 characters (the content is re-injected into **every** model call — better to stay concise).
- **Per-project scope:** `.agentic/memory.md` lives in the current project folder, so memory is not shared between different projects.

---

## Live settings (`/parameters`)

A full-screen menu (in the style of `htop`/`raspi-config`) for adjusting live everything that
used to be hard-coded. Navigate with **↑/↓** between rows, **←/→** to adjust the value,
**`r`** to reset the selected one to its default, **`q`**/Enter to exit. A help line at the
bottom explains the currently selected parameter.

**30 parameters, 3 sections:**

- **Model Generation (7)** — Temperature, Top P, Top K, Repeat Penalty, Max Output Tokens,
  Seed, and **Stream Final Answer** (stream the final answer live; can be disabled if a model
  regresses on tool-calling while streaming).
- **Context & Safety Limits (15)** — context cap (**64K**), max tool rounds, max background
  processes, max self-check re-prompts, max fake-tool-call retries, max citation reminders,
  max anti-hypothetical-fabrication nudges, max unsupported-values nudges
  (`_grounding_check`), max claimed-without-action nudges, tolerated tool refusals during the
  architect phase (`MAX_READONLY_REFUSALS`), `search_semantic` result count, indexing chunk
  size, and **context compaction** (`AUTO_COMPACT` on/off, `COMPACT_THRESHOLD_PCT` threshold,
  `COMPACT_KEEP_TURNS` recent turns kept).
- **Web Search (8)** — search language, number of results kept, `search_web_deep` settings
  (pages actually read, character budget per page, timeout before giving up, thin-content
  threshold), the never-converging deep-search circuit breaker (`MAX_DEEP_SEARCHES`), and the
  RSS fallback toggle.

```
You → /parameters
```

✅ Changes are saved automatically (`~/.agentic_1a_params.json`) and reloaded on every launch
— no need to re-tune everything each session.

---

## Context management

When a conversation gets very long it eventually fills the model's context window (**64K
tokens** by default, tunable). Three tools:

- **`/context`** — see where you stand: tokens actually used (Ollama's real
  `prompt_eval_count`, not an estimate) vs the cap, and the percentage.
- **`/compact`** — compact now, on demand. Two stages, an approach drawn from research
  (LangChain, Zylos, Claude Code, Factory.ai…):
  1. **lossless cleanup**: truncate old bulky tool results (free, no model call);
  2. if needed, a **structured summary** (`## Goal / ## Files changed / ## Key decisions /
     ## Open problems / ## Next steps`) of the older turns — the system prompt and the **last
     3 turns** are kept verbatim, never cut in the middle of a tool call.
- **Auto-compaction** (`/parameters` → *Auto-Compact Context*) — **OFF by default, on
  purpose.** The community's main complaint is auto-compaction that destroys working context
  by surprise, so nothing compacts until you enable it. Once enabled, it triggers when the
  context passes `COMPACT_THRESHOLD_PCT` (70% by default — early, because a model near its cap
  summarises less well).

> 💡 Important facts should never depend on the summary (which is lossy by nature): ask the
> agent to record durable decisions with `memory_write` (persistent), and it can find code by
> meaning again with `search_semantic`.

---

## Privacy & logs

**What is written to disk in a normal session** (`--private` turns all of it off, see below):

| What | Where | Content |
|---|---|---|
| **Full conversation** | `<project>/.agentic/sessions/<timestamp>.json` | Every message (you + model + tools) — powers `/resume` |
| **Typed lines** | `~/.agentic_1a_history` | Everything you type at the prompt (messages + commands), **across all projects** |
| **Audit log** | `<project>/.agentic/audit_YYYYMMDD.log` | Every tool call: name + truncated arguments (≈250 chars: queries, paths, start of written content) |
| **Snapshots** | `<project>/.agentic/snapshots/*.bak` | A copy of a file before editing (file content) |
| **Git checkpoints** | `<project>/.agentic/checkpoints.git` | Project state before each write (file content) |
| **Persistent memory** | `<project>/.agentic/memory.md` | Facts the model explicitly recorded (`memory_write`) |
| **Background logs** | `<project>/.agentic/bg_logs/*.log` | Output of processes started with `run_background` |

> Unrelated to the conversation: `semantic_index.db` (code embeddings, for `search_semantic`)
> and `model_categories.json` (a model-metadata cache).

**Clearing existing logs** (nothing is deleted automatically):

```bash
# One project's conversation + audit + snapshots/checkpoints:
rm -rf ~/path/to/project/.agentic/sessions
rm -f  ~/path/to/project/.agentic/audit_*.log
rm -rf ~/path/to/project/.agentic/snapshots ~/path/to/project/.agentic/checkpoints.git
rm -f  ~/path/to/project/.agentic/memory.md          # if you also want to forget the memory

# The global input history (everything you typed, all projects):
rm -f  ~/.agentic_1a_history
```

In-session, **`/forget`** clears persistent memory and **`/undo`** reverts file writes. (Note:
`/clear` only empties the **in-memory** history; it does not delete the session file on disk.)

**Private session — nothing is logged, everything disappears on exit:**

```bash
bash launch.sh ~/my/project --private
# (alias: --incognito)
```

In `--private` mode **no trace of the conversation is written**: no session file, no input
history (`~/.agentic_1a_history` — in-memory only), no audit log, no disk snapshots, no git
checkpoints, no memory. A 🔒 banner confirms it at startup, and **`/private`** shows the state
at any time. `/undo` still works (RAM snapshots) for the duration of the session.

⚠️ **What private mode does NOT hide** (in the interest of honesty): the **real file changes**
the agent makes in your project are genuine changes on disk (use `/undo` before quitting to
revert them if needed); **settings** (`/parameters`, models) are still saved (they are not
conversation); and **web searches** still hit the network (SearXNG/DuckDuckGo). Private mode
is about **local on-disk logs**, not the network.

---

## Skills — reusable workflows

A **skill** is a reusable set of instructions for a type of task (writing a commit message,
doing a security review, generating a report in your format…). It is simply a folder with a
**`SKILL.md`** file — **the same open format as Claude Code / Cursor / Codex**, so skills are
portable.

**How it works (progressive disclosure, 3 levels):**
- At startup the agent reads only each skill's **name + description** (near-zero cost) and lists them in its system prompt.
- When a task matches, the **model loads** the full instructions itself (the `load_skill` tool), **or** you load them by hand with **`/skill <name>`**.
- The instructions can point to other files in the skill's folder; the agent reads them on demand.

```
You → /skills                 # list available skills + their descriptions
You → /skill commit-message   # load a skill into context for your next request
```

**Where to put your skills** (most specific wins on a name clash):

| Location | Scope |
|---|---|
| `<Agentic_1A repo>/skills/` | **14 bundled skills** (see below) |
| `~/.agentic_1a_skills/` | **Your global skills** (all projects) — created at startup |
| `<project>/.agentic/skills/` | Project-specific skills |

**Bundled skills (14)** — type `/skills` to see them with their descriptions:

| Skill | What it does |
|---|---|
| `test-and-fix` | Runs the tests, diagnoses failures, fixes, re-runs until green |
| `debug-error` | Debugs an error/traceback: reproduce → locate → fix → verify |
| `write-tests-for` | Writes real unit tests (happy path + edge cases + errors) and makes them pass |
| `security-review` | Audits code/diff for **real** security flaws, with a fix |
| `optimize-performance` | Measures first (profiling), applies the highest-impact fix, proves the gain |
| `dependency-audit` | Finds vulnerable/outdated dependencies (`pip-audit`, `npm audit`…), proposes updates |
| `explain-codebase` | Explores and explains the architecture of an unfamiliar project |
| `dockerize-project` | Writes a correct Dockerfile + `.dockerignore`, builds and verifies it runs |
| `changelog-from-git` | Generates a CHANGELOG / release notes from the real git history |
| `web-research-report` | Sourced web research → Markdown report with citations |
| `new-python-project` | Scaffolds a modern Python project (venv, pyproject, git, first green test) |
| `commit-message` | Writes a clean commit message from the real diff |
| `skill-creator` | Helps you **write a new skill** (adapted from `anthropics/skills`, Apache-2.0) |
| `mcp-builder` | Helps you **build an MCP server** wired into the agent (same, Apache-2.0) |

> The first twelve are original to this project (MIT); `skill-creator`/`mcp-builder` are
> adapted from Anthropic's official repository. See [`skills/LICENSES.md`](./skills/LICENSES.md).
> You can add, edit or delete them freely — they are just folders with a `SKILL.md`.

**Creating a skill** — a folder plus a `SKILL.md`:
```markdown
---
name: security-review
description: Audit the diff for real security issues. Use when the user asks for a security review.
---

# Security review

## Steps
1. Read the diff with git_diff.
2. Check for: injection, hardcoded secrets, missing authz, unsafe deserialization…
3. Report only real issues (ignore false positives), each with file:line and a fix.
```
- `name`: lowercase/digits/hyphens, ≤ 64 characters.
- `description`: **the most important field** — it is what the model uses to decide whether to load the skill. Be precise about *when* to use it.
- The body can point to other files in the folder (`reference.md`, `scripts/…`) — the agent reads them with `read_file` and runs them with `run_command`.

> Skills vs MCP: a **skill** says *how* to approach a task (workflow, judgement); an **MCP
> server** gives *access* to tools/data. They are complementary.

---

## Tool reference

### 🔍 Web search (`search_web` / `search_web_deep`)

Uses your local SearXNG instance. The tool detects news-type queries itself (keywords like
"news", "today", "breaking", "latest") and automatically switches to the SearXNG "news"
category (real dated articles) instead of "general" — invisible to the model, one tool to
remember. Automatic fallback if the chosen category returns nothing usable, including an
invisible failover to the `duckduckgo` MCP server when SearXNG returns nothing at all.

**Two tools, two uses:**
- **`search_web`** — fast, returns snippets (~300 characters). Good for an overview or for deciding what to dig into.
- **`search_web_deep`** — slower, but **actually reads** the top 3 results in parallel (not just their snippets). Use it whenever the answer needs verifiable facts (precise news, figures, quotes). Each source comes back with its **publication date** (when found) and the **number of engines that independently confirm it** — e.g. `[confirmed by 2 sources: duckduckgo news, bing news]` — so you can judge freshness and reliability without guessing.

The model picks between them itself.

```
You → What's the weather in Paris today?
You → What's the latest news about Apple?
You → Search for tutorials on Python AI agents
```

### 🌐 Reading a web page (`fetch_url` / `fetch_url_rendered`)

`fetch_url` retrieves raw HTML without executing JavaScript — on a single-page app it sees
only the empty shell (or the unexecuted `<script>` source, which can look like text when it
isn't). `fetch_url_rendered` opens a real headless Chromium (Playwright), lets the JS run,
then reads the content actually displayed. Slower (~5–10s), so the model is instructed to try
`fetch_url` first and only escalate when the result looks empty/incomplete.

Requires `playwright` + `playwright install chromium` (optional dependency). Without it, the
tool simply reports itself unavailable rather than crashing.

```
You → Read this article: https://example.com/article
You → Summarise this page (it's a React app): https://example.com
```

### 📂 Reading files (`read_file` / `read_file_lines`)

```
You → Read src/config.yml and explain the configuration
You → Read lines 45 to 80 of src/main.py
You → Show me the function around line 120 of utils.py
```

### ✍️ Writing files (`write_file` / `append_file` / `edit_file`)

`write_file` creates or replaces a file; `append_file` adds to the end (and is how large files
are written in chunks); `edit_file` surgically replaces one precise block without rewriting
the rest.

Since v2.9.20, `write_file`/`edit_file` automatically check (via `ast.parse`) that the
resulting `.py` file is syntactically valid, and add a clear warning to the return message if
it isn't — without blocking the write. Since v2.9.18, a failed `edit_file` gives a real hint:
if it finds a close-enough passage (`difflib`) to your `old_text` elsewhere in the file, it
shows you that real passage with its line number.

```
You → Create a todo.md with a task list for this week
You → In main.py, replace get_user() with a version that validates the email
You → Fix the typo in README.md: "instalation" → "installation"
```

### 💻 Running commands (`run_command` / `run_tests` / `python_repl`)

```
You → What Python version is installed?
You → Run the tests and tell me what fails
You → Run pytest and fix the errors
```

### 🔎 Searching code (`search_in_files` / `find_files` / `find_references` / `search_semantic`)

- `search_in_files` — pattern across every project file (`grep -rn`).
- `find_files` — files by name or glob pattern.
- `find_references` — understands code instead of just matching text: separates real definitions/imports from actual uses, and ignores mentions in comments/docstrings (exact on `.py` via AST, best-effort elsewhere).
- `search_semantic` — conceptual search by meaning (local RAG).

```
You → Where is parse_user() defined?
You → Before renaming calculate_total, show me everything that uses it with find_references
You → Where is the retry logic handled?
```

### 🧪 Quick check (`lint_file`)

Runs a fast static check on a single file (much faster than `run_tests`): `ruff`/`flake8` for
Python (falling back to `py_compile` if neither is installed), `eslint` for JS/TS (if
installed as a local devDependency), `go vet` for Go.

### 🔀 Git (`git_status` / `git_diff` / `git_log` / `git_commit`)

```
You → What's the state of the git repo?
You → Show me what changed since the last commit
You → Commit the changes with the message "feat: add email validation"
  (the model will run git add automatically via run_command before committing)
```

### 📅 Other

`get_datetime` (current date and time — the model is required to call it before any
"today"/"current" search rather than guessing), `create_directory`, `list_directory`,
`analyze_image`, `python_repl`, `load_skill`, `todo_write`/`todo_read`,
`memory_write`/`memory_read`, `run_background`/`check_process`/`kill_process`/`list_processes`.

---

## Safety — checkpoints & undo

### `/diff` — see what changed

```
You → /diff
```
Shows a unified diff (like `git diff`) between the original files and their current state.

### `/undo` — restore a checkpoint

A **shadow git repository** (`<project>/.agentic/checkpoints.git`) snapshots the project
before the first write of each turn — it works even in projects that are not git repos, and it
never touches your own git history.

```
You → /undo          # list the available checkpoints
You → /undo last     # restore the most recent one
You → /undo 3        # restore checkpoint number 3
```

> Each checkpoint corresponds to the state **before a turn's first write**, so `/undo last`
> reverts the whole of the last turn's changes, not just the last individual edit.

### Safe mode and the sandbox

- **`/safe`** (or `--safe`) — `write_file`, `append_file`, `edit_file`, `run_command`, `run_tests`, `run_background`, `kill_process`, `git_commit` and `python_repl` ask for `[y/N]` approval before running. Enter alone = refusal (it fails on the cautious side). MCP tools are also treated as risky. Off by default.
- **`/sandbox`** (or `--sandbox`) — runs `run_command`/`run_tests`/`python_repl` inside an isolated Docker container instead of on the host. Orthogonal to safe mode: `/safe` gates *approval*, the sandbox contains the *blast radius*. If Docker is unavailable while the sandbox is on, the command is refused rather than silently run on the host.

---

## Code context — `/add` `/files` `/drop`

Inject files into the model's context before asking questions about them.

```bash
# Inject one or more files
You → /add src/main.py src/utils.py

# See what's in context
You → /files

# Stop tracking one
You → /drop utils.py
```

After `/add`, the model knows the content with line numbers. You can then:

```
You → Explain the main() function we just injected
You → Optimise the UserService class
You → Are there any bugs in this code?
```

---

## Planning — `/plan`

Ask the model to plan a task WITHOUT executing it. It explains its approach, the files
involved, and the risks.

```
You → /plan Refactor the auth module to use JWT
You → /plan Add unit tests to the UserService class
You → /plan Migrate from SQLite to PostgreSQL
```

Then, to execute it:
```
You → OK go ahead, execute that plan
```

> For a stronger version of this, `/architect <task>` runs the plan phase on one model
> (read-only tools) and the execution on another (all tools).

---

## A typical coding workflow

```bash
# 1. Launch from the project folder
cd ~/projects/my-project
bash /path/to/Agentic_1A/launch.sh

# 2. Explore the project
You → Show me the project structure
You → Find where the UserController class is defined

# 3. Plan before acting
You → /plan Add a POST /users endpoint with email validation

# 4. Inject the relevant files
You → /add src/routes/users.py src/models/user.py

# 5. Ask for the changes
You → Add the POST /users endpoint with email validation as planned

# 6. Check the changes
You → /diff
You → Run the tests: pytest

# 7. Commit if OK
You → Commit with "feat: add POST /users endpoint"

# 8. Revert if there's a problem
You → /undo last
```

---

## Switching models

### Via the interactive list (recommended)

```
You → /model
```

Shows a numbered table of every model from `ollama list`, with:

- **Size / Params** — from `ollama list`.
- **Usage** — Light / Medium / Heavy / Very heavy, computed from the RAM actually detected on the machine, not a fixed value. `⚡` = MoE model (name containing `-aXb`, e.g. `30b-a3b`) → runs faster than its raw size suggests.
- **Task** — what the model is best at (Code, Agentic, Research/RAG, Generalist…). It first uses a local knowledge base built into the agent; if a model is unknown, the agent runs a SearXNG search on its name and infers the category by keywords, then caches the result in `.agentic/model_categories.json` (searched once per model). ⚠️ This automatic categorisation is a keyword heuristic, not an AI judgement — reliable when the model is well documented online, but it can be wrong on an obscure or poorly indexed name.
- **Tools** ✓/✗ — tool-calling support.
- **Active** — the model currently loaded.

Type the number (e.g. `3`) or part of the name (e.g. `qwen3`) to switch, or leave it empty to
cancel.

A model marked **Tools ✗** is refused automatically (error message, no switch): the agent
needs tool calling to work, so those models (e.g. pure embedding models like `bge-m3`) are not
selectable.

### Directly by name

```
You → /model qwen3.5:4b
```

### Model recommendations

Any tool-capable Ollama model works. Scores below are out of 100 from the ranking campaign in
[`benchmarks/model_ranking/RESULTS.md`](./benchmarks/model_ranking/RESULTS.md) — four tasks
(reasoning, web search, agentic work, report writing) on a 24 GB Apple Silicon machine.

| Model | Size | Score | Notes |
|---|---|---|---|
| `gemma4:12b-mlx` | 7.7 GB | **95** | **Recommended default.** The only model of ten that actually fixed the broken program rather than claiming to |
| `gpt-oss:20b` | 13 GB | 75 | Best planner and best report prose; natively supported by Ollama; 0 timeouts, 0 swap |
| `hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M` | 5.6 GB | 71 | Strong reasoning and reports, but timed out on 3 of 4 tasks |
| `qwen3.5:4b` | 3.4 GB | 70 | The shipped fallback: perfect web-search score at the smallest size, zero swap |
| `jikepjikep_16HEX/gemma-4-12b-nightshift-heretic…` | 7.4 GB | 64 | Uncensored (Heretic); perfect search score |
| `Agen/gemma-4-26B-A4B-it-uncensored-heretic` | 18 GB | 59 | Uncensored + vision, but ~8.7 GB of swap on a 24 GB machine |

> ⚠️ **On 24 GB, models above ~13 GB are a poor trade.** `gemma4:26b-mlx` pushed **13.2 GB into
> swap** and still scored below a 7.7 GB model. A 27B+ model at q8 may not load at all — Ollama
> refused one outright with *"requires 26.6 GiB but only 17.3 GiB are available"*.

> ⚠️ Models that do not support tool calling are not compatible, and `/model` blocks selecting
> them. Models "uncensored" via classic abliteration (`huihui_ai/*`) showed repeated factual
> fabrication under pressure — prefer the **Heretic** method if you need an uncensored model.

---

## iMessage bridge — control from an iPhone

Send commands to the agent from your iPhone via iMessage. **macOS only**, and entirely
optional.

### Setup (first time only)
```bash
cd /path/to/Agentic_1A && .venv/bin/python imessage_bridge.py --setup
```
It will ask for your own phone number or iCloud email — the one you will message from.

**Prerequisites:** System Settings → Privacy → Full Disk Access → Terminal ✓, Messages.app
open on the Mac, Ollama running.

### Running the bridge
```bash
cd /path/to/Agentic_1A && .venv/bin/python imessage_bridge.py
```
The bridge stops when you close the terminal. There is no need to leave it running
permanently.

### Usage

1. Open **Messages** on the iPhone.
2. Send a message to **your own number** (the one configured at setup).
3. The message must start with `!`.

```
! what time is it
! list the project files
! search for the latest AI news
```

> Without the leading `!`, the bridge ignores the message.

**Behaviour:** the bridge replies in the same iMessage conversation; long messages are split
into fragments automatically; a `⏳` is sent immediately as an acknowledgement; the answer
arrives within a few seconds depending on complexity.

---

## Troubleshooting

### "Ollama is not running"
```bash
ollama serve
# then relaunch the agent in another terminal
```

### "Model not found"
```bash
ollama list                                  # what's available
ollama pull gemma4:12b-mlx                   # or any tool-capable model
```

### Search errors (`search_web`)
```bash
# Check SearXNG
curl "http://localhost:8080/search?q=test&format=json"
```
If you don't run SearXNG, `search_web` automatically fails over to the `duckduckgo` MCP server
when one is configured — see the MCP section of [`capabilities.md`](./capabilities.md).

### The agent doesn't answer / is very slow
- The model is thinking — the "Thinking…" spinner with the live RAM readout is normal.
- Press **Esc** to stop it and get back to the prompt.
- For faster answers, switch to a smaller model with `/model`.

### Python import error
```bash
cd /path/to/Agentic_1A
.venv/bin/pip install -r requirements.txt
```

### Rebuild the environment from scratch
```bash
cd /path/to/Agentic_1A
rm -rf .venv
bash launch.sh
```

---

## Advanced tips

### Multi-step requests
The agent chains several tools automatically:
```
You → Find the current Bitcoin price, compare it with a week ago from another
      source, and write a summary to bitcoin.md
```

### Carrying file context through a conversation
```
You → Read src/main.py
You → Optimise the parse_data() function you just read
You → Save the improved version to src/main_v2.py
```

### "System engineer" mode
```
You → Check whether git is installed, show me the version, and list the repos here
```

### Keeping a long session on track
The context window is **64K tokens** by default. Use `/context` to see how full it is,
`/compact` to compact on demand, and `/clear` only when you genuinely want to start over.
Durable facts belong in `memory_write`, not in the conversation history.

---

## Appendix — version history

> This is a condensed summary. The full engineering history, with the reasoning and the
> benchmark evidence behind each change, is in [`DESIGN.md`](./DESIGN.md).

**v3.0 (2026-08-05) — major release.** 7 fixes + 10 features.
- **5 new tools:** `append_file` (chunked writes, anti-truncation), `search_semantic` (local RAG via bge-m3), `analyze_image` (vision), `python_repl` (persistent interpreter), `load_skill`. **34 tools total.**
- **New commands:** `/architect`, `/architect-models`, `/review-by`, `/resume`, `/failover-model`, `/vision-model`, `/context`, `/compact`, `/skills`, `/skill`, `/private`.
- **`/undo` reworked** into a list of git checkpoints instead of all-or-nothing undo.
- **Streaming final answers**, automatic **session persistence**, invisible **DuckDuckGo search failover**, an **encoding fix** (no more `â€™`), a **closest-path hint** on file-not-found, and **deterministic honesty layers** (unsupported values, claimed-fixed-without-action).
- **Headless mode**: `--run "prompt"` and `--recipe file.md` (exit code = success).
- Context cap doubled to **64K** plus **context compaction** (auto off by default), **slash-command autocomplete**, **Esc-to-stop**, and **`--private`** ephemeral mode.
- **Skills**: reusable `SKILL.md` workflows with progressive disclosure, plus a 14-skill library.

**v2.9.x — the reliability series.** Safe mode (v2.9); real context negotiation with Ollama,
a thin-search circuit breaker and a no-guessing-the-date rule (v2.9.4); empty-response retries
for "thinking" models (v2.9.5); anti-fabrication prompt rules (v2.9.6–.7); `search_web_deep`
(v2.9.9); `/parameters` (v2.9.10); the web-search quality overhaul — `trafilatura`,
robots.txt, caching, honest User-Agent (v2.9.11); five reliability/ecosystem workstreams —
fake-tool-call detection, persisted settings, citation reminders, **MCP support**, **Docker
sandbox** (v2.9.14); MCP progress notifications, more anti-fabrication rules, `prompt_toolkit`
input, a persisted user-chosen default model (v2.9.15); **a path-confinement security fix**
plus three research-driven fixes (v2.9.16); the anti-hypothetical-tool-output nudge (v2.9.17);
the `edit_file` near-match hint (v2.9.18); "a clean lint is not proof" (v2.9.19); automatic
post-write syntax checking (v2.9.20).

**v2.2–v2.8 — the tool-belt years.** English-by-default bilingual interface (v2.2);
`lint_file` + the self-correction loop + the 25-round guard (v2.3); `todo_write`/`todo_read`
(v2.4); background processes (v2.5); `fetch_url_rendered` via Playwright (v2.6);
`memory_write`/`memory_read` persistent memory (v2.7); `find_references` with real AST
analysis (v2.8).
