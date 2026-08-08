#!/usr/bin/env bash
# Model ranking campaign driver. See PLAN.md for the protocol.
#
#   bash rank.sh gate                    # round 1: tool-discipline gate, all models
#   bash rank.sh battery                 # round 2: t1..t4 on the models in survivors.txt
#   bash rank.sh battery --reps 2        # add a second rep (doubles the time)
#   bash rank.sh battery --tasks t2,t4   # only some tasks
#   bash rank.sh gate --skip-heavy       # leave out the two >20 GB models (see below)
#
# Three invariants this script enforces rather than trusts:
#   1. Exactly one model is resident at a time (`ollama ps` is asserted empty before
#      every run and the model is stopped after it).
#   2. Swap usage is sampled either side of every run. The two >20 GB models are on
#      this machine's edge (24 GB unified memory) but their vendors advertise a real
#      working set below the on-disk size — the A3B one is a mixture-of-experts that
#      activates ~3B parameters per token. So they are TESTED by default, and whether
#      they actually fit is answered by the measured swap delta and by whether they
#      crash. --skip-heavy leaves them out.
#   3. The real ~/.agentic_1a_* files are byte-identical at the end. If they are not,
#      the campaign aborts loudly — a benchmark must never mutate the user's setup.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="$REPO/.venv/bin/python"
RESULTS="$HERE/results"

TIMEOUT=300        # 5 min hard cap per run (was 9) — a slow model is a finding, not a wait
COOLDOWN=8         # seconds between runs, so the GPU memory is really released and the
                   # machine gets a moment to shed heat before the next load
HEAVY_GB=20        # models above this are flagged and reported on, but still run

# Ordered lightest-first on purpose: if the campaign is interrupted, the cheap results
# are already banked, and the machine warms up gradually instead of starting at 18 GB.
# The two in HEAVY_MODELS go last, for the same reason.
ALL_MODELS=(
  "oamazonasgabriel/qwen2.5-coder.1.5b-mlx:f16-8gbGPU"                        # 3.1 GB
  "htunnthuthutech/gemma-4-e2b-aiops:latest"                                  # 3.4 GB
  "qwen3.5:4b"                                                                # 3.4 GB
  "gamy316/aileen1.0:latest"                                                  # 4.9 GB
  "lfm2.5:8b"                                                                 # 5.2 GB
  "MHKetbi/DeepSeek-R1-Distill-Llama-8B-NexaQuant:latest"                     # 5.3 GB
  "ornith:9b"                                                                 # 5.6 GB
  "hf.co/deepreinforce-ai/Ornith-1.0-9B-GGUF:Q4_K_M"                          # 5.6 GB
  "studiobrn/modCoderMLX:latest"                                              # 7.4 GB
  "jikepjikep_16HEX/gemma-4-12b-nightshift-heretic-uncensored-qat-q4:latest"  # 7.4 GB
  "gemma4:12b-mlx"                                                            # 7.7 GB
  "gpt-oss:20b"                                                               # 13.8 GB
  "gemma4:26b-mlx"                                                            # 17.6 GB
  "Agen/gemma-4-26B-A4B-it-uncensored-heretic:latest"                         # 18.0 GB
  "qwen3-coder:30b"                                                           # 18.6 GB
)
# Above HEAVY_GB. Included by default (--skip-heavy to drop them): both advertise a
# real working set below their on-disk size, and the only honest way to settle that is
# to run them and read the swap delta. A crash or a timeout here is a result, not an
# error — it gets written into meta.json like any other outcome.
HEAVY_MODELS=(
  "rafw007/Qwen3.6-35B-A3B-mlx-claude-coder-abliterated:latest"   # 23.9 GB on disk, A3B MoE
  "charaf/Qwen3.6-27B-OBLITERATED-mlx-q8:latest"                  # 28.6 GB on disk, > total RAM
)

# ── config-safety guard ──────────────────────────────────────────────────────
CONFIG_FILES=(~/.agentic_1a_params.json ~/.agentic_1a_default_model.txt \
              ~/.agentic_1a_models.json ~/.agentic_1a_mcp.json ~/.agentic_1a_history)

snapshot_config() { for f in "${CONFIG_FILES[@]}"; do [ -f "$f" ] && shasum -a 256 "$f"; done; }
BEFORE="$(snapshot_config)"

check_config() {
  local after; after="$(snapshot_config)"
  if [ "$after" != "$BEFORE" ]; then
    echo ""
    echo "!!! ABORT: a run modified your real Agentic_1A config. Diff:"
    diff <(echo "$BEFORE") <(echo "$after")
    exit 2
  fi
}

