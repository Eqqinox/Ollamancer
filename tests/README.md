# Tests

Deterministic tests for `agent.py` — one file per feature/fix. They use only monkeypatched
`ollama.chat` (or direct function calls) plus `tempfile` working dirs, so they run offline with
**no Ollama, no network, and no writes to your real config**.

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

## TODO (roadmap #3 — CI)

These were written as fast standalone verification scripts. To formalize:
1. Wrap each script's body in `def test_*()` functions.
2. Add fixtures that reset mutated globals between tests (or keep per-module isolation).
3. Add a `conftest.py` that puts the project root on `sys.path`.
4. Wire up a **GitHub Actions** workflow running them on push.
