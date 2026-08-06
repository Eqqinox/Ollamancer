#!/usr/bin/env bash
# Run every deterministic test, each in its OWN process (required — see README.md).
# From the project root:  bash tests/run_all.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
pass=0; fail=0; failed=""
for t in "$ROOT"/tests/test_*.py; do
    if PYTHONPATH="$ROOT" "$PY" "$t" >/dev/null 2>&1; then
        pass=$((pass+1))
    else
        fail=$((fail+1)); failed="$failed $(basename "$t")"
    fi
done
echo "tests: $pass passed, $fail failed"
[ -n "$failed" ] && echo "FAILED:$failed"
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
