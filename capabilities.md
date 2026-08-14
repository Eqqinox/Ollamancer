# Ollamancer: Exhaustive capability list
> Everything the agent can do, updated 2026-08-05 (v3.0)

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
| Cancel a running command | `run_command` is blocking (30s timeout) | Add async process management |
| Streaming long outputs | `run_command` buffers everything | Rewrite with subprocess + streaming |
| Parallel multitasking | The ReAct loop is sequential | Refactor with asyncio / threads |
| Dedicated SSH/SFTP connections | Possible via `run_command ssh` but fragile | Add an `ssh_exec(host, cmd)` tool |
| Sending emails / messages | No native mail/Slack tool, MCP can add one (see section 9 ter) | Configure a mail/Slack MCP server |
| ~~Reliable web search without SearXNG~~ | yes **Solved in v3.0**, `search_web` now falls back **automatically and invisibly** to the `duckduckgo` MCP server when SearXNG returns nothing usable (0 results, empty CAPTCHA-style snippets, or a transport error). The model no longer has to pick the MCP tool itself (same pattern as the v2.9.3 news routing) |, |
| Verifying that a citation genuinely matches its source | The citation nudge (v2.9.14) checks that a URL is present, not that the claim faithfully reflects it | **Partially closed (v3.0):** `_grounding_check` deterministically verifies that cited URLs/numbers/dates/names do appear in a tool result from the turn (otherwise it nudges). *Semantic* verification, does the claim reflect the source, remains out of scope. Possible complement: cross-model review with `/review-by <model>` |
| **Fabricating structure around a thin result** (a bare URI dressed up as an invented table/JSON) | An active 2026 research area (confabulation is a structural property of probabilistic generation, not a deliberate lie), no *complete* deterministic fix is known | **Deterministic layer added (v3.0):** `_grounding_check` flags hard tokens (cited numbers/dates/URLs/names) in the answer that are absent from every tool result of the turn, plus the claim-vs-action nudge (claiming "fixed/verified" with no real edit/verification; the "verified" half stands down on a search/read-only turn, where the word means checked against the sources and no verification tool could ever have run). It does not cover paraphrased structure, nor a paraphrased claim of having checked the sources, it remains a layer, not a guarantee; complement with `/review-by` |
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

### 11.1 Current ranking (2026-08-11, `pass^2`, four tasks)

**Battery:** reasoning with no tools, web search, an agentic fix-and-verify task, and
report writing. 100 points, 25 per task, five-minute cap per run, identical generation
parameters throughout. **Two runs per model per task, scored `pass^k`: the reported number
is the *minimum* across reps**, so a model counts only what it produces every time. Full
protocol, per-run evidence and stated limits in
[`benchmarks/model_ranking/RESULTS.md`](./benchmarks/model_ranking/RESULTS.md) §10.

| Model | Size | Reasoning | Search | Agentic | Report | pass^2 | Note |
|---|---|---|---|---|---|---|---|
| `qwen-heretic` ³ (Qwen3.5-9B) | 7.0 GB | 17 | 20 | 25 | 25 | **87.0** | Added 2026-08-11. Best agentic *and* best report score tested, both perfect on both reps. 0 swap across 8 runs |
| `gemma4:e4b-mlx` ² | 8.8 GB | 25 | 18.7 | 12 | 24 | **79.7** | Matches a 13 GB model at 8.8 GB, but never calls `get_datetime` unprompted (0 of 4 runs). Single-run: not a real 2nd place |
| `gemma4:12b-mlx` | 7.7 GB | 25 | 20.7 | 9 | 24.5 | **79.2** | Current default. Second-highest mean (89.3), but passed the agentic task only once of two |
| `gpt-oss:20b` | 13 GB | 19 | 19 | 12 | 25 | **75.0** | Current architect model. Best planner. **Identical score on both reps**, 0 timeouts, 0 swap: the most repeatable model here |
| `hf.co/HauhauCS/Qwen3.6-35B-A3B…:IQ2_M` | 12.6 GB | 17 | 17 | 12 | 23.8 | **69.8** | Added 2026-08-11. 35B MoE (~3B active): fits in RAM, 0 swap, and timed out less than the winner (2 of 8 vs 4 of 8) |
| `hf.co/HauhauCS/Qwen3.6-35B-A3B…:IQ3_M` | 16.3 GB | 16 | 22 | 6 | 25 | **69.0** | Added 2026-08-11. **Higher mean than IQ2_M (76.5 vs 74.7) but lower pass^2** — better on a good run, less dependable, and it swaps |
| `qwen3.5:4b` | 3.4 GB | 12 | 22 | 9 | 23.9 | **66.9** | Shipped fallback. Strong search at the smallest size, zero swap |
| `hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M` | 5.6 GB | 25 | 16 | 6 | 19 | **66.0** | Strong reasoning, but timed out on 4 of 8 runs |
| `qwen2.5:7b` ² | 4.7 GB | 12 | 18.7 | 6 | 21.2 | **57.9** | No standout task, no `thinking` capability |
| `jikepjikep_16HEX/gemma-4-12b-nightshift-heretic…` | 7.4 GB | 0 | 25 | 9 | 23.3 | **57.3** | Best uncensored option. Timed out 5 of 8 |
| `Agen/gemma-4-26B-A4B-it-uncensored-heretic` | 17 GB | 25 | 22 | 9 | 0 | **56.0** | Uncensored + vision. Perfect reasoning, but **+16.2 GB of swap** and never finished the report |
| `gemma4:26b-mlx` | 17 GB | 25 | 22 | 9 | 0 | **56.0** | Perfect reasoning, **+18.9 GB into swap** on a 24 GB machine, for a score below a 7.0 GB model |
| `gemma4:e4b-mlx-bf16` ² | 16 GB | 18 | 25 | 6 | 0 | **49.0** | Removed 2026-08-10. Full-precision twin of `gemma4:e4b-mlx`, and 31 points worse. See below |
| `ornith:9b` | 5.6 GB | 0 | 14.3 | 6 | 19 | **39.3** | Removed 2026-08-11. Timed out 5 of 8 |
| `qwen3.5:4b-mlx` | 4.0 GB | 0 | 4 | 6 | 18 | **28.0** | Added 2026-08-11. nvfp4 twin of `qwen3.5:4b`, and 39 points worse. See §11.1.1 |
| `gamy316/aileen1.0` | 4.9 GB | 1 | 14.3 | 6 | 0 | **21.3** | Removed 2026-08-11. Fastest overall, weakest answers, zero tool calls on the agentic task |
| `qwen3.5:9b-mlx` | 8.9 GB | 0 | 4 | 6 | 0 | **10.0** | Added 2026-08-11. nvfp4 twin of `qwen-heretic`, and 77 points worse. Timed out 6 of 8 runs |
| `lfm2.5:8b` | 5.2 GB | 0 | 0 | 9 | 0 | **9.0** | Removed 2026-08-11. Never wrote the report file |

