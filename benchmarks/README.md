# Benchmarks

Reusable test fixtures for evaluating model reliability on real coding tasks.
Created 2026-08-03. See `DESIGN.md` §6 ("The open problem — end-to-end multi-bug fixing")
for the full investigation these came from.

## game_py_bugfix

A small (~200-line) menu-driven text game with 4 real, verified bugs:

1. `new_game()` never sets an `"alive"` key, but `main()` reads `player["alive"]`
   in its loop condition — crashes on the very first loop iteration.
2. `new_game()`/`choose_character()` set `player["attack"]`, but every other
   function (`player_attack`, `heal`, `level_up`, `print_screen`) reads
   `player["attack_range"]` — crashes on the first status screen or attack.
3. `enemy` is only assigned inside `if action in ("1", "2")`, but referenced
   unconditionally afterward — flagged by Pyright as an `UnboundLocalError`/
   possibly-unbound bug. **Correction (2026-08-04, verified by tracing the
   actual control flow):** this is a Pyright false positive, not a real
   runtime bug — the `elif`/`continue` guards in the original file are
   exhaustive, so no code path ever reaches the fight loop with `enemy`
   unassigned. This was validated via the Pyright diagnostic alone, never by
   an actual reproduction. Kept in the list for historical accuracy (models
   were scored against "fixing" it in earlier rounds), but don't treat it as
   a required fix going forward.
4. Choosing "Heal" still spawns an enemy and enters the fight loop even though
   the heal branch never damages it — an infinite unproductive loop.
   **Fixed directly in `game_py_bugfix_original.py` on 2026-08-04** (not left
   for models to find): after three separate rounds of testing (Ornith v1-v3,
   `qwen3-coder:30b` v3), no model ever solved this one — it's a design-
   comprehension gap (restructuring `main()` so only Attack triggers combat),
   not a tooling/verification gap, so further blind retries weren't expected
   to converge. Choosing "2" now heals and returns straight to the main loop,
   no enemy, no fight loop. See `DESIGN.md` for
   the full rationale and the retest this enabled. Bugs 1, 2, 3 (false
   positive), and 5 are untouched and still present in the original fixture.

**`game_py_bugfix_original.py`** — the exact buggy starting file, byte-for-byte
reconstructed from the real incident transcript. Use this as the reset point
before each model attempt.

**`game_py_bugfix_reference_solution.py`** — a verified-working fix (all 4 bugs
fixed, confirmed via full live playthroughs covering every menu action, not
just lint). Use this to diff a model's attempt against a known-correct answer,
or as a target for automated pass/fail checks.

### How to use for a fresh model test

```bash
mkdir -p /tmp/some_test_dir
cp benchmarks/game_py_bugfix_original.py /tmp/some_test_dir/game.py
# then run agent.py against /tmp/some_test_dir with a fix-the-bugs prompt
```

### `play_verify.py` — repeat-action playthrough harness (v3.0)

`benchmarks/play_verify.py` is a scripted playthrough that exercises **every menu
action (Attack, Heal, Use Item, Go Deeper, Info) at least 3 times** and classifies
the outcome honestly, so model fixes can be scored without hand-piping stdin:

- **TIMEOUT** → likely infinite loop (this is how the Heal-enters-combat bug, bug 4,
  manifests) — a FAIL.
- **CRASH** → any traceback whose final exception is *not* `EOFError` — a FAIL.
- **OK (input exhausted)** → the game asked for more input than the script provided.
  This game has no "quit" (it only ends on death), so running out of input is the
  **expected, benign** end — *not* a failure. This deliberately neutralizes the
  `EOFError`-from-exhausted-pipe artifact that twice hijacked the v2.9.24 search-web
  nudge during model tests (see `DESIGN.md` §3).
- **OK (clean exit)** → the game ended on its own (player death / game over).

A run PASSES only if there's no crash, no hang, and all five actions ran ≥3×.

```bash
# Self-check against the known-good reference (should PASS, exit 0):
python3 benchmarks/play_verify.py

# Score a model's attempt (any game.py), optionally with a custom hang timeout:
python3 benchmarks/play_verify.py /tmp/some_test_dir/game.py --timeout 20
```

Tell models to run `play_verify.py` for verification instead of hand-piping stdin.
Verified 2026-08-05: the reference solution PASSES (all actions ≥3×), the original
buggy file FAILS (crashes on the missing `alive` key, bug 1).

### Known results (2026-08-03, all models tested against the original file)

