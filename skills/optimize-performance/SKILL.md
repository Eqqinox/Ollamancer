---
name: optimize-performance
description: Make code faster by measuring first, then applying the single highest-impact fix and proving the speedup. Use when the user says something is slow, asks to optimize/speed up code, or to improve performance.
license: MIT
---

# Optimize performance

Measure, don't guess. One real bottleneck fixed beats ten speculative micro-optimizations.

## Steps

1. **Reproduce the slowness** with a concrete workload. Ask for (or construct) a representative
   input that actually shows the problem. If you can't reproduce it, say so — don't optimize blind.
2. **Profile to find the hotspot** — the code spends most of its time in a few places:
   - Python: `python_repl` / `run_command` with `cProfile` (`python -m cProfile -s cumtime script.py`)
     or `timeit` for a small function. Read the top cumulative-time entries.
   - Other langs / commands: time the run (`/usr/bin/time -l`), or add coarse timers.
   Identify the **one** function/line/query dominating the time.
3. **Understand why it's slow** before touching it: an O(n²) loop, repeated I/O, a query in a
   loop (N+1), recomputing the same thing, an unbounded data structure. `read_file_lines` it.
4. **Apply the highest-impact fix** with `edit_file`: better algorithm/data structure, caching/
   memoization, batching I/O, hoisting invariant work out of a loop, a proper index. Prefer the
   change that removes the bottleneck class, not a constant-factor tweak.
5. **Prove it.** Re-run the exact same workload from step 1 and report **before → after** numbers
   (e.g. "2.3s → 0.4s"). If it's not actually faster, revert and reconsider.
6. **Confirm correctness** — run the tests (or `test-and-fix`); a faster wrong answer is worthless.

## Notes

- Don't sacrifice readability for a tiny gain. Note the trade-off if you do.
- Stop after the biggest win unless the user asks for more — diminishing returns are real.
