# Ollamancer: Exhaustive capability list
> Everything the agent can do, updated 2026-08-15 (v3.1)

---

## How to read this file

The agent has **35 dedicated tools** plus **`run_command`**, which exposes the entire shell.
So there are two levels of capability:

- **Native** → a dedicated tool: reliable, with a precise docstring the model reads.
- **Via shell** → goes through `run_command`; works if the binary is installed.

> **New in v3.0 (2026-08-05):** `append_file` (chunked writes, anti-truncation),
> `search_semantic` (local RAG, meaning-based search via bge-m3), `analyze_image`
> (multimodal vision), `python_repl` (persistent Python interpreter). New commands:
> `/architect`, `/architect-models`, `/review-by`, `/resume`, `/failover-model`,
> `/vision-model`, `/context`, `/compact`; `/undo` became a list of git checkpoints;
> headless mode `--run`/`--recipe`. Context cap doubled to **64K** plus **context
> compaction** (auto-compaction off by default). **Slash-command autocomplete** (type `/`
> to list everything; each character filters). **Esc (or Ctrl+C) stops the running model**
> and returns to the prompt without quitting the session. **Private mode `--private`**:
> ephemeral session, no trace of the conversation on disk (see the "Privacy & logs" table
> in the manual). **Skills** (`/skills`, `/skill <name>`, `load_skill` tool): reusable
> workflows in the **open `SKILL.md` format** (portable with Claude Code/Cursor/Codex),
> with progressive disclosure. See the dedicated sections below and `DESIGN.md`.

---

## 1. Search & information

### Web
- Search the internet for current information, short snippets (local SearXNG, no tracking) **[native, `search_web`]**
- Search **and actually read** the top 3 results (clean extraction via `trafilatura`, not just snippets), each source annotated with the **publication date** found and the **number of engines that independently confirm it** **[native, `search_web_deep`]**
- Read the text content of a web page, article or documentation, "reader mode" extraction (`trafilatura`), robots.txt respected, honest User-Agent **[native, `fetch_url`]**
- Read a JS-heavy page (single-page app) via a real headless browser (Playwright/Chromium) **[native, `fetch_url_rendered`]**
- Download a file from a URL (`curl`, `wget`) **[shell]**
- Call a REST API (GET, POST, PUT, DELETE) with `curl -X POST -d...` **[shell]**
- Look up available packages (`pip index versions`, `npm search`, `brew search`) **[shell]**
- Search results are cached for 5 minutes within a session, repeating a near-identical query doesn't hit SearXNG again
- Cover several **sections of one answer in a single search** (`search_web_deep(query, sections=[…])`), on any topic — news by region, models by benchmark, a how-to by cause/fix: the call returns the pages it read **plus the results it did not open**, which arrived in the same response and used to be discarded, so upstream engines still see **one query** and the extra breadth costs no extra requests **[native, `search_web_deep`; `MAX_SECTIONS` in `/parameters`, v3.1]**
- Get a web answer **organised into sections that match the question** (news brief by region/theme, comparison by criterion, cause/fix/verify, price table…), answer first, a date and a source per item: the `web-answer-format` skill, **auto-loaded code-side** on a recency/"look it up" wording so it doesn't depend on the model choosing to load it **[skill, automatic, v3.1]**

### Local system
- Get the exact date and time **[native]**
- Find a file by name or pattern anywhere in the project **[native]**
- Search for a string or regex across every file in the project **[native]**
- Find files with Spotlight (`mdfind "name OR content"`) **[shell, macOS]**
- List running processes (`ps aux`, `pgrep`) **[shell]**
- Check system resources, CPU, RAM, disk (`vm_stat`, `df -h`, `top -l 1`) **[shell]**
- List active macOS services (`launchctl list`) **[shell, macOS]**
- View active network connections (`lsof -i`, `netstat`) **[shell]**

---

## 2. Files & folders