| Model | Result |
|---|---|
| Ornith-1.0-9B | Introduced a new crash (renamed one dict's keys but not the `roles` dict) |
| `Agen/gemma-4-26B-A4B-it-uncensored-heretic` | First pass: got furthest (3/4 bugs fixed) but missed the `defense`-key issue (see below). Retested later: corrupted the file via a truncated `write_file` (155 lines deleted), repeated 8× without detecting it |
| `gpt-oss:20b` | First pass: fixed the fewest, introduced a second new crash. Retested: made zero net changes to the file but falsely claimed the alive-key bug was fixed |
| `qwen3-coder:30b` | Diagnosed correctly but never applied any fix at all |
| `qwen3.5:4b` | Only model to use real execution (`run_command`) for verification unprompted; still missed most bugs (function-level testing, not whole-program). Retested with syntax-check safety net: caught its own broken edits and kept iterating (real improvement) but still hit the round limit before finishing |

A 5th bug — enemies returned by `encounter()` never have a `"defense"` key,
crashing `player_attack(player, enemy)` on the first attack — was present in
the original file but not part of the original 4-bug list above; it was only
found by directly running the game, and neither of the two models that got
furthest (26B, gpt-oss) ever caught it despite both doing substantial,
careful-looking work elsewhere in the file.

### Retest (2026-08-04) after 4 systemic agent-side fixes — v2.9.21 through v2.9.24

Full research + fix + retest cycle documented in `DESIGN.md`,
section "7 quindecies". Four fixes shipped to `agent.py`, each independently
verified with a deterministic test before being trusted: automatic retry on a
confirmed Ollama tool-parser bug (`ollama/ollama#16988`), a `search_in_files`
regex fix (it silently treated `|` as a literal character instead of
alternation), a post-`edit_file` check that warns when a key rename looks
incomplete, and a nudge toward `search_web` when the same verification
failure recurs after an edit.

Retested with the decomposed ("one bug at a time, guided by real execution")
prompt — see the full analysis in `DESIGN.md`:

| Model | Result |
|---|---|
| `Ornith-1.0-9B` (v3) | Bugs 1, 2, 5 fixed — 2 is a **fully consistent** rename this time (the rename-consistency nudge fired twice and the model visibly responded to it). Bug 4 (Heal enters combat) still produces a genuine infinite loop, confirmed by scripted playthrough. |
| `qwen3-coder:30b` (v3) | Bugs 1, 2 (worked around, not renamed), 5 fixed. Bug 4 still an infinite loop, identical failure mode, reproduced independently. Bonus: implemented action "4" (Go Deeper), which the original file never actually handled at all. |

**No model has yet produced a fully working fix in one sitting** — but the
gap narrowed concretely: bugs 1, 2, and 5 are now reliably reachable (5 in
particular had never been caught by any model before this retest). What
remains is bug 4, and it's a different *kind* of gap than the others — not
insufficient execution (both models ran the game repeatedly), but a design-
comprehension gap: the reference fix requires restructuring `main()` so only
Attack triggers combat, and neither model questioned the existing (flawed)
structure enough to arrive at that on its own. Both also only tried Heal
once or twice during their own verification, when the 0-damage symptom only
becomes visible after several repeats — a scaffolding fix (repeat each
action multiple times during verification) is the untried lever here, not
another agent-side tooling fix. See `DESIGN.md` for the full
narrative.

### Targeted retest of the 4th fix (search-web nudge, v2.9.24) — 2026-08-04

Full detail in `DESIGN.md` §3. Sequential runs
only (never two models loaded at once — VRAM contention on this 24 GB
machine makes concurrent runs slower than sequential, not faster).

| Model | Result |
|---|---|
| `Ornith-1.0-9B` (3 attempts) | Attempt 1 cut short by the Ollama parser bug — but this time **handled cleanly by v2.9.21** (2 retries, then a clear message) instead of crashing the session, first real-world confirmation of that fix working. Attempt 2 derailed by an unrelated new finding: the model consistently mistyped the long scratchpad path (`mounirekknaci` instead of `mounirmeknaci`) across most of its tool calls, burning nearly all 25 rounds on "file not found" before ever touching the bugs — worked around by retesting with a short path. Attempt 3 (clean): bugs 1, 2, 5 fixed; action "4" implemented but now prints "Unknown action" right after succeeding (new cosmetic regression); bug 4 still an infinite loop (3rd confirmed reproduction across this whole investigation). |
| `qwen3.5:4b` | **Regressed to a syntactically broken file** — worse than the starting bug. Tried an unforced refactor of `choose_character`, broke syntax, got caught by the existing v2.9.20 check, self-corrected successfully — then retried the same risky refactor unprompted, broke it again identically, and this time a **second, different Ollama tool-parser bug** (`XML syntax error... element <parameter> closed by </function>`, matching `ollama/ollama#14834`/`#16383` found in the original research but never covered by a fix) ended the session before the break could be corrected. |

**Search-web nudge (v2.9.24) fired twice** — once per model — and worked
exactly as designed (only triggers on a genuinely repeated failure). But both
times, the repeated failure was an `EOFError` from the model's own piped test
input running out, not a real code bug. Both models correctly recognized
this themselves but never called `search_web` and never fixed their own test
methodology. Not a failure of the mechanism — it just hasn't yet been
observed catching the case it was actually built for (a real, recurring
logic bug).

**Follow-up identified, not yet implemented**: extend the v2.9.21 retry
pattern to also cover the XML tool-call parsing error found on `qwen3.5:4b`
— same shape of fix (retry, then clean fallback), different root cause
(malformed tool-call XML from the model, not Ollama's internal parser
generation) and different error signature, so the existing `except` clause
doesn't catch it.
