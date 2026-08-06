# Tests

Deterministic tests for the agent — one file per feature/fix. They use only monkeypatched
`ollama.chat` (or direct function calls) plus `tempfile` working dirs, so they run offline with
**no Ollama, no network, and no writes to your real config**.

> That last claim is now enforced, not just asserted. `run_all.sh` checksums every
> `~/.agentic_1a_*` file before and after the run and fails if any changed. This was added
> after `test_structure`'s `/parameters` round-trip silently rewrote the live
> `~/.agentic_1a_params.json` — bumping all 30 settings one step, including
> `GEN_NUM_PREDICT` from `-1` (unlimited) to `127`, which truncates every model answer. The
> suite stayed green the whole time.

## How to run (today)

Each test must run in its **own process**. They are currently standalone scripts (module-level
assertions ending in `... ALL PASS`), and several deliberately mutate module globals
(`agent.STREAM_FINAL`, `agent.ollama.chat`, `agent.PROJECT_ROOT`, …) — so running them all in a
single interpreter would cross-contaminate. Use the runner, which isolates each in a subprocess:

```bash
bash tests/run_all.sh          # from the project root → "tests: 22 passed, 0 failed"
```

Or a single test:

```bash
PYTHONPATH="$PWD" .venv/bin/python tests/test_skills.py
```

## Coverage (22 files)

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

## Structural guardrails

Two of the tests are not behavioural — they exist to make the ongoing modularization safe:

| File | Enforces |
|---|---|
| `test_structure.py` | Golden master over the agent's *shape*: the 34-tool registry, the 36 slash commands, EN/FR parity across `STR`/`SYSTEM_PROMPT`/`HELP_TEXT`, and the 30-entry `/parameters` schema — including a live write/read round-trip proving the menu is still wired to the variables the agent reads. |
| `test_import_rules.py` | `config` and `state` must always be reached through the module object (`config.X`), never `from config import X`, which copies a value that never sees a later rebinding. Also bans `globals()[...]` across module boundaries and any local shadowing those module names. |

Both were verified *negatively* — each fails on the bug it exists to catch.

## TODO (roadmap #3 — CI)

These were written as fast standalone verification scripts. To formalize:
1. Wrap each script's body in `def test_*()` functions.
2. Add fixtures that reset mutated globals between tests. **`agentic.state.reset()` does this in
   one call** — it restores every per-session global to its startup default and clears the caches
   in place, without touching `config` (settings survive). So the fixture is roughly:
   ```python
   @pytest.fixture(autouse=True)
   def clean_state():
       state.reset()
       yield
       state.reset()
   ```
   Note some tests also monkeypatch `agent.ollama.chat`, which is not state — restore that separately.
3. Add a `conftest.py` that puts the project root on `sys.path`.
4. Wire up a **GitHub Actions** workflow running them on push (matrix: Python 3.12 and 3.14, to
   prove the declared 3.12 floor).
