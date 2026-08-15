#!/usr/bin/env bash
# A/B: what do the two post-answer honesty checks cost?
#
#   bash ab_honesty.sh              # run it (resumable — re-run to continue)
#   bash ab_honesty.sh --dry-run    # print the plan and the time estimate, run nothing
#
# The question. `_grounding_check` and `_claim_without_action` are argued for from origin
# anecdotes (a "fixed" file that was bit-for-bit identical, four models "verified" after a
# clean lint) and have never been measured. Every nudge is a full extra generation, and
# `_grounding_check` false-positives on derived values by construction — a percentage computed
# from two fetched numbers appears in no tool result. So the layer has a cost and nobody has
# counted it. Two arms, everything else identical:
#
#   on   the shipped defaults
#   off  MAX_GROUNDING_CHECK_NUDGES=0 MAX_CLAIM_ACTION_NUDGES=0
#
# Why these tasks. t2 (websearch) and t4 (report) only. t1 makes zero tool calls in all 33
# banked runs, and `_grounding_check` is gated on `turn_tool_results`, so it cannot fire there
# — nothing to measure. t3 is excluded for the opposite reason: 22 of its 33 banked runs hit
# the 300 s cap, so it would compare the arms on "did it finish", and since a nudge *is* an
# extra generation the on-arm would lose on timeouts alone. That would look like a quality
# difference and would not be one.
#
# Which is also why T4_TIMEOUT is 480 and not the campaign's 300: 21 of 33 banked t4 runs hit
# the cap, so t4's banked median *is* the cap. Raising it lets the arms be compared on the
# answer rather than on the clock. It does not make the numbers comparable to the campaign's
# t4 — they are a different measurement and live in a different directory.
#
# WHAT IT FOUND, 2026-08-15, so nobody assumes a conclusion it did not reach.
#
#   * `_grounding_check` fired ZERO times in all 48 on-arm runs. The layer under test never
#     engaged, so this run says nothing about it. Its sensitivity had to be established another
#     way — see tests/test_grounding_sensitivity.py and RESULTS.md §2.
#   * `_claim_without_action` fired 6 times in 48.
#   * Completion: 37/48 answered on-arm vs 35/48 off. McNemar on the 10 discordant pairs gives
#     p = 0.75. No detectable effect on whether you get an answer.
#   * Among the 31 pairs where both arms answered, the on-arm was slower by a median of 31 s
#     (22 of 31 pairs, sign test p = 0.029). That is NOT attributable to the two checks: six
#     firings cannot produce a consistent slowdown across 22 pairs. It is confounded with arm
#     order, since `on` always runs first in a cell and eats the cold-model load.
#
# So the honest reading is: no measured cost to answer completion, one of the two checks never
# fired, and the timing difference is unattributable. A conclusive version needs arm order
# counterbalanced and a task where the grounding check actually triggers.
#
# What this does NOT touch: results/. The campaign's 168 banked runs are read by nothing here.
# Note `run_one.py` rmtree's its own --outdir, so the skip-if-done guard below is load-bearing
# rather than an optimisation, exactly as in rank.sh.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="$REPO/.venv/bin/python"
RESULTS="$HERE/results_ab"          # NOT results/ — the campaign is not touched

T2_TIMEOUT=300
T4_TIMEOUT=480
COOLDOWN=8
REPS=2

# Hard wall-clock budget, enforced rather than estimated: no new run is started if its own cap
# could carry it past the deadline, so the bound holds even if every remaining run times out.
# Worst case for the 96 planned runs is 10.6 h (48×300 s + 48×480 s + cooldowns), so at 11 h
# every cell is guaranteed to be attempted; the expected time is ~6.5 h. Stopping early is safe
# regardless — every completed run is banked and re-running resumes where it stopped.
BUDGET_HOURS=11

# The 12 roster models that are actually installed. survivors.txt lists 15; gamy316/aileen1.0,
# lfm2.5:8b and ornith:9b are no longer in `ollama list` and are omitted rather than pulled.
MODELS=(
  "qwen3.5:4b"                                                                # 3.4 GB
  "qwen3.5:4b-mlx"                                                            # 4.0 GB
  "hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M"                          # 5.6 GB
  "qwen-heretic:latest"                                                       # 7.0 GB
  "jikepjikep_16HEX/gemma-4-12b-nightshift-heretic-uncensored-qat-q4:latest"  # 7.4 GB
  "gemma4:12b-mlx"                                                            # 7.7 GB
  "qwen3.5:9b-mlx"                                                            # 8.9 GB
  "hf.co/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive:IQ2_M"       # 12.0 GB
  "gpt-oss:20b"                                                               # 13.8 GB
  "hf.co/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive:IQ3_M"       # 16.0 GB
  "gemma4:26b-mlx"                                                            # 17.6 GB
  "Agen/gemma-4-26B-A4B-it-uncensored-heretic:latest"                         # 18.0 GB
)

OFF_PARAMS=(--param MAX_GROUNDING_CHECK_NUDGES=0 --param MAX_CLAIM_ACTION_NUDGES=0)

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

# ── config-safety guard, same contract as rank.sh ────────────────────────────
CONFIG_FILES=(~/.agentic_1a_params.json ~/.agentic_1a_default_model.txt \
              ~/.agentic_1a_models.json ~/.agentic_1a_mcp.json ~/.agentic_1a_history)
