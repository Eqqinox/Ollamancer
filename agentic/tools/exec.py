"""Agentic_1A — execution: linting, tests, shell, REPL and background processes.

Everything that runs code. All of it passes through the same two gates in `agentic/safety.py`:
`_check_command` (destructive-pattern blocklist) and `_run_shell` (host or Docker sandbox,
fail-closed).

**`lint_file` is deliberately not treated as proof.** A clean lint says nothing about logic —
a missing dict key or an unreachable branch passes it happily. Measured directly: in a
four-model comparison on a real bug, every model that attempted a fix declared itself
"verified" after a clean lint, and every one shipped a guaranteed crash. That is why
`run_command` counts as real verification alongside `run_tests`, and why the self-check nudge
pushes toward actually executing the code.

**`python_repl` is a persistent subprocess**, so variables and imports survive between calls —
the point is incremental work (load a CSV once, then explore it) rather than re-running setup
every time. A sentinel protocol frames each execution: send code, send an EXEC marker, read
until the DONE marker, echoing the last expression the way a real REPL does.

**Background processes** exist because `run_command` blocks with a 30s timeout, which is
useless for a dev server or a watcher. Output is redirected to `.agentic/bg_logs/`, and every
process still alive at session end is killed — no orphan server outliving the agent.
"""

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from agentic import config, state, ui
from agentic.i18n import t
from agentic.safety import (
    _audit, _check_command, _check_file_path, _ensure_sandbox_container, _run_shell)
from agentic.tools.files import _closest_path_hint

# Linters tried in order per extension; first one found on PATH wins.
# --no-install on npx prevents an unexpected network install if eslint isn't a local devDependency.
_LINTERS = {
    ".py":  [("ruff", ["ruff", "check", "--quiet"]), ("flake8", ["flake8"])],
    ".js":  [("eslint", ["npx", "--no-install", "eslint"])],
    ".jsx": [("eslint", ["npx", "--no-install", "eslint"])],
    ".ts":  [("eslint", ["npx", "--no-install", "eslint"])],
    ".tsx": [("eslint", ["npx", "--no-install", "eslint"])],
    ".go":  [("go vet", ["go", "vet"])],
}


