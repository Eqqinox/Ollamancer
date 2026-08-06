#!/usr/bin/env bash
# Run every deterministic test, each in its OWN process (required — see README.md).
# From the project root:  bash tests/run_all.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
pass=0; fail=0; failed=""
home_snapshot() { for f in "$HOME"/.agentic_1a_params.json "$HOME"/.agentic_1a_history \
                           "$HOME"/.agentic_1a_models.json "$HOME"/.agentic_1a_default_model.txt \
                           "$HOME"/.agentic_1a_mcp.json; do
                      [ -e "$f" ] && shasum "$f" 2>/dev/null
                  done; }
HOME_BEFORE="$(home_snapshot)"
for t in "$ROOT"/tests/test_*.py; do
    if PYTHONPATH="$ROOT" "$PY" "$t" >/dev/null 2>&1; then
        pass=$((pass+1))
    else
        fail=$((fail+1)); failed="$failed $(basename "$t")"
    fi
done
# The suite must never touch your real config. This is enforced here rather than inside a
# test because each test runs in its own process and cannot police the others. It is not
# hypothetical: test_structure's /parameters round-trip once rewrote the live
# ~/.agentic_1a_params.json, bumping every setting one step (GEN_NUM_PREDICT -1 -> 127,
# which silently truncates every answer) — green suite, corrupted settings.
home_snapshot() { for f in "$HOME"/.agentic_1a_params.json "$HOME"/.agentic_1a_history \
                        "$HOME"/.agentic_1a_models.json "$HOME"/.agentic_1a_default_model.txt \
                        "$HOME"/.agentic_1a_mcp.json; do
                   [ -e "$f" ] && shasum "$f" 2>/dev/null
               done; }
if [ "$HOME_BEFORE" != "$(home_snapshot)" ]; then
    echo "FAILED: the suite modified your real ~/.agentic_1a_* config"
    fail=$((fail+1))
fi

echo "tests: $pass passed, $fail failed"
[ -n "$failed" ] && echo "FAILED:$failed"
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