snapshot_config() { for f in "${CONFIG_FILES[@]}"; do [ -f "$f" ] && shasum -a 256 "$f"; done; }
BEFORE="$(snapshot_config)"
check_config() {
  local after; after="$(snapshot_config)"
  if [ "$after" != "$BEFORE" ]; then
    echo ""; echo "!!! ABORT: a run modified your real Ollamancer config. Diff:"
    diff <(echo "$BEFORE") <(echo "$after"); exit 2
  fi
}

# `local` is load-bearing: without it this loop variable is the same global as the driver
# loop's, and unload_all is called from inside it. Observed — one resident model tripped
# assert_none_resident, unload_all left the global at the LAST array element, and the next six
# cells ran as that model instead of the intended one. They were filed correctly (run_one.py
# derives outdir and meta.json from the same variable, so nothing was mislabelled) and then
# skipped as already-done when the loop reached them, so the symptom was a model silently
# ending up with zero runs rather than any corrupt data. rank.sh:101 has the same shape.
unload_all() { local m; for m in "${MODELS[@]}"; do ollama stop "$m" >/dev/null 2>&1; done; }

assert_none_resident() {
  local n
  n="$(ollama ps 2>/dev/null | tail -n +2 | grep -c '[^[:space:]]')"
  if [ "$n" -ne 0 ]; then
    echo "  … a model is still resident, unloading"
    unload_all; sleep 5
    n="$(ollama ps 2>/dev/null | tail -n +2 | grep -c '[^[:space:]]')"
    [ "$n" -ne 0 ] && { echo "!!! ABORT: could not get to zero resident models"; ollama ps; exit 3; }
  fi
}

slug() { echo "$1" | tr '/:' '__' | tr -cd 'A-Za-z0-9._-'; }

START="$(date +%s)"
DEADLINE=$(( START + BUDGET_HOURS * 3600 ))
DONE=0; SKIPPED=0; STOPPED=0

run_cell() {
  local model="$1" task="$2" rep="$3" arm="$4" timeout="$5"
  local out="$RESULTS/$(slug "$model")/${task}_rep${rep}_${arm}"

  if [ -f "$out/meta.json" ]; then
    SKIPPED=$((SKIPPED+1)); echo "    skip  $task rep$rep $arm (already done)"; return
  fi
  # Never start a run that could cross the deadline. Checked against the run's own cap, so
  # the bound holds even if every remaining run times out.
  local now; now="$(date +%s)"
  if [ $(( now + timeout + COOLDOWN )) -gt "$DEADLINE" ]; then
    STOPPED=1; return
  fi
  if [ "$DRY" -eq 1 ]; then echo "    plan  $task rep$rep $arm (cap ${timeout}s)"; DONE=$((DONE+1)); return; fi

  assert_none_resident
  printf '    → %-3s rep%s %-3s  ' "$task" "$rep" "$arm"
  if [ "$arm" = "off" ]; then
    "$PY" "$HERE/run_one.py" --model "$model" --task "$task" --outdir "$out" \
        --timeout "$timeout" --seed "$rep" "${OFF_PARAMS[@]}" 2>/dev/null | tail -1
  else
    "$PY" "$HERE/run_one.py" --model "$model" --task "$task" --outdir "$out" \
        --timeout "$timeout" --seed "$rep" 2>/dev/null | tail -1
  fi
  ollama stop "$model" >/dev/null 2>&1
  check_config
  DONE=$((DONE+1))
  sleep "$COOLDOWN"
}

mkdir -p "$RESULTS"
echo "=== A/B: honesty-layer cost — ${#MODELS[@]} models × [t2,t4] × ${REPS} reps × 2 arms ==="
echo "    arm on  = shipped defaults"
echo "    arm off = MAX_GROUNDING_CHECK_NUDGES=0 MAX_CLAIM_ACTION_NUDGES=0"
echo "    budget  = ${BUDGET_HOURS} h hard stop; results → $RESULTS"
echo ""

# Ordering matters: the two arms of a cell run back to back, so any prefix of this run is a
# balanced sample. If the budget stops the run early, what is banked is still analysable
# rather than being all-on and no-off.
for m in "${MODELS[@]}"; do
  [ "$STOPPED" -eq 1 ] && break
  echo "$m"
  for rep in $(seq 1 "$REPS"); do
    for spec in "t2:$T2_TIMEOUT" "t4:$T4_TIMEOUT"; do
      t="${spec%%:*}"; to="${spec##*:}"
      for arm in on off; do
        [ "$STOPPED" -eq 1 ] && break
        run_cell "$m" "$t" "$rep" "$arm" "$to"
      done
    done
  done
done

ELAPSED=$(( $(date +%s) - START ))
echo ""
printf 'ran %d, skipped %d, elapsed %dh%02dm\n' "$DONE" "$SKIPPED" $((ELAPSED/3600)) $(((ELAPSED%3600)/60))
[ "$STOPPED" -eq 1 ] && echo "STOPPED on the ${BUDGET_HOURS}h budget before finishing — re-run to resume."
check_config
echo "config unchanged ✓"
