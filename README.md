# Ollamancer

**A fully-local, terminal-first AI agent for [Ollama](https://ollama.com), built from scratch, obsessed with honesty, small-model reliability, and privacy.**

[![tests](https://github.com/Eqqinox/Ollamancer/actions/workflows/tests.yml/badge.svg)](https://github.com/Eqqinox/Ollamancer/actions/workflows/tests.yml)

No cloud. No API keys. No data leaves your machine. Point it at a project folder and talk to it. It reasons and acts with 35 native tools, MCP servers, and your shell.

> Status: **v3.0** · developed on macOS (Apple Silicon, 24 GB) · Python 3.12+ · documentation in English, **bilingual EN/FR interface** · MIT.

<!-- TODO: demo recording.
     asciinema rec demo.cast --cols 100 --rows 30
     agg demo.cast demo.gif      # https://github.com/asciinema/agg
     Then replace this comment with:![Ollamancer demo](./docs/demo.gif)
     Suggested 45s script: launch → "where is the retry logic handled?" (RAG)
     → "fix the failing test and verify it" (edit + run_tests) → /diff → /undo last -->

```
┌─ demo placeholder ──────────────────────────────────────────────┐
│                                                                 │
│                       COMING SOON                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why another terminal agent?

The local-agent space is crowded (Aider, OpenCode, Goose…). Ollamancer is different where it counts: it takes seriously the three things the [2026 local-first market analysis](https://nimbalyst.com/blog/best-local-first-ai-coding-tools-2026/) says the field is *missing*:

-  **Deterministic honesty controls**: it flags numbers/dates/URLs/names in an answer that appear in *no* tool result this turn, and nudges when the model claims "fixed/verified" without a real edit or verification. Hallucination is treated as a first-class, *deterministic* problem, not left to the model.
-  **Small-model reliability engineering**: retries + fallback for four confirmed Ollama tool-call failure signatures, chunked writes to avoid mid-JSON truncation, a one-time **model failover**, and a documented benchmark campaign across 18 models, scored `pass^k` (the *minimum* across repeats, so a model counts only what it delivers every time).
-  **Privacy by design**: fully offline, plus a `--private` ephemeral mode that writes *nothing* to disk.

Plus local RAG, vision, dual-model planning, skills, and a genuinely nice terminal UX.

> The engineering behind those claims, including the negative results, is written up in
> [`DESIGN.md`](./DESIGN.md).

---

## Features

- **35 native tools** + [MCP](https://modelcontextprotocol.io) + full shell.
- **Web search**: private SearXNG with automatic **DuckDuckGo failover**, plus deep-read and a headless-browser fetch.
- **Repo map**: `repo_map` outlines every file's classes and functions, ranked by PageRank over a "who uses whose names" graph so the widely used modules survive the budget. Python needs no dependencies; other languages use tree-sitter via the `treesitter` extra.
- **Local RAG**: conceptual code search over your project with the `bge-m3` embedding model (`search_semantic`), zero extra dependencies.
- **Vision**: describe screenshots / read charts via an installed multimodal model.
- **Persistent Python REPL**: state survives across calls, for real data work.
- **Architect / editor dual-model**: one model plans (read-only), another executes (full tools), **loaded strictly one at a time** to fit small VRAM.
- **Cross-model review**: an independent second model critiques your diff.
- **Git checkpoints**: `/undo` reverts a whole turn (shadow repo, works in non-git projects too).
- **Context compaction**: summarizes old turns when the window fills (off by default; `/compact` on demand).
- **Session resume**, **streaming answers**, **live RAM readout**, **Esc-to-stop**.
- **Compact tool display**: one line per tool call with result size and elapsed time; `/details` prints the full, untruncated record of the last turn.
- **Skills**: reusable [`SKILL.md`](https://agentskills.io) workflows (the open standard, portable with Claude Code / Cursor / Codex) + a bundled **14-skill library**.
- **Headless / batch**: `--run "prompt"` and `--recipe file.md` (exit code = success) for cron/scripts.
- **Safe mode** (approve risky calls) and a **Docker sandbox** (isolate shell/REPL).
- **31 live-tunable settings** in a `/parameters` menu, persisted across sessions.

---

## Quick start

**Requirements:** [Ollama](https://ollama.com) running with at least one tool-capable model, **Python 3.12+** (a venv is created for you). Optional: SearXNG (Docker) for web search ([setup](./Agentic_Manual.md#setting-up-searxng-optional-for-web-search)), Docker for the sandbox.

```bash
# 1. Pull a tool-capable model (any small Qwen/Gemma build works), and the RAG embedder:
ollama pull gemma4:12b-mlx    # the default; any tool-capable model works. See RESULTS.md §10
ollama pull bge-m3            # embedding model, needed for local RAG

# 2. Install it (not on PyPI yet, so straight from the repo):
pip install git+https://github.com/Eqqinox/Ollamancer.git

# 3. Point it at a project:
ollamancer ~/path/to/your/project
```

Optional extras, all of which the agent runs happily without:

```bash
pip install "ollamancer[browser] @ git+https://github.com/Eqqinox/Ollamancer.git"
pip install "ollamancer[mcp]     @ git+https://github.com/Eqqinox/Ollamancer.git"
pip install "ollamancer[all]     @ git+https://github.com/Eqqinox/Ollamancer.git"
```

`browser` adds `fetch_url_rendered` and then needs `playwright install chromium`; `mcp`
adds third-party MCP servers; `prompt` fixes paste-submits-early on macOS libedit builds.

Prefer to work from a checkout? `launch.sh` creates the venv and installs dependencies
for you:

```bash
git clone https://github.com/Eqqinox/Ollamancer.git
bash Ollamancer/launch.sh ~/path/to/your/project
```

**Optional flags:** `--safe` (approve risky tool calls), `--sandbox` (Docker isolation), `--private` (ephemeral, unlogged session).

---

## Usage

Just talk to it:

```
You → fix the failing tests in this project and verify by running them
You → where is the retry logic handled?          # uses local RAG
You → do a security review of my changes
You → research the latest on <topic> and write a cited report
```

Type **`/`** to autocomplete commands, `/help` lists them all. A few highlights:

| Command | Does |
|---|---|
| `/model`, `/default-model` | Switch / persist the model |
| `/architect <task>` | Dual-model plan → execute |
| `/review-by <model>` | Second model reviews the diff |
| `/skills`, `/skill <name>` | List / load a skill |
| `/undo`, `/diff` | Revert a turn / see changes |
| `/context`, `/compact` | Context usage / compact now |
| `/details` | Full record of the last turn's tool calls |
| `/resume` | Reload a saved session |
| `/parameters` | Settings menu (31 tunables) |
| `/private` | Is this session logged? |

Press **Esc** (or Ctrl+C) while it's working to stop the model and return to the prompt.

---

## Skills

Skills are reusable `SKILL.md` workflows the agent loads on demand. 14 ship bundled, e.g.
`test-and-fix`, `debug-error`, `write-tests-for`, `security-review`, `optimize-performance`,
`dependency-audit`, `explain-codebase`, `dockerize-project`, `changelog-from-git`,
`web-research-report`, `new-python-project`, `commit-message`, plus `skill-creator` and
`mcp-builder` (adapted from Anthropic's Apache-2.0 [anthropics/skills](https://github.com/anthropics/skills)
,  see [`skills/LICENSES.md`](./skills/LICENSES.md)).

Add your own: drop a folder with a `SKILL.md` into `~/.agentic_1a_skills/` (global) or
`<project>/.agentic/skills/` (per-project). The format is the open standard, so skills are
portable to/from other agents.

---

## Privacy

Everything runs locally. In a normal session the agent keeps a session transcript, an input
history, and an audit log on disk, **`--private` disables all of it** (ephemeral, deleted on
exit). See the [Privacy & logs](./Agentic_Manual.md#privacy--logs) section of the manual for
exactly what's stored, where, and how to delete it.

Those files live in `~/.agentic_1a_*`, named before the project was renamed, and kept
that way so upgrades do not orphan an existing install.

---

## Tests

The agent ships with 34 deterministic tests that run **fully offline**, no Ollama, no
network, and no writes to your real config (the runner enforces that last one):

```bash
pytest                         # or: bash tests/run_all.sh
```

They run on every push against Python 3.12 and 3.14, on Linux, via GitHub Actions.

See [`tests/README.md`](./tests/README.md) for what each one covers.

---

## How it compares (honest)

- **Aider**: better at disciplined git-native multi-file editing. Both now have a ranked repo map; Aider's covers more languages out of the box, while `repo_map` here needs no dependencies for Python and an optional extra for the rest.
- **OpenCode**: far more popular, and provider-neutral across many cloud and local backends. Ollamancer declines that neutrality on purpose: Ollama-only means no API keys and nothing leaving your machine.
- **Ollamancer's niche**: the deterministic honesty layers, small-model reliability work, privacy mode, local RAG, and skills-beyond-MCP, in one transparent, from-scratch tool.

---

## Documentation

- [`Ollamancer.md`](./Ollamancer.md): detailed presentation.
- [`Agentic_Manual.md`](./Agentic_Manual.md): full user manual.
- [`capabilities.md`](./capabilities.md): exhaustive capability list.
- [`DESIGN.md`](./DESIGN.md): design rationale & engineering history (including what *didn't* work).
- [`benchmarks/README.md`](./benchmarks/README.md): the model-reliability fixtures and findings.
- [`benchmarks/model_ranking/RESULTS.md`](./benchmarks/model_ranking/RESULTS.md): 18 local models ranked on reasoning, search, agentic work and report writing, with the protocol and its limits in [`PLAN.md`](./benchmarks/model_ranking/PLAN.md). §10 is the current `pass^2` ranking; the earlier sections are single-run and are kept only to show how much a second run moved them.

All documentation is in English. The **agent's interface is bilingual EN/FR** (`/lang`), that's a feature, not an oversight.

---

## Project layout

```
pyproject.toml        # packaging; `ollamancer` console script -> agentic.cli:main
agent.py              # entry point + compatibility facade (44 lines)
agentic/              # the implementation
  config.py           #   persisted settings (the 31 /parameters values)
  state.py            #   per-session runtime state + reset()
  i18n.py             #   bilingual EN/FR strings and the system prompt
  ui.py               #   console, prompt, autocomplete, /parameters menu
  safety.py           #   blocklists, path confinement, safe mode, sandbox, audit
  checkpoints.py      #   the shadow-git repo behind /undo
  models.py           #   model discovery, context negotiation, /model picker
  mcp_client.py       #   MCP servers + the sync-to-async bridge
  skills.py           #   SKILL.md discovery, progressive disclosure
  tools/              #   the 35 tools, one module per domain
  loop.py             #   the ReAct loop, retries, honesty nudges, compaction
  commands.py         #   slash commands, architect/review, sessions
  cli.py              #   flags and the interactive/headless entry point
launch.sh             # venv setup + launcher
skills/               # bundled SKILL.md workflows (14)
benchmarks/           # model-reliability fixtures + playthrough harness
tests/                # deterministic offline test suite (34 tests)
imessage_bridge.py    # optional: drive it from iPhone via iMessage (macOS)
```

---

## Status & contributing

A mature **personal project**, open-sourced primarily as a transparent, local-first,
honesty-focused alternative, not a bid to out-feature the incumbents.

**Scope, stated up front:** packaging (`pip install`), a CI test suite, cross-platform
support (Linux first) and a skills registry are the roadmap, in that order.

**Ollama-only is permanent.** It is not a missing integration. It is the guarantee the
project exists for. Adding a remote endpoint would mean API keys and data leaving your
machine, which is precisely what this tool refuses to do.

**Issues and small PRs are welcome.** Large feature PRs are likely to be declined, not
because they aren't good, but because this is maintained by one person and unbounded scope is
how solo projects die. If you want to build something bigger on top of it, fork freely; that's
what the MIT license is for.

## License

MIT, see [`LICENSE`](./LICENSE). The bundled `skill-creator` and `mcp-builder` skills are
Apache-2.0, adapted from [anthropics/skills](https://github.com/anthropics/skills); see
[`skills/LICENSES.md`](./skills/LICENSES.md).