**All totals are final** — the 26 outstanding hand judgements were completed on 2026-08-11, so
no row is provisional. ² **Not `pass^2`**, never given a second rep: `qwen2.5:7b` and
`gemma4:e4b-mlx-bf16` are single runs throughout, and `gemma4:e4b-mlx` is single-run except on
search, where it has four. Not comparable to the `pass^2` rows, so rank 2 is not a real second
place.
³ **`qwen-heretic:latest` is a local Ollama tag, not a pullable name.** The build is
`Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-Q4_K_M.gguf`, imported from a local file;
`ollama show --modelfile` resolves only to a blob hash with no upstream repository. Every other
model in this table can be pulled by the name shown — the top-ranked one cannot.

> **Caveat on ranks 1–3.** The ten models carried over from the earlier campaign had their
> two reps run on *different builds of the harness* (8 August vs 10–11 August, eight commits
> apart, including a new tool and a change to three generation defaults). The five added on
> 11 August ran both reps on one build. So `qwen-heretic`'s score is sound, but its margin over
> `gemma4:12b-mlx` mixes model variance with harness drift. See RESULTS.md §10.6.
>
> **The top two were checked before being trusted.** While the judged items were outstanding
> the gap was 2.8 points, inside the margin those items could move, so it was published as
> provisional. Completing them *widened* it to 7.8. **The default model has still not been
> changed:** one campaign on one machine is not grounds to re-point the docs, and
> `gemma4:12b-mlx` is the stronger reasoner (25 vs 17).

#### 11.1.1 The nvfp4 MLX builds

Two of the models added on 2026-08-11 are nvfp4 MLX re-quantisations of models already in the
table, and both collapse:

| Base model | Q4 build | nvfp4 build |
|---|---|---|
| Qwen3.5-9B | `qwen-heretic` **87.0** | `qwen3.5:9b-mlx` **10.0** |
| Qwen3.5-4B | `qwen3.5:4b` **66.9** | `qwen3.5:4b-mlx` **28.0** |

Neither nvfp4 build touched swap, so this is **not** the memory story of §11.1's 26B rows.
`qwen3.5:9b-mlx` timed out on 6 of 8 runs — it does not finish. Both declare `requires 0.19.0`.
Treat this as a **suspected runtime problem, not a verdict on the weights**: it has not been
isolated to a root cause, and until it is, the honest claim is that these builds do not work
in this harness on this machine.

Four findings that generalise beyond the ranking:

- **On 24 GB, models above roughly 13 GB are a poor trade.** Both 17 GB models scored
  below a 7.7 GB one while forcing 8 to 13 GB of swap.
- **Tool-call count predicts agentic success almost perfectly.** The top four made 10 to
  25 calls; the bottom three made 0 or 1 and simply asserted the code was fixed.
- **Memory headroom beats precision.** `gemma4:e4b-mlx` (4-bit, 8.8 GB) beat its own
  unquantised twin `gemma4:e4b-mlx-bf16` (16 GB) by **29 points**, winning three tasks of
  four. The extra 7.2 GB bought no measurable quality, only swap: the bf16 build was 2.7x
  slower on search for an identical result, and produced no report at all. Buy headroom
  before precision.
- **A capability badge is not a behaviour.** `gemma4:e4b-mlx` has `tools` and follows the
  system prompt's date rule only when told to. Left alone it skips `get_datetime` in 4 of 4
  runs and hands the raw phrase to the search engine, which silently returns results outside
  the requested window. Grounding stayed perfect (7.0/7.0, no fabricated URLs), so the
  failure is invisible to every check except `datetime_first`. For date-bounded questions
  prefer `qwen3.5:4b`, or say "check the date first", which works.

Read the limits section of `RESULTS.md` before treating any of this as settled. Two runs
per model per task is enough to separate 87 from 9; it is not enough to separate 1st from
3rd, especially since the ten models carried over from the earlier campaign had their two
runs executed on different builds of the harness.

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
