#!/usr/bin/env python3
"""
Ollamancer — iMessage bridge v1.0
─────────────────────────────────
From an iPhone: send "! your question" to yourself (your own number/email).
The Mac receives it, the agent handles it, and the answer comes back over iMessage.

Requirements (macOS only):
  - System Settings -> Privacy -> Full Disk Access -> Terminal ✓
  - Messages.app open on the Mac
  - Ollama running (ollama serve)
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
AGENT_DIR   = Path(__file__).parent
CONFIG_FILE = Path.home() / ".agentic_imessage.json"
MESSAGES_DB = Path.home() / "Library" / "Messages" / "chat.db"

# ── Settings ──────────────────────────────────────────────────────────────────
TRIGGER      = "!"    # Trigger prefix: send "! your question"
POLL_SECS    = 3      # Polling interval in seconds
MAX_MSG_LEN  = 1800   # Max length per iMessage fragment

# ── Import the agent (tools, ReAct loop, etc.) ────────────────────────────────
sys.path.insert(0, str(AGENT_DIR))
try:
    import agent as _a
    from agentic import config as _cfg, state as _st
except ImportError as e:
    print(f"[Error] Could not import agent.py: {e}")
    sys.exit(1)

try:
    from rich.console import Console
    console = Console()
except ImportError:
    class Console:
        def print(self, *a, **kw): print(*a)
    console = Console()


# ── Configuration ──────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def setup():
    """First-run configuration wizard (run once)."""
    print("\n══════════════════════════════════════════")
    print("  Ollamancer — Configuration iMessage")
    print("══════════════════════════════════════════\n")
    print("You will send commands to yourself from your iPhone.")
    print("The bridge needs your iMessage handle in order to filter messages.\n")
    print("Accepted format: +33612345678  or  you@icloud.com\n")

    handle  = input("Your iMessage number / email: ").strip()
    project = input(f"Default project folder [{Path.home() / 'Desktop'}] : ").strip()

    if not project:
        project = str(Path.home() / "Desktop")

    cfg = {"handle": handle, "project_root": project}
    save_config(cfg)
    print(f"\n✓ Saved to {CONFIG_FILE}")
    print(f"  Handle  : {handle}")
    print(f"  Project : {project}\n")
    return cfg


# ── Reading Messages ─────────────────────────────────────────────────────────

def _decode_attributed_body(data: bytes) -> str | None:
    """
    Extract the text from an attributedBody blob (NSKeyedArchive).
    Required on macOS Ventura+ where the text field is sometimes NULL.
    """
    if not data:
        return None
    try:
        blob = bytes(data)
        # Main pattern observed in iMessage bplists
        m = re.search(rb'\x01\+(.*?)(\x00\x00|\x86|\x85|\x84)', blob, re.DOTALL)
        if m:
            raw = m.group(1)
            txt = raw.decode("utf-8", errors="replace").strip()
            if txt:
                return txt
        # Fallback: extract every readable ASCII/UTF-8 string
        strings = re.findall(rb'[\x20-\x7e\xc0-\xff]{3,}', blob)
        parts   = [s.decode("utf-8", errors="ignore") for s in strings]
        parts   = [p for p in parts if not p.startswith("NS") and len(p) > 2]
        return " ".join(parts[:8]).strip() or None
    except Exception:
        return None


def _get_text(text, attributed_body) -> str | None:
    """Return a message's text, whatever the format."""
    if text:
        return str(text).strip()
    return _decode_attributed_body(attributed_body)


def get_max_rowid() -> int:
    """Return the current max ROWID (to ignore history at startup)."""
    try:
        conn = sqlite3.connect(f"file:{MESSAGES_DB}?mode=ro", uri=True)
        row  = conn.execute("SELECT COALESCE(MAX(ROWID),0) FROM message").fetchone()
        conn.close()
        return row[0]
    except Exception as e:
        print(f"[DB] {e}")
        return 0


def get_new_messages(since_rowid: int, handle_filter: str) -> list[tuple]:
    """
    Return the new messages received since since_rowid.
    Filters on handle_filter when set.
    """
    try:
        conn = sqlite3.connect(f"file:{MESSAGES_DB}?mode=ro", uri=True)
        rows = conn.execute("""
            SELECT m.ROWID, m.text, m.attributedBody, h.id
            FROM   message m
            JOIN   handle  h ON m.handle_id = h.ROWID
            WHERE  m.ROWID > ?
            ORDER  BY m.ROWID
        """, (since_rowid,)).fetchall()
        conn.close()
    except Exception as e:
        print(f"[DB] {e}")
        return []

    results = []
    for rowid, text, ab, h_id in rows:
        msg = _get_text(text, ab)
        if not msg:
            continue
        # Handle filter: if configured, accept only that contact
        if handle_filter:
            # Flexible matching (number <-> email, international prefix)
            norm_filter = re.sub(r"[\s\-\(\)]", "", handle_filter).lower()
            norm_handle = re.sub(r"[\s\-\(\)]", "", h_id).lower()
            if norm_filter not in norm_handle and norm_handle not in norm_filter:
                continue
        results.append((rowid, msg, h_id))

    return results


# ── Sending iMessage ───────────────────────────────────────────────────────────

