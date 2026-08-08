#!/usr/bin/env bash
# Run every deterministic test, each in its OWN process (required, see README.md).
# From the project root:  bash tests/run_all.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
pass=0; fail=0; failed=""
if command -v sha256sum >/dev/null 2>&1; then   CKSUM="sha256sum"
elif command -v shasum      >/dev/null 2>&1; then CKSUM="shasum -a 256"
else                                              CKSUM="cksum"
fi
home_snapshot() { for f in "$HOME"/.agentic_1a_params.json "$HOME"/.agentic_1a_history \
                           "$HOME"/.agentic_1a_models.json "$HOME"/.agentic_1a_default_model.txt \
                           "$HOME"/.agentic_1a_mcp.json; do
                      [ -e "$f" ] && $CKSUM "$f" 2>/dev/null
                  done; }
HOME_BEFORE="$(home_snapshot)"
for t in "$ROOT"/tests/test_*.py; do
    # test_scripts.py is the pytest runner for everything else. Executed directly it
    # defines functions and exits 0 without asserting anything, which would be counted
    # here as a pass that tested nothing.
    [ "$(basename "$t")" = "test_scripts.py" ] && continue
    # stdin closed: a test that accidentally reaches the real _prompt() should FAIL fast,
    # not block forever waiting for input (test_ctrlc did exactly that once).
    if PYTHONPATH="$ROOT" "$PY" "$t" >/dev/null 2>&1 </dev/null; then
        pass=$((pass+1))
    else
        fail=$((fail+1)); failed="$failed $(basename "$t")"
    fi
done
# The suite must never touch your real config. This is enforced here rather than inside a
# test because each test runs in its own process and cannot police the others. It is not
# hypothetical: test_structure's /parameters round-trip once rewrote the live
# ~/.agentic_1a_params.json, bumping every setting one step (GEN_NUM_PREDICT -1 -> 127,
# which silently truncates every answer), green suite, corrupted settings.
if [ "$HOME_BEFORE" != "$(home_snapshot)" ]; then
    echo "FAILED: the suite modified your real ~/.agentic_1a_* config"
    fail=$((fail+1))
fi

echo "tests: $pass passed, $fail failed"
[ -n "$failed" ] && echo "FAILED:$failed"
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