def lint_file(path: str) -> str:
    """Run a fast static-analysis/lint check on a single file (auto-detects the right
    linter for its language: ruff/flake8 for Python, eslint for JS/TS, go vet for Go).
    Much cheaper than run_tests — call this right after editing a file, before running
    the full test suite.
    Args:
        path: File to check
    """
    safe, reason = _check_file_path(path)
    if not safe:
        return f"⛔ Blocked: {reason}"
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}{_closest_path_hint(path)}"

    for name, cmd in _LINTERS.get(p.suffix.lower(), []):
        if shutil.which(cmd[0]) is None:
            continue
        try:
            result = subprocess.run(cmd + [str(p)], capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return f"⏱ Timeout running {name}."
        except Exception as e:
            return f"Error running {name}: {e}"
        output = (result.stdout + result.stderr).strip()
        # npx with --no-install fails this way when the linter isn't a local devDependency —
        # that's "not available", not a real lint finding. Try the next candidate instead.
        if cmd[0] == "npx" and "canceled due to missing packages" in output:
            continue
        status = "✅ CLEAN" if result.returncode == 0 else "⚠️ ISSUES"
        return f"{status} ({name}, exit {result.returncode})\n\n{output[:2000] or '(no output)'}"

    if p.suffix.lower() == ".py":
        # Always available: syntax check alone if no linter is installed.
        result = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return "✅ CLEAN (syntax only — no linter installed, ran py_compile)"
        return f"⚠️ SYNTAX ERROR\n\n{result.stderr.strip()[:2000]}"

    return f"No linter available for '{p.suffix}' files on this system."


def run_tests(command: str) -> str:
    """Run a test suite and return results with success/failure status.
    Args:
        command: Test command (e.g. pytest, npm test, go test ./..., cargo test)
    """
    safe, reason = _check_command(command)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        output, returncode = _run_shell(command, timeout=120)
        status = "✅ SUCCESS" if returncode == 0 else "❌ FAILED"
        return f"{status} (exit: {returncode})\n\n{output[:3000]}"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout: tests > 120 seconds."
    except RuntimeError as e:
        return f"⛔ {e} — tests NOT run. Use /sandbox to disable, or fix Docker."
    except Exception as e:
        return f"Error: {e}"


def run_command(command: str) -> str:
    """Run a shell command from the project root.
    Args:
        command: Full shell command (git, npm, pip, ls, curl, etc.)
    """
    safe, reason = _check_command(command)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        output, _ = _run_shell(command, timeout=30)
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Timeout (>30s)"
    except RuntimeError as e:
        return f"⛔ {e} — command NOT run. Use /sandbox to disable, or fix Docker."
    except Exception as e:
        return f"Error: {e}"


# ── Python REPL persistant (B7) ──────────────────────────────────────────────────
# A subprocess Python interpreter whose state (variables, imports) survives from one
# call to the next within the session. Same security gate as run_command: the
# _check_command filter on the code + Docker sandbox gating (the REPL runs in the container
# when SANDBOX_MODE is active) + SAFE_MODE approval (python_repl is in _RISKY_TOOLS).
# Driver protocol: we send the code then an EXEC sentinel line; the driver
# runs the block in a persistent namespace, captures stdout/stderr, echoes
# the last expression's value (REPL behaviour), then emits a DONE sentinel.
_REPL_EXEC = "<<<AGENTIC_EXEC_5f2a>>>"


_REPL_DONE = "<<<AGENTIC_DONE_5f2a>>>"


_REPL_DRIVER = '''
import sys, io, ast, traceback
_ns = {"__name__": "__main__"}
_buf = []
while True:
    _line = sys.stdin.readline()
    if not _line:
        break
    _line = _line.rstrip("\\n")
    if _line != "__EXEC__":
        _buf.append(_line); continue
    _code = "\\n".join(_buf); _buf = []
    _cap = io.StringIO(); _o, _e = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _cap
    try:
        _tree = ast.parse(_code)
        if _tree.body and isinstance(_tree.body[-1], ast.Expr):
            _last = _tree.body.pop()
            if _tree.body:
                exec(compile(_tree, "<repl>", "exec"), _ns)
            _val = eval(compile(ast.Expression(_last.value), "<repl>", "eval"), _ns)
            if _val is not None:
                print(repr(_val))
        else:
            exec(compile(_code, "<repl>", "exec"), _ns)
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout, sys.stderr = _o, _e
    _o.write(_cap.getvalue()); _o.write("\\n__DONE__\\n"); _o.flush()
'''.replace("__EXEC__", _REPL_EXEC).replace("__DONE__", _REPL_DONE)


def _repl_start():
    """(Re)start the persistent interpreter for the current sandbox mode."""
    _repl_stop()
    if state.SANDBOX_MODE:
        ok, container_or_err = _ensure_sandbox_container()
        if not ok:
            raise RuntimeError(f"Sandbox unavailable ({container_or_err})")
        argv = ["docker", "exec", "-i", container_or_err, "python3", "-u", "-c", _REPL_DRIVER]
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
    else:
        proc = subprocess.Popen([sys.executable, "-u", "-c", _REPL_DRIVER],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(state.PROJECT_ROOT) if state.PROJECT_ROOT else None)
    state._repl_state["proc"] = proc
    state._repl_state["mode"] = "sandbox" if state.SANDBOX_MODE else "host"
    return proc


def _repl_stop():
    proc = state._repl_state.get("proc")
    if proc is not None:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    state._repl_state["proc"] = None
    state._repl_state["mode"] = None


def _repl_read_until_done(proc, timeout: float) -> tuple[bool, str]:
    lines: list[str] = []
    done = threading.Event()

    def _reader():
        for raw in proc.stdout:
            if raw.rstrip("\n") == _REPL_DONE:
                done.set()
                return
            lines.append(raw.rstrip("\n"))
        done.set()  # the process is dead

    threading.Thread(target=_reader, daemon=True).start()
    finished = done.wait(timeout)
    return finished, "\n".join(lines)


def python_repl(code: str) -> str:
    """Run Python code in a persistent interpreter whose state (variables, imports, loaded
    data) survives across calls within this session — ideal for step-by-step data analysis
    (pandas/CSV), quick computation, or incremental debugging without re-running setup each
    time. The value of a final bare expression is echoed like a real REPL; otherwise use
    print(). Runs under the same safety gate as run_command (blocked destructive patterns,
    Docker sandbox when /sandbox is on, approval when /safe is on).
    Args:
        code: Python source to execute in the persistent session interpreter
    """
    safe, reason = _check_command(code)
    if not safe:
        return f"⛔ Blocked: {reason}"
    try:
        proc = state._repl_state.get("proc")
        want_mode = "sandbox" if state.SANDBOX_MODE else "host"
        if proc is None or proc.poll() is not None or state._repl_state.get("mode") != want_mode:
            proc = _repl_start()
    except RuntimeError as e:
        return f"⛔ {e} — REPL NOT started. Use /sandbox to disable, or fix Docker."
    except Exception as e:
        return f"REPL start error: {e}"
    try:
        proc.stdin.write(code + "\n" + _REPL_EXEC + "\n")
        proc.stdin.flush()
    except Exception as e:
        _repl_stop()
        return f"REPL write error: {e} (interpreter restarted; try again)."
    finished, output = _repl_read_until_done(proc, timeout=30)
    if not finished:
        _repl_stop()  # infinite loop / hang -> kill it and start clean on the next call
        return f"⏱ Timeout (>30s) — the interpreter was reset. Partial output:\n{output[:3000]}"
    return output[:5000] if output.strip() else "(no output)"


def run_background(command: str) -> str:
    """Start a long-running shell command in the background (e.g. a dev server or
    file watcher) and return immediately with a process id — unlike run_command,
    this never blocks or times out. Use check_process(id) to poll its output and
    kill_process(id) to stop it. Any process still running when the session ends
    is stopped automatically.
    Args:
        command: Full shell command to run in the background
    """
    safe, reason = _check_command(command)
    if not safe:
        return f"⛔ Blocked: {reason}"

    running = sum(1 for info in state._bg_processes.values() if info["proc"].poll() is None)
    if running >= config.MAX_BACKGROUND_PROCESSES:
        return f"Too many background processes running ({running}/{config.MAX_BACKGROUND_PROCESSES}). Stop one first with kill_process."

    state._bg_counter += 1
    pid_label = str(state._bg_counter)
    log_dir = state._BG_LOG_DIR if state._BG_LOG_DIR else Path.cwd()
    log_path = log_dir / f"bg_{pid_label}.log"
    try:
        log_file = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            command, shell=True, stdout=log_file, stderr=subprocess.STDOUT, preexec_fn=os.setsid,
        )
    except Exception as e:
        return f"Error starting background process: {e}"

    state._bg_processes[pid_label] = {
        "proc": proc, "command": command, "log_path": log_path,
        "log_file": log_file, "started_at": datetime.now().strftime("%H:%M:%S"),
    }
    _audit("RUN_BACKGROUND", {"id": pid_label, "command": command})
    return f"Started background process #{pid_label} (PID {proc.pid}): {command}\nUse check_process('{pid_label}') to see its output."


