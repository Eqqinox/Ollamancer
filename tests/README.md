# Tests

Deterministic tests for the agent, one file per feature/fix. They import from the
`agentic/` package; anything that is monkeypatched must be patched on the module that *owns*
it, since a name imported elsewhere is a separate binding.
 They use only monkeypatched
`ollama.chat` (or direct function calls) plus `tempfile` working dirs, so they run offline with
**no Ollama, no network, and no writes to your real config**.

> That last claim is now enforced, not just asserted. `run_all.sh` checksums every
> `~/.agentic_1a_*` file before and after the run and fails if any changed. This was added
> after `test_structure`'s `/parameters` round-trip silently rewrote the live
> `~/.agentic_1a_params.json`, bumping all 30 settings one step, including
> `GEN_NUM_PREDICT` from `-1` (unlimited) to `127`, which truncates every model answer. The
> suite stayed green the whole time.

## How to run

Either runner works, and both run each test in its **own process**.

```bash
pytest                         # 29 scripts plus a collection guard
pytest -k skills               # one script
pytest -x                      # stop at the first failure
bash tests/run_all.sh          # no pytest needed
```

`pytest` gives you the failing script's stdout, stderr and traceback instead of a bare
exit code. `run_all.sh` needs nothing but bash and works when pytest is not installed.
Neither wraps the other.

Each test must run in its **own process**. They are currently standalone scripts (module-level
assertions ending in `... ALL PASS`), and several deliberately mutate module globals
(`agent.STREAM_FINAL`, `agent.ollama.chat`, `agent.PROJECT_ROOT`, …), so running them all in a
single interpreter would cross-contaminate. Use the runner, which isolates each in a subprocess:

```bash
bash tests/run_all.sh          # from the project root, "tests: 34 passed, 0 failed"
```

Or a single test:

```bash
PYTHONPATH="$PWD" .venv/bin/python tests/test_skills.py
```

## Coverage (24 files)

| File | Feature under test |
|---|---|
| `test_a1` | `append_file` + chunked-write note |
| `test_a2` | SearXNG → DuckDuckGo-MCP failover |
| `test_a3` | bytes→trafilatura encoding fix (mojibake) |
| `test_a4` | closest-path hint on file-not-found |
| `test_a56` | `_grounding_check` + claim-vs-action nudge |
| `test_a7` | model failover on plumbing-bug exhaustion |
| `test_b1` | git checkpoints / `/undo` |
| `test_b2` | streaming reconstruction + toggle |
| `test_b3` | session persistence / `/resume` |
| `test_b4` | architect read-only gate + sequential load |
| `test_b4b` | architect read-only "write the plan" nudge |
| `test_b5` | `search_semantic` (fake embedder) |
| `test_b6` | `analyze_image` detection + sequential load |
| `test_b7` | persistent `python_repl` |
| `test_b8` | cross-model `/review-by` |
| `test_b9` | headless `--run` / `--recipe` |
| `test_compact` | context compaction |
| `test_completer` | slash-command autocomplete |
| `test_escape` | Esc-to-stop plumbing |
| `test_ctrlc` | Ctrl+C at prompt cancels (doesn't quit) |
| `test_private` | `--private` writes nothing to disk |
| `test_skills` | skills discovery / `load_skill` |
| `test_structure` | golden master: tool registry, slash commands, EN/FR parity, params schema |
| `test_import_rules` | live-module import rules, no globals() across modules, no shadowing, no undefined names |
| `test_ram_readout` | the live RAM figure comes from `ollama.ps()`, not process RSS, which undercounts the MLX engine |
| `test_packaging` | the 14 bundled skills are findable in a checkout and shipped by the wheel; requirements.txt and pyproject stay in step |
| `test_repomap` | PageRank, the distinctiveness filter, Python extraction, ranking order, `focus=`, the character budget, and both language paths |
| `test_tool_display` | the compact one-line tool display, and that `/details` keeps the full untruncated result the line omitted |
| `test_banner` | the startup wordmark keeps its shape, and the width guard hides it on a terminal too narrow to hold it |
| `test_architect_guards` | architect phase stays read-only; no unsatisfiable claim-vs-action nudge |
| `test_nudge_marking` | automatic nudges are labelled as checks, in EN and FR, so they read as corrections rather than new user requests |
| `test_repetition_breaker` | stop nudging once an answer has collapsed into repeating itself |
| `test_source_diversity` | one page per outlet in search results, rather than several from the same domain |
| `test_duplicate_items` | flag the same event reported twice in one answer, without firing on a shared live-blog URL |
| `test_ram_units` | the `/model` header shows memory in binary GiB (a "24 GB" Mac reports 25.77 decimal GB and used to print **26**), while `usage_tier` keeps the decimal value so it still matches the model sizes Ollama reports. Pins both halves, and the 16.3 GB boundary model that the two divisors disagree about |

## Structural guardrails

Two of the tests are not behavioural. They exist to make the ongoing modularization safe:

| File | Enforces |
|---|---|
| `test_structure.py` | Golden master over the agent's *shape*: the 35-tool registry, the slash-command set, EN/FR parity across `STR`/`SYSTEM_PROMPT`/`HELP_TEXT`, and the 31-entry `/parameters` schema, including a live write/read round-trip proving the menu is still wired to the variables the agent reads. |
| `test_import_rules.py` | `config` and `state` must always be reached through the module object (`config.X`), never `from config import X`, which copies a value that never sees a later rebinding. Also bans `globals()[...]` across module boundaries and any local shadowing those module names. |

Both were verified *negatively*, each fails on the bug it exists to catch.

## How the pytest layer works

The scripts are **not** collected by pytest directly. They assert at import time and most
mutate module globals, so importing them into one interpreter would let them corrupt each
other, with whichever ran last deciding the result. Instead:

- `conftest.py` excludes every `test_*.py` from collection except the runner, and adds a
  session fixture that checksums `~/.agentic_1a_*` before and after the run.
- `test_scripts.py` parametrises over the scripts and runs each one in a subprocess with
  stdin closed.
- `test_every_script_is_collected` compares the two lists, so a new script can never end
  up both ignored by pytest and absent from the runner, silently untested.

An autouse `clean_state` fixture calls `state.reset()` around every test, which restores
each per-session global and clears the caches without touching `config`. Anything a test
patches that is not state, `ollama.chat` above all, must still be restored by the test.

CI runs both runners on Ubuntu against Python 3.12 and 3.14, the floor the README claims
and the current release.

## Still to do

Convert the scripts into real pytest functions with assertions pytest can introspect.
That is a per-file rewrite, not a mechanical one, because each script would need its
global mutations replaced by fixtures before it is safe to share an interpreter. The
subprocess runner above makes it optional rather than urgent.