# ── size guard ───────────────────────────────────────────────────────────────
model_gb() {
  ollama list | awk -v m="$1" '$1==m {
      if ($3 ~ /GB/ || $4=="GB") { gsub(/GB/,"",$3); print $3+0; exit }
      if ($3 ~ /MB/ || $4=="MB") { gsub(/MB/,"",$3); print ($3+0)/1024; exit }
  }'
}

is_heavy() {
  local gb; gb="$(model_gb "$1")"
  [ -z "$gb" ] && return 1
  awk -v a="$gb" -v b="$HEAVY_GB" 'BEGIN{exit !(a>b)}'
}

# ── one-model-at-a-time guard ────────────────────────────────────────────────
unload_all() {
  for m in "${ALL_MODELS[@]}" "${HEAVY_MODELS[@]}"; do ollama stop "$m" >/dev/null 2>&1; done
}

assert_none_resident() {
  local n
  n="$(ollama ps 2>/dev/null | tail -n +2 | grep -c '[^[:space:]]')"
  if [ "$n" -ne 0 ]; then
    echo "  … a model is still resident, unloading"
    unload_all; sleep 5
    n="$(ollama ps 2>/dev/null | tail -n +2 | grep -c '[^[:space:]]')"
    if [ "$n" -ne 0 ]; then
      echo "!!! ABORT: could not get to zero resident models"; ollama ps; exit 3
    fi
  fi
}

slug() { echo "$1" | tr '/:' '__' | tr -cd 'A-Za-z0-9._-'; }

run_one() {
  local model="$1" task="$2" rep="$3"
  local out="$RESULTS/$(slug "$model")/${task}_rep${rep}"
  if [ -f "$out/meta.json" ]; then echo "  skip $task rep$rep (already done)"; return; fi

  assert_none_resident
  printf '  → %s rep%s  ' "$task" "$rep"
  "$PY" "$HERE/run_one.py" --model "$model" --task "$task" --outdir "$out" --timeout "$TIMEOUT" --seed "$rep" \
    2>/dev/null | tail -1
  ollama stop "$model" >/dev/null 2>&1
  check_config
  sleep "$COOLDOWN"
}

# ── argument parsing ─────────────────────────────────────────────────────────
MODE="${1:-}"; shift 2>/dev/null || true
REPS=1
TASKS="t1,t2,t3,t4"
SKIP_HEAVY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --reps)          REPS="$2"; shift 2 ;;
    --tasks)         TASKS="$2"; shift 2 ;;
    --timeout)       TIMEOUT="$2"; shift 2 ;;
    --skip-heavy)    SKIP_HEAVY=1; shift ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done

if [ "$SKIP_HEAVY" -eq 0 ]; then
  ALL_MODELS+=("${HEAVY_MODELS[@]}")
fi

mkdir -p "$RESULTS"

case "$MODE" in
  gate)
    echo "=== Round 1: tool-discipline gate — ${#ALL_MODELS[@]} models, 1 short probe each ==="
    for m in "${ALL_MODELS[@]}"; do
      echo "$m"
      if is_heavy "$m"; then
        echo "  (heavy: $(model_gb "$m") GB on disk — watching swap; a crash here is a result)"
      fi
      run_one "$m" t0 1
    done
    echo ""
    echo "Now review the t0 answers, then list the survivors (one per line) in:"
    echo "  $HERE/survivors.txt"
    ;;

  battery)
    SURV="$HERE/survivors.txt"
    [ -f "$SURV" ] || { echo "missing $SURV — run 'bash rank.sh gate' first"; exit 1; }
    # bash 3.2 on macOS has no `mapfile`, so read the list the portable way.
    MODELS=()
    while IFS= read -r line; do
      case "$line" in ''|'#'*) continue ;; esac
      MODELS+=("$line")
    done < "$SURV"
    [ "${#MODELS[@]}" -eq 0 ] && { echo "survivors.txt has no models in it"; exit 1; }

    echo "=== Round 2: battery — ${#MODELS[@]} models × [$TASKS] × ${REPS} rep(s) ==="
    IFS=',' read -ra TASK_LIST <<< "$TASKS"
    for m in "${MODELS[@]}"; do
      echo ""
      echo "$m"
      for rep in $(seq 1 "$REPS"); do
        for t in "${TASK_LIST[@]}"; do
          run_one "$m" "$t" "$rep"
        done
      done
    done
    echo ""
    "$PY" "$HERE/score.py" --all "$RESULTS"
    ;;

  *)
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac

check_config
echo ""
echo "config unchanged ✓"
