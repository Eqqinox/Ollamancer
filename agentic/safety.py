"""Ollamancer — safety rails.

Everything that decides whether an action is allowed to happen, and everything that records
that it did. Four independent layers, deliberately kept separate:

1. **Blocklists** — command patterns and file paths that are never allowed, whatever the
   mode (`_check_command`, `_check_file_path`, `_check_url`, `_check_robots`).
2. **Path confinement** — `_check_file_path` canonicalises first and then requires the target
   to sit under `state.PROJECT_ROOT`. This is the real boundary; the sensitive-path denylist
   is defence in depth on top of it, not a substitute. It was added in v2.9.16 after an
   adversarial test found that write_file, edit_file, read_file, lint_file, create_directory
   and /add had never checked containment at all.
3. **Safe mode** — `_confirm_risky_call` gates the tools in `_RISKY_TOOLS` behind a [y/N]
   prompt. Enter alone means no: it fails on the cautious side.
4. **The Docker sandbox** — contains the blast radius of shell execution. Orthogonal to safe
   mode: one gates *approval*, the other contains *impact*, and they compose. Fail-closed —
   if the sandbox is requested but Docker is unavailable, the command is refused rather than
   silently run on the host.

Plus `_audit`, which records every tool call (and every refusal) to the session log, and
`_auto_snapshot`, which copies a file before it is edited so /undo has something to restore.

This module is a leaf: it depends on config, state, ui and i18n, and nothing depends on it
except the tools themselves.
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests

from agentic import config, state, ui
from agentic.i18n import t
from agentic.ui import _prompt

_RISKY_TOOLS = {"write_file", "append_file", "edit_file", "run_command", "run_tests", "run_background", "kill_process", "git_commit", "python_repl"}


_SANDBOX_IMAGE_DEFAULT = "agentic1a-sandbox-default:latest"


_DEFAULT_SANDBOX_DOCKERFILE = """FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
        git curl build-essential nodejs npm \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
"""


# Command patterns too destructive to ever allow
_CMD_BLOCKLIST = [
    (r"rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f\s+/",  "rm -rf on system root"),
    (r"rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f\s+~",  "rm -rf on home directory"),
    (r"rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f\s+\*", "rm -rf with wildcard"),
    (r"\bdd\s+if=",                          "dd on a block device"),
    (r"\bmkfs\b",                            "filesystem formatting"),
    (r":\s*\(\s*\)\s*\{.*:\s*\|",           "fork bomb"),
    (r"(curl|wget|fetch).+\|\s*(ba)?sh\b",  "pipe to shell (remote execution)"),
    (r">\s*/dev/sd[a-z]",                   "direct write to raw disk"),
    (r"\bshred\b.*-[a-zA-Z]*u",             "irreversible secure deletion"),
]


# Sensitive file paths that are never accessible
_SENSITIVE_PATH_PATTERNS = [
    r"/\.ssh/",
    r"/\.aws/",
    r"/\.gnupg/",
    r"\.netrc$",
    r"/(id_rsa|id_ed25519|id_ecdsa|id_dsa)(\.pub)?$",
    r"\.(pem|key|p12|pfx|cer|crt|jks)$",
    r"/credentials$",
    r"/\.kube/",
    r"/\.docker/config\.json$",
    r"/Library/Keychains/",
    r"/Keychain\.keychain",
]


# Internal IPs/hostnames blocked in fetch_url (anti-SSRF)
_PRIVATE_HOST_PATTERNS = [
    r"^localhost$",
    r"^127\.",
    r"^10\.",
    r"^192\.168\.",
    r"^172\.(1[6-9]|2[0-9]|3[01])\.",
    r"^169\.254\.",    # Link-local / AWS metadata endpoint
    r"^::1$",
    r"^0\.0\.0\.0$",
    r"^fc[0-9a-f]{2}:",  # IPv6 private
]


def _check_command(cmd: str) -> tuple[bool, str]:
    """Check whether a command matches the blocklist. Returns (safe, reason)."""
    for pattern, reason in _CMD_BLOCKLIST:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, reason
    return True, ""


def _check_file_path(path_str: str) -> tuple[bool, str]:
    """Check whether a path is safe to read/write: contained within
    PROJECT_ROOT, and not a protected sensitive file.

    Containment is the real boundary (allowlist: only PROJECT_ROOT and its
    subdirectories are valid targets, checked on the *canonicalized* path via
    Path.relative_to() — resolves ../ and symlinks first, and does proper
    component-wise comparison rather than a bare string prefix check, which
    would wrongly let /project-evil match a /project root). The sensitive-
    pattern denylist below is defense in depth on top of that, not a
    substitute for it — found missing entirely (2026-08-03) when an absolute
    path pointed clean out of the project root and both write_file and its
    read-back silently operated on it with no containment check at all."""
    resolved = Path(path_str).expanduser().resolve()
    if state.PROJECT_ROOT is not None:
        root = state.PROJECT_ROOT.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return False, f"Path escapes the project root ({root}): {resolved}"
    resolved_str = str(resolved)
    for pattern in _SENSITIVE_PATH_PATTERNS:
        if re.search(pattern, resolved_str, re.IGNORECASE):
            return False, f"Protected sensitive path: {Path(path_str).name}"
    return True, ""


def _check_url(url: str) -> tuple[bool, str]:
    """Check that a URL doesn't target a private network (SSRF protection)."""
    try:
        hostname = urlparse(url).hostname or ""
        for pattern in _PRIVATE_HOST_PATTERNS:
            if re.match(pattern, hostname, re.IGNORECASE):
                return False, f"Private network access blocked (SSRF): {hostname}"
    except Exception:
        pass
    return True, ""