def check_process(process_id: str) -> str:
    """Check a background process's status and recent output.
    Args:
        process_id: The id returned by run_background (e.g. "1")
    """
    info = state._bg_processes.get(str(process_id))
    if not info:
        return f"No background process with id '{process_id}'. Use list_processes to see active ones."
    ret = info["proc"].poll()
    status = "running" if ret is None else ("exited 0 (success)" if ret == 0 else f"exited {ret} (failed)")
    try:
        output = info["log_path"].read_text(encoding="utf-8")[-2000:]
    except Exception:
        output = ""
    return f"#{process_id} [{status}] — {info['command']}\n\n{output or '(no output yet)'}"


def kill_process(process_id: str) -> str:
    """Stop a background process started with run_background.
    Args:
        process_id: The id returned by run_background (e.g. "1")
    """
    info = state._bg_processes.get(str(process_id))
    if not info:
        return f"No background process with id '{process_id}'."
    proc = info["proc"]
    ret = proc.poll()
    if ret is not None:
        return f"#{process_id} already exited (code {ret})."
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception as e:
        return f"Error stopping #{process_id}: {e}"
    _audit("KILL_PROCESS", {"id": process_id})
    return f"Stopped #{process_id}."


def list_processes() -> str:
    """List every background process started this session, with its current status."""
    if not state._bg_processes:
        return "No background processes started this session."
    lines = []
    for pid_label, info in sorted(state._bg_processes.items(), key=lambda kv: int(kv[0])):
        ret = info["proc"].poll()
        status = "running" if ret is None else f"exited {ret}"
        lines.append(f"#{pid_label} [{status}] started {info['started_at']} — {info['command']}")
    return "\n".join(lines)


def _cleanup_background_processes(verbose: bool = False) -> None:
    """Stop every still-running background process (session end / interpreter exit).
    Waits for real termination (SIGKILL fallback) rather than firing SIGTERM and hoping —
    otherwise poll() right after would still report "running" (not yet reaped)."""
    for pid_label, info in list(state._bg_processes.items()):
        proc = info["proc"]
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait(timeout=2)
                if verbose:
                    ui.console.print(f"[dim]{t('bg_stopped_on_exit', id=pid_label, command=info['command'])}[/dim]")
            except Exception:
                pass
        try:
            info["log_file"].close()
        except Exception:
            pass