def send_imessage(to: str, text: str) -> bool:
    """Send an iMessage via AppleScript (split if longer than MAX_MSG_LEN)."""
    chunks = [text[i:i+MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    ok = True
    for chunk in chunks:
        esc = (chunk
               .replace("\\", "\\\\")
               .replace('"',  '\\"')
               .replace("\n", "\\n"))
        script = f'''
tell application "Messages"
    set s to 1st service whose service type = iMessage
    set b to buddy "{to}" of s
    send "{esc}" to b
end tell
'''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[iMessage] Send error: {r.stderr.strip()}")
            ok = False
        if len(chunks) > 1:
            time.sleep(0.8)  # Anti-spam delay between fragments
    return ok


# ── Agent ──────────────────────────────────────────────────────────────────────

def init_agent(project_root: Path):
    """Initialise the agent's globals before use."""
    agentic_dir = AGENT_DIR / ".agentic"
    agentic_dir.mkdir(exist_ok=True)
    (agentic_dir / "snapshots").mkdir(exist_ok=True)

    _st.PROJECT_ROOT  = project_root
    _st._AUDIT_LOG    = agentic_dir / f"imessage_{datetime.now().strftime('%Y%m%d')}.log"
    _st._SNAPSHOT_DIR = agentic_dir / "snapshots"

    os.chdir(project_root)


def run_agent(command: str, project_root: Path) -> str:
    """Run the agent for one iMessage command and return the answer."""
    init_agent(project_root)

    system_prompt = (
        _a.make_system_prompt(project_root)
        + "\n\nYou are replying over iMessage to an iPhone. "
          "Be concise, clear and well structured. "
          "Replace long code blocks with a description unless code was asked for. "
          "Use emojis sparingly, for mobile readability."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": command},
    ]

    try:
        return _a.run_agent(messages, _cfg.DEFAULT_MODEL)
    except Exception as e:
        return f"❌ Error: {e}"


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    # ── Checks ───────────────────────────────────────────────────────────────
    if not MESSAGES_DB.exists():
        print(f"\n[Error] Messages database not found:")
        print(f"  {MESSAGES_DB}")
        print(f"\n-> Grant access in:")
        print(f"  System Settings -> Privacy -> Full Disk Access -> Terminal ✓\n")
        sys.exit(1)

    # ── Configuration ──────────────────────────────────────────────────────────
    if "--setup" in sys.argv:
        setup()
        return

    cfg = load_config()
    if not cfg:
        cfg = setup()

    handle_filter = cfg.get("handle", "")
    project_root  = Path(cfg.get("project_root", str(Path.home() / "Desktop")))

    if not project_root.exists():
        project_root = Path.home() / "Desktop"

    # Ignore pre-existing messages at startup
    last_rowid = get_max_rowid()

    # ── Header ─────────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%H:%M:%S")
    console.print()
    console.print("─" * 50)
    console.print(f"  [bold cyan]Ollamancer — iMessage bridge[/bold cyan]")
    console.print(f"  Started at [yellow]{ts}[/yellow]")
    console.print(f"  Handle   : [green]{handle_filter or 'all contacts'}[/green]")
    console.print(f"  Project  : [white]{project_root}[/white]")
    console.print(f"  Trigger  : [yellow]{TRIGGER}[/yellow]  (e.g. [dim]{TRIGGER} what time is it?[/dim])")
    console.print(f"  Polling  : every {POLL_SECS}s")
    console.print("─" * 50)
    console.print()
    console.print(f"[dim]Waiting for messages... (Ctrl+C to stop)[/dim]")

    # Check that Ollama is available
    if not _a.check_ollama(_cfg.DEFAULT_MODEL):
        console.print("[red]Start Ollama before launching the bridge: ollama serve[/red]")
        sys.exit(1)

    # ── Polling loop ──────────────────────────────────────────────────────────
    try:
        while True:
            new_msgs = get_new_messages(last_rowid, handle_filter)

            for rowid, text, handle in new_msgs:
                last_rowid = max(last_rowid, rowid)

                stripped = text.strip()
                if not stripped.startswith(TRIGGER):
                    continue  # Not the trigger prefix

                command = stripped[len(TRIGGER):].strip()
                if not command:
                    continue

                ts_now = datetime.now().strftime("%H:%M:%S")
                console.print(f"\n[{ts_now}] [cyan]📩 {handle}[/cyan] : {command[:80]}")

                # ── Immediate acknowledgement ─────────────────────────────
                send_imessage(handle_filter or handle, "⏳")

                # ── Agent processing ───────────────────────────────────────
                t0       = time.time()
                response = run_agent(command, project_root)
                elapsed  = time.time() - t0

                # ── Send the reply ──────────────────────────────────────────
                final = f"{response}\n\n─ {elapsed:.0f}s"
                if send_imessage(handle_filter or handle, final):
                    console.print(f"[{ts_now}] [green]✅ Réponse envoyée[/green] ({len(response)} chars, {elapsed:.0f}s)")
                else:
                    console.print(f"[{ts_now}] [red]❌ Échec envoi[/red]")

            time.sleep(POLL_SECS)

    except KeyboardInterrupt:
        console.print("\n[dim]Pont iMessage arrêté.[/dim]")


if __name__ == "__main__":
    main()