def _check_robots(url: str) -> tuple[bool, str]:
    """Check robots.txt for this URL. Fail-open: unreachable/malformed robots.txt,
    or any error, means allowed — robots.txt is a voluntary courtesy signal, not a
    security boundary (that's _check_url's job), so absence of a clear rule should
    never block a legitimate fetch."""
    try:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return True, ""

    rp = state._robots_cache.get(origin, "__unset__")
    if rp == "__unset__":
        rp = None
        try:
            robots_url = urljoin(origin, "/robots.txt")
            resp = requests.get(robots_url, headers={"User-Agent": config.USER_AGENT}, timeout=3)
            if resp.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
                rp = parser
        except Exception:
            rp = None
        state._robots_cache[origin] = rp

    if rp is None:
        return True, ""
    try:
        if rp.can_fetch(config.USER_AGENT, url):
            return True, ""
        return False, "disallowed by robots.txt"
    except Exception:
        return True, ""


def _audit(tool: str, args: dict, blocked: bool = False, reason: str = "") -> None:
    """Write an entry to the audit log."""
    if not state._AUDIT_LOG:
        return
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tag = "BLOCKED" if blocked else "OK     "
    args_s = json.dumps(args, ensure_ascii=False)[:250]
    line = f"{ts} | {tag} | {tool} | {args_s}"
    if reason:
        line += f" | {reason}"
    try:
        with open(state._AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _auto_snapshot(path_str: str) -> None:
    """Save a file's original content before modification (RAM + disk)."""
    p = Path(path_str).expanduser().resolve()
    key = str(p)
    if key not in state._snapshots and p.exists():
        try:
            content = p.read_text(encoding="utf-8")
            state._snapshots[key] = content
            # Persistance sur disque
            if state._SNAPSHOT_DIR and state._SNAPSHOT_DIR.exists():
                ts   = datetime.now().strftime("%H%M%S")
                dest = state._SNAPSHOT_DIR / f"{p.name}_{ts}.bak"
                dest.write_text(content, encoding="utf-8")
        except Exception:
            pass


def _confirm_risky_call(name: str, args: dict) -> bool:
    """Safe mode: ask for human approval before a tool that changes state (files,
    shell, processes, git). Refusal by default if the user just presses Enter —
    we fail on the cautious side."""
    args_s = json.dumps(args, ensure_ascii=False)
    ui.console.print(f"[bold yellow]{t('safe_mode_prompt', name=name, args=args_s)}[/bold yellow]")
    choice = _prompt(t("safe_mode_input")).strip().lower()
    return choice in ("y", "yes", "o", "oui")


def _docker_available() -> tuple[bool, str]:
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, "Docker daemon not running (is Docker Desktop started?)."
        return True, ""
    except FileNotFoundError:
        return False, "Docker not installed."
    except Exception as e:
        return False, f"Docker check failed: {e}"


def _sandbox_dockerfile_path() -> Path | None:
    custom = state.PROJECT_ROOT / ".agentic" / "sandbox.Dockerfile"
    return custom if custom.exists() else None


def _sandbox_image_tag() -> str:
    custom = _sandbox_dockerfile_path()
    if custom is None:
        return _SANDBOX_IMAGE_DEFAULT
    digest = hashlib.sha1(custom.read_bytes()).hexdigest()[:12]
    return f"agentic1a-sandbox-{digest}:latest"


def _ensure_sandbox_image() -> tuple[bool, str]:
    """Returns (ok, tag_or_error_message). Only rebuilds if the image does not
    already exist — a repeated /sandbox does not rebuild every time."""
    tag = _sandbox_image_tag()
    check = subprocess.run(["docker", "images", "-q", tag], capture_output=True, text=True, timeout=10)
    if check.stdout.strip():
        return True, tag

    custom = _sandbox_dockerfile_path()
    if custom is not None:
        dockerfile_path, build_context = custom, str(custom.parent)
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="agentic1a_sandbox_"))
        dockerfile_path = tmp_dir / "Dockerfile"
        dockerfile_path.write_text(_DEFAULT_SANDBOX_DOCKERFILE)
        build_context = str(tmp_dir)

    ui.console.print(f"[dim]Sandbox: building image {tag} (first use, may take a minute)...[/dim]")
    result = subprocess.run(
        ["docker", "build", "-t", tag, "-f", str(dockerfile_path), build_context],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()[-2000:]
    return True, tag


def _ensure_sandbox_container() -> tuple[bool, str]:
    """Returns (ok, container_name_or_error_message). Reuses this session's
    container if it is already running."""
    if state._SANDBOX_CONTAINER:
        check = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", state._SANDBOX_CONTAINER],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode == 0 and check.stdout.strip() == "true":
            return True, state._SANDBOX_CONTAINER
        state._SANDBOX_CONTAINER = None  # died/was removed in the meantime, so recreate one

    available, reason = _docker_available()
    if not available:
        return False, reason

    ok, tag_or_err = _ensure_sandbox_image()
    if not ok:
        return False, f"image build failed: {tag_or_err}"
    tag = tag_or_err

    container_name = f"agentic1a-sandbox-{os.getpid()}"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)  # any leftover container
    result = subprocess.run(
        ["docker", "run", "-d", "--name", container_name,
         "-v", f"{state.PROJECT_ROOT}:/workspace", "-w", "/workspace", tag,
         "tail", "-f", "/dev/null"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()[-1000:]
    state._SANDBOX_CONTAINER = container_name
    return True, container_name


def _cleanup_sandbox() -> None:
    if state._SANDBOX_CONTAINER:
        subprocess.run(["docker", "rm", "-f", state._SANDBOX_CONTAINER], capture_output=True, timeout=15)
        state._SANDBOX_CONTAINER = None


def _run_shell(command: str, timeout: int) -> tuple[str, int]:
    """Execution shared by run_command/run_tests: local (unchanged behaviour)
    when SANDBOX_MODE is off, otherwise via `docker exec` in the session
    container. Raises RuntimeError (no silent fallback to the host) if the
    sandbox is requested but unavailable."""
    if state.SANDBOX_MODE:
        ok, container_or_err = _ensure_sandbox_container()
        if not ok:
            raise RuntimeError(f"Sandbox unavailable ({container_or_err})")
        argv = ["docker", "exec", container_or_err, "sh", "-c", command]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    else:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
    return (result.stdout + result.stderr).strip(), result.returncode