### Reading
- Read a whole file with line numbers **[native]**
- Read a specific line range (e.g. lines 45-80) without loading the whole file **[native]**
- List a folder's contents with sizes and types **[native]**
- Search for a pattern across every file in the project **[native]**
- View a file's metadata, date, permissions, size (`ls -la`, `stat`) **[shell]**
- Read JSON, YAML, TOML, CSV files and extract values (`jq`, `python3`) **[shell]**
- Unpack and read an archive (`unzip`, `tar -xzf`) **[shell]**

### Writing & modifying
- Create a file with content **[native, `write_file`]**
- **Append to a file / write a large file in reliable chunks** (works around Ollama's JSON truncation) **[native, `append_file`, v3.0]**
- Surgically modify one precise block of a file without rewriting the rest **[native]**
- Create folders and their whole parent tree **[native]**
- Copy, move, rename files (`cp`, `mv`) **[shell]**
- Delete files or folders (`rm`, `rm -rf`) **[shell]**
- Change permissions (`chmod`, `chown`) **[shell]**
- Create symlinks (`ln -s`) **[shell]**
- Compress files (`zip`, `tar -czf`, `gzip`) **[shell]**
- Generate data and write it as JSON, CSV or Markdown **[native + shell]**

---

## 3. Development & code

### Codebase navigation
- Explore the structure of an unfamiliar project **[native]**
- **Ranked map of the whole repository**, every file's classes and functions ordered by PageRank over a "who uses whose names" graph, truncated to a character budget; Python with no dependencies, other languages via the optional `treesitter` extra **[native, `repo_map`]**
- Find where a function, class or variable is defined **[native]**
- **Conceptual/semantic search by meaning** ("where is the retry logic handled?"), local RAG over the project via bge-m3 embeddings, incremental SQLite index **[native, `search_semantic`, v3.0]**
- Find every use of a function in the project **[native]**
- **Load a reusable workflow (skill)** in the open `SKILL.md` format (instructions + reference files), progressive disclosure, portable with Claude Code/Cursor/Codex **[native, `load_skill`; commands `/skills`, `/skill <name>`, v3.0]**
- Identify every import of a module **[native]**
- List every TODO/FIXME/HACK in the code **[native]**
- Analyse a file's complexity, line count, function count **[shell + native]**

### Writing code
- Write a script in any language (Python, Bash, JS, …) **[native]**
- Modify an existing function without touching the rest of the file **[native]**
- Add a new method to an existing class **[native]**
- Refactor code across several steps **[native]**
- Generate unit tests for a function **[native]**
- Fix bugs identified in the code **[native]**
- Translate code from one language to another **[native]**
- Add docstrings/comments to existing code **[native]**

### Execution
- Run a Python script (`python3 script.py`) **[shell]**
- Run JavaScript/Node (`node script.js`) **[shell]**
- Run Bash directly **[shell]**
- Compile and run Go, Rust, C/C++, Java **[shell]**
- Start a development server (`uvicorn`, `flask run`, `npm run dev`) **[shell]**
- Run inline Python (`python3 -c "..."`) **[shell]**
- **Run Python in a persistent interpreter**: variables and imports survive between calls, last expression echoed (step-by-step data analysis, quick computation, incremental debugging) **[native, `python_repl`, v3.0]**

### Tests & quality
- Run pytest, unittest, Jest, Mocha, cargo test, go test **[native]**
- Analyse test results and identify failures **[native]**
- Fix code until the tests pass (autonomous loop) **[native]**
- Lint code (`flake8`, `pylint`, `eslint`, `ruff`) **[shell]**
- Format code (`black`, `prettier`, `gofmt`, `rustfmt`) **[shell]**
- Measure test coverage (`pytest --cov`, `jest --coverage`) **[shell]**
- Generate a code-quality report **[shell]**

### Dependency management
- Install Python packages (`pip install`, `pip3 install`) **[shell]**
- Install Node packages (`npm install`, `yarn add`, `pnpm add`) **[shell]**
- Install macOS tools (`brew install`) **[shell]**
- Manage Python virtual environments (`python3 -m venv`, `source.venv/bin/activate`) **[shell]**
- Update dependencies (`pip install -U`, `npm update`) **[shell]**
- Check for vulnerabilities (`pip-audit`, `npm audit`) **[shell]**
- Generate/update requirements.txt, package.json **[native + shell]**

---

## 4. Git & versioning

- See repo status, modified files, branch, untracked **[native]**
- See uncommitted changes (precise diff) **[native]**
- See commit history with a graph **[native]**
- Create a commit with a message **[native]**
- Stage specific files (`git add file.py`) **[shell]**
- Create/switch branches (`git checkout -b`, `git switch`) **[shell]**
- Merge branches (`git merge`, `git rebase`) **[shell]**
- Push to the remote (`git push`) **[shell]**
- Pull the latest changes (`git pull`, `git fetch`) **[shell]**
- Resolve merge conflicts (read + edit the files) **[native]**
- Clone a repository (`git clone URL`) **[shell]**
- See who wrote which line (`git blame`) **[shell]**
- Go back to an earlier commit (`git checkout SHA`, `git reset`) **[shell]**
- Manage stashes (`git stash`, `git stash pop`) **[shell]**
- Create tags (`git tag v1.0.0`) **[shell]**
- Generate commit messages from diffs **[native]**

---

## 5. macOS automation

> This section is macOS-specific. On other platforms the equivalent shell commands differ;
> everything else in this document is portable.

### System
- Open an application or a file (`open -a`, `open file.pdf`) **[shell]**
- Open a URL in the default browser (`open https://...`) **[shell]**
- Control volume and brightness (via `osascript`) **[shell]**
- Read the clipboard (`pbpaste`) **[shell]**
- Write to the clipboard (`echo "text" | pbcopy`) **[shell]**
- Make the Mac speak (`say "message"`) **[shell]**
- Take a screenshot (`screencapture ~/Desktop/screenshot.png`) **[shell]**
- Prevent sleep during a long task (`caffeinate`) **[shell]**
- Schedule a deferred task (`at now + 1 hour "command"`) **[shell]**
- Send a macOS notification (`osascript -e 'display notification "msg"'`) **[shell]**

### Process management
- Start a program in the background (`command &`) **[shell]**
- Stop a process (`pkill name`, `kill PID`) **[shell]**
- See a process's CPU/RAM usage (`ps -o %cpu,%mem -p PID`) **[shell]**
- Restart a service (`launchctl kickstart`, `brew services restart`) **[shell]**

---

## 6. Data & processing

### Text & documents
- Search/replace with regex across files (`grep`, `sed`) **[shell]**
- Count lines, words, characters (`wc`) **[shell]**
- Sort and deduplicate lines (`sort`, `uniq`) **[shell]**
- Convert documents, Markdown → PDF, HTML → text (`pandoc`) **[shell]**
- Extract text from PDFs (`pdftotext`, `python3` with pdfminer) **[shell]**
- Generate Markdown or HTML reports from data **[native]**

### JSON / CSV / YAML
- Query JSON (`jq '.users[].name'`) **[shell]**
- Convert between formats (`python3 -c`, `jq`, csvkit) **[shell]**
- Create and write structured JSON, CSV, YAML files **[native]**
- Analyse logs and extract statistics **[shell + native]**

### Images & media (if installed)
- **Analyse/describe an image, read a screenshot or a chart**: one-shot call to an installed multimodal model, sequential loading **[native, `analyze_image`, v3.0]**
- Resize and convert images (ImageMagick: `convert img.png -resize 50%`) **[shell]**
- Extract image metadata (`exiftool file.jpg`) **[shell]**
- Convert video/audio (`ffmpeg -i input.mp4 output.mp3`) **[shell]**
- Create a GIF from images or a video **[shell]**

---

## 7. Docker & infrastructure

- List containers and images (`docker ps`, `docker images`) **[shell]**
- Start/stop containers (`docker start`, `docker stop`) **[shell]**
- Run a command inside a container (`docker exec -it name bash`) **[shell]**
- Build an image (`docker build -t name.`) **[shell]**
- Manage Docker volumes and networks **[shell]**
- Use Docker Compose (`docker compose up -d`, `docker compose logs`) **[shell]**
- Inspect container logs **[shell]**

---

## 8. Network & APIs

- Test a REST API (GET, POST, PUT, DELETE) with `curl` **[shell]**
- Download files with resume (`curl -C -`, `wget -c`) **[shell]**
- Test connectivity (`ping`, `traceroute`, `curl -I`) **[shell]**
- Check open ports (`lsof -i:3000`, `nc -zv host port`) **[shell]**
- Query DNS (`dig`, `nslookup`) **[shell]**
- Fetch an API's content and process it (fetch + jq/python3) **[shell + native]**
- Send requests with headers, auth and a JSON body via curl **[shell]**

---

## 9. Complex agentic workflows

What the agent can do autonomously by chaining its tools:

### Research & documentation
- Search the web → summarise → write a Markdown report → git commit
- Read online documentation → write a tested code example
- Compare several web sources → synthesise → structure as a table

### Autonomous development
- Find a bug from the tests → read the code → fix → re-run the tests → commit
- Analyse an unfamiliar project → explore → summarise the architecture
- Take an issue described in natural language → implement → test → commit
- Refactor a module in several steps, verifying at each step
- Generate a test suite for an existing file
- Read a README → install the dependencies → run the project

### System automation
- Watch a folder and process new files
- Analyse error logs and propose fixes
- Generate deployment scripts from a description
- Create a complete new-project structure (folders, files, git init, venv)

### Data
- Download CSV data → analyse → generate a report
- Call an API → transform the JSON → write the result to a file
- Scrape several web pages → consolidate → export

---

## 9 bis. Live settings (`/parameters`)

**Tool call display.** By default the agent prints one line per tool call while it works,
showing the name, the identifying argument, the size of the result and the elapsed time.
**`/details`** then prints the complete record of the turn just finished: every call, its
full arguments, and its **untruncated** result. Setting **Tool Call Display** to `full`
restores the original two-panel view, which shows more on screen but actually less of a
large result, since those panels cut each one at 300 characters and discard the remainder.


A full-screen interactive menu (`curses`, navigate with ↑/↓/←/→) for adjusting things without
touching the code: Ollama generation parameters (temperature, top_p, top_k, repeat penalty,
max tokens, seed, **none of which were tunable before 2026-08-02**), safety limits (max
context, max tool rounds, max background processes, auto-retry budgets), and web-search
settings (language, number of results, `search_web_deep` behaviour). See `Agentic_Manual.md`
for the full parameter reference. **Since v2.9.14 the settings persist between sessions**
(`~/.agentic_1a_params.json`, saved on every adjustment, reloaded at startup).

---

## 9 ter. MCP (Model Context Protocol): third-party tools

Since v2.9.14 the agent can connect to external MCP servers in addition to its 35 native
tools, the same mechanism as Claude Desktop/Claude Code.

**Configuration (one-time):**
1. `pip install mcp` (optional dependency, if absent, MCP is silently disabled and the rest of the agent is unchanged)
2. Create `~/.agentic_1a_mcp.json` in the form `{"mcpServers": {"name": {"command": "...", "args": [...]}}}`, **exactly the same format as Claude Desktop/Claude Code**, so an existing config can be reused directly

**After that it's automatic on every launch:** the agent connects to each configured server,
discovers its tools (prefixed `mcp__<server>__<tool>`), and offers them to the model exactly
like native tools, nothing to do per session. The `/mcp` command lists connected servers and
discovered tools. MCP tools are treated as "risky" by default in safe mode (`/safe`), an MCP
server can do anything a local tool can. A server that fails to start is logged and skipped;
it never prevents the other servers or the rest of the agent from working.

Note: The feature is tested and verified, but **no server is configured by default**, it stays
dormant as long as `~/.agentic_1a_mcp.json` lists nothing.

---

## 9 quater. Docker sandbox for shell execution (opt-in)

Since v2.9.14, `run_command`/`run_tests` can run inside an isolated Docker container instead
of directly on the machine, enable it with `--sandbox` at launch or `/sandbox` mid-session.
It is orthogonal to safe mode: `/safe` gates *approval*, the sandbox contains the *blast
radius*, and the two combine. The project folder is mounted into the container; a generic
default image (Python + Node + common tools) is built once and reused, and can be customised
per project via `.agentic/sandbox.Dockerfile`. If Docker is unavailable while the sandbox is
enabled, the command is refused rather than silently run on the host.

---

## 9 quinquies. User-chosen default model, with random fallback

Since v2.9.15, `DEFAULT_MODEL` in the code is no longer the only source of the startup model:

- **`/model`** lists the installed models **newest first**, the same order `ollama list`
  uses, so a model you just pulled is at the top rather than buried alphabetically.
- **`/default-model`** opens the same interactive picker as `/model`, but saves the choice to
  `~/.agentic_1a_default_model.txt`: used on every future launch, for every project, until
  changed. (`/model` on its own still changes the model for the current session only, without
  touching the persisted default.)
- **Automatic fallback if the default disappeared:** if the chosen default model (or the code's
  `DEFAULT_MODEL` constant, when nothing is saved) has since been deleted (`ollama rm`), the
  agent no longer crashes at startup as it used to, it automatically picks a random
  tool-capable model from those currently installed, with an explicit message explaining what
  happened and inviting you to set a new default with `/default-model`.
- If **no** tool-capable model is installed at all, the agent shows the usual
  no-model-available message and stops, that case remains a deliberate halt, because there is
  nothing to fall back to.

---

## 10. What the agent CANNOT do (current limits)

| Limitation | Reason | Possible solution |
|---|---|---|
| ~~See images / screenshots~~ | yes **Solved in v3.0**, `analyze_image(path, question)` tool, one-shot call to an installed multimodal model (sequential loading; configure with `/vision-model`) |, |
| ~~RAG over local documents~~ | yes **Solved in v3.0**, `search_semantic(query)` tool, bge-m3 embeddings + stdlib SQLite index (no added dependency: neither ChromaDB nor FAISS), incremental re-indexing |, |
| GUI control / mouse clicks | No Accessibility API tool | Add `osascript` or PyAutoGUI |
| ~~A turn that runs out of budget returns nothing~~ | yes **Solved 2026-08-15.** Hitting `MAX_TOOL_ROUNDS`, or the optional `TURN_BUDGET_SECONDS` wall clock, used to return a status line and discard everything gathered — in the model-ranking campaign that happened to 50 of 135 runs, one of them after 35 successful tool calls. `loop._salvage` now spends one final generation, with tools disabled, answering from the evidence already in the conversation and stating what is missing. `_grounding_check` still runs on it and **warns** rather than nudging, because a nudge is another generation and the budget is gone |, |
| Cancel a running command | `run_command` is blocking (30s timeout) | Add async process management |
| Streaming long outputs | `run_command` buffers everything | Rewrite with subprocess + streaming |
| Parallel multitasking | The ReAct loop is sequential | Refactor with asyncio / threads |
| Dedicated SSH/SFTP connections | Possible via `run_command ssh` but fragile | Add an `ssh_exec(host, cmd)` tool |
| Sending emails / messages | No native mail/Slack tool, MCP can add one (see section 9 ter) | Configure a mail/Slack MCP server |
| ~~Reliable web search without SearXNG~~ | yes **Solved in v3.0**, `search_web` now falls back **automatically and invisibly** to the `duckduckgo` MCP server when SearXNG returns nothing usable (0 results, empty CAPTCHA-style snippets, or a transport error). The model no longer has to pick the MCP tool itself (same pattern as the v2.9.3 news routing) |, |
| Verifying that a citation genuinely matches its source | The citation nudge (v2.9.14) checks that a URL is present, not that the claim faithfully reflects it | **Partially closed (v3.0):** `_grounding_check` deterministically verifies that cited URLs/numbers/dates/names do appear in a tool result from the turn (otherwise it nudges). *Semantic* verification, does the claim reflect the source, remains out of scope. Possible complement: cross-model review with `/review-by <model>` |
| **Fabricating structure around a thin result** (a bare URI dressed up as an invented table/JSON) | An active 2026 research area (confabulation is a structural property of probabilistic generation, not a deliberate lie), no *complete* deterministic fix is known | **Deterministic layer added (v3.0):** `_grounding_check` flags hard tokens (cited numbers/dates/URLs/names) in the answer that are absent from every tool result of the turn, plus the claim-vs-action nudge (claiming "fixed/verified" with no real edit/verification; the "verified" half stands down on a search/read-only turn, where the word means checked against the sources and no verification tool could ever have run). It does not cover paraphrased structure, nor a paraphrased claim of having checked the sources, it remains a layer, not a guarantee; complement with `/review-by`. **Verified, not assumed:** `_grounding_check` fired zero times in 264 benchmark runs, which on its own is equally consistent with a calibrated check and a dead one, so its sensitivity was measured instead — 91/91 injected fabrications caught on real answers against their real tool results, 91% caught on realistic one-digit perturbations (`DESIGN.md` §4.2c, `tests/test_grounding_sensitivity.py`) |
| **The same event reported twice as two separate items** | Every honesty check compared the answer to its *sources*; none compared the answer to *itself*, so one school shooting could appear as "seven killed" and "nine killed" four rows apart with both figures individually grounded | **Deterministic check added**: `_duplicate_items` flags two list items sharing a rare multi-word proper noun. Measured at 1/2 real duplicates caught with 0 false positives on a six-answer corpus; a shared-URL signal was tested and rejected (live blogs source many unrelated stories). A nudge, capped at 1 |
| **Describing a hypothetical tool result without ever calling it** ("returns something like this" + invented values) | A distinct sub-case of the fabrication above, observed during a v2.9.16 re-test | A dedicated heuristic nudge was added (v2.9.17, `MAX_GROUNDING_NUDGES`), detection by sentence pattern plus `{ }`/code-block structure, not a semantic check |
| Certain MCP tools requiring advanced protocol capabilities (e.g. `taskSupport`) | `_session_main()` does not negotiate those capabilities at `initialize()` | Implement extended MCP capability negotiation, not done; those tools fail cleanly in the meantime |

> yes Solved since this file was first written: persistent memory between sessions
> (`memory_write`/`memory_read`), JS scraping (`fetch_url_rendered` via Playwright),
> persistent `/parameters` settings, MCP support, opt-in Docker sandbox (see sections 9
> bis/ter/quater), **confining file paths to the project folder** (v2.9.16), and the
> **anti-hypothetical-tool-result nudge** (v2.9.17).
>
> yes **Solved in v3.0** (see `DESIGN.md`): vision (`analyze_image`), local RAG
> (`search_semantic`), chunked anti-truncation writes (`append_file`), persistent Python REPL
> (`python_repl`), automatic DuckDuckGo search failover, the mojibake encoding fix, the
> closest-path hint, git checkpoints (`/undo`), streaming of the final answer, session
> persistence (`/resume`), architect/editor mode (`/architect`), cross-model review
> (`/review-by`), headless mode (`--run`/`--recipe`), deterministic honesty layers
> (`_grounding_check`, claim-vs-action nudge), model failover on plumbing bugs
> (`/failover-model`), a **doubled context cap (64K) plus research-backed context compaction**
> (`/context`, `/compact`, auto-compaction off by default), and the **streaming RAM-spinner
> fix**.

---

## 11. Capabilities by model

What the agent can actually do depends on the model driving it. Two benchmark campaigns
are reported below. They are kept apart on purpose: they measured different things, so
their results are not comparable and no combined ranking is offered. Only four models
appear in both. The ranking in §11.1 is `pass^2`; the reliability campaign in §11.2 is
single-run and its numbers have not been re-measured under `pass^k`.

### 11.1 Current ranking (2026-08-15, corrected scorer)

**Battery:** reasoning with no tools, web search, an agentic fix-and-verify task, and report
writing. 25 points per task, five-minute cap per run, identical generation parameters
throughout. Two runs per model per task where available, scored `pass^k`: the reported number is
the *minimum* across reps, so a model counts only what it produces every time. Full protocol,
per-run evidence and stated limits in
[`benchmarks/model_ranking/RESULTS.md`](./benchmarks/model_ranking/RESULTS.md) §11.

> **This replaces the table published on 2026-08-11.** That one was produced by a scorer which
> recorded a timed-out run as `status: "ok"` and then scored it on whatever file it had left
> behind, so runs that produced nothing collected up to 25/25. Correcting it moved 42 of 135
> runs and cost fifteen of eighteen models points; the model ranked first at 87.0 had timed out
> on all four of its agentic and report runs, and is now eleventh.
>
> **The headline is a core score out of 75** — reasoning, search, report — with the agentic task
> reported separately. **14 of 18 models score zero on it and the best result in the campaign is
> 12/25**, so blending it into one total produces a figure that describes neither. `DESIGN.md`
> §6 already calls that task *the open problem*. **Runs completed** counts how many of a model's
> runs returned an answer at all rather than hitting the cap: it distinguishes weak from slow,
> and one score cannot.

| # | Model | Size | Reasoning | Search | Report | **Core /75** | Agentic /25 | Runs completed |
|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.6-35B-A3B **IQ2_M** | 12.6 GB | 17 | 17 | 23.8 | **57.8** | 0 | 6/8 |
| 2 | qwen2.5:7b ◆ | 4.7 GB | 12 | 19 | 21.2 | **51.9** | 6 | 4/4 |
| 3 | Agen/gemma-4-26B-heretic | 17 GB | 25 | 22 | 0.0 | **47.0** | 0 | 4/8 |
| 4 | gemma4:26b-mlx | 17 GB | 25 | 22 | 0.0 | **47.0** | 0 | 4/8 |
| 5 | gemma4:12b-mlx | 7.7 GB | 25 | 21 | 0.0 | **45.7** | 0 | 5/8 |
| 6 | gemma4:e4b-mlx ◆ | 8.8 GB | 25 | 19 | 0.0 | **43.7** | 0 | 5/7 |
| 7 | gemma4:e4b-mlx-bf16 ◆ | 16 GB | 18 | 25 | 0.0 | **43.0** | 0 | 3/4 |
| 8 | Ornith-1.0-9B-GGUF | 5.6 GB | 25 | 16 | 0.0 | **41.0** | 0 | 4/8 |
| 9 | gpt-oss:20b | 13 GB | 19 | 19 | 0.0 | **38.0** | 12 | 7/8 |
| 10 | Qwen3.6-35B-A3B **IQ3_M** | 16.3 GB | 16 | 22 | 0.0 | **38.0** | 0 | 4/8 |
| 11 | qwen-heretic | 7.0 GB | 17 | 20 | 0.0 | **37.0** | 0 | 4/8 |
| 12 | qwen3.5:4b | 3.4 GB | 12 | 22 | 0.0 | **34.0** | 0 | 6/8 |
| 13 | gemma-4-12b-nightshift-heretic | 7.4 GB | 0 | 25 | 0.0 | **25.0** | 0 | 3/8 |
| 14 | qwen3.5:4b-mlx | 4.0 GB | 0 | 0 | 18.0 | **18.0** | 0 | 5/8 |
| 15 | gamy316/aileen1.0 | 4.9 GB | 1 | 14 | 0.0 | **15.3** | 6 | 8/8 |
| 16 | ornith:9b | 5.6 GB | 0 | 14 | 0.0 | **14.3** | 0 | 3/8 |
| 17 | lfm2.5:8b | 5.2 GB | 0 | 0 | 0.0 | **0.0** | 9 | 8/8 |
| 18 | qwen3.5:9b-mlx | 8.9 GB | 0 | 0 | 0.0 | **0.0** | 0 | 2/8 |

◆ Single-observation rows, not comparable to the `pass^2` rest.

**Reading it:** the 300 s cap decides more than the models do — 50 of 135 runs produced nothing.
`gamy316/aileen1.0` and `lfm2.5:8b` completed 8/8 and still rank near the bottom: weak, not slow.
`Agen/gemma-4-26B` ranks third on 4/8: strong when it finishes, finishes half the time.
`gpt-oss:20b` ranks ninth on core while holding **the highest agentic score any model has
recorded**, on 7/8 completed runs. Treat the top half as unordered — ranks 1–8 span 57.8 to 41.0
with three non-comparable rows inside them.

### 11.2 Earlier code-focused campaign (2026-08-02, archival)

Kept because it measured two things the newer campaign does not: **claims verified by
external fact-checking**, and **code verified by `pytest`**. Battery: four identical
tests, factual search with external fact-checking, reasoning, verified code, and a
multi-step task. Full detail and history in `DESIGN.md`.

Rows are retained even where the model has since been removed from this machine. Several
are negative results, and a finding that a model is unusable is worth as much as a
finding that one is good; deleting it would only cost the next person the download. The
status column says what is still here, so no row reads as a recommendation to install
something that was tested and dropped.

> Also removed since this campaign and not tabulated: `lfm2:24b-a2b`,
> `brianmatzelle/qwen3-coder-heretic:30b`, `qwen3:8b`, and the Heretic variants of
> `qwen3.5:9b`, all after a confirmed failure (the plain-text pseudo tool-call bug, see
> `DESIGN.md`) or because a better candidate replaced them.

| Model | Status | Strengths | Weaknesses |
|---|---|---|---|
| `hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M` | installed | Best factual precision in this campaign (4/4 verified by external fact-check), builds its own edge-case tests without being asked, reliable spontaneous discovery of unnamed MCP tools, including with zero hints | Only 9B, so more limited in raw capacity than larger models on very complex tasks |
| `qwen3.5:4b` | installed | A very close 2nd, the smallest model tested, very precise factual search, the most rigorous code verification | 4B, even more limited in raw capacity |
| `Agen/gemma-4-26B-A4B-it-uncensored-heretic` | installed | 3rd, MoE, uncensored (Heretic method, low capability loss), the most systematic code-correction process, verified by external fact-checking | 18 GB, the heaviest of the recommended models |
| `igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:Q4_0` | tested, removed | 4th, uncensored (Heretic), 4/4 tests passed | Messier execution (redundant calls), 1 confirmed factual error on a regulatory topic |
| `gpt-oss:20b` | installed | MoE, natively supported by Ollama (first-class support, not a community re-quantised GGUF), 0 confirmed factual errors, the fastest of all (see `DESIGN.md`) | Pickier about search than the others, needs an explicit date rather than "today" to avoid getting stuck on a midnight-boundary problem |
| `qwen3.6:27b` / `qwen3.6:35b-a3b` | tested, unusable | Theoretically deeper reasoning | **Objectively impractical on this hardware**, zero output observed in 8 minutes on a simple question, including the MoE version |
| "Uncensored" models via classic abliteration (`huihui_ai/*`) | not recommended | No content restrictions | Repeated factual fabrication under pressure (see `DESIGN.md`), prefer a model uncensored with the **Heretic** method if the subject requires it |

**Since v2.9.15** the default-model choice is no longer hard-coded, see section 9 quinquies.

---

## 12. Example prompts that work

```
# Development
"Create a complete FastAPI project with JWT auth, Pydantic models and tests"
"Find every bug in this module and fix them one by one"
"Generate unit tests for every function in utils.py"
"Refactor the UserService class to use async/await"
"Analyse this project and tell me how to improve it"

# Git & deployment
"Commit all changes with a descriptive message based on the diff"
"Create a feature/user-auth branch and implement authentication"
"Prepare a CHANGELOG.md from the git log"

# Research & data
"Search for best practices for securing a REST API and apply them"
"Download this CSV, analyse it and generate a Markdown report"
"Compare the FastAPI and Flask docs, tell me which suits this project better"

# Automation
"Create a deployment script that builds, tests, and pushes to git"
"Analyse every error log in the logs/ folder and summarise the problems"
"Initialise this empty folder as a modern Python project (venv, git, structure)"
```
