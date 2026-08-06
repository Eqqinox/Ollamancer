#!/usr/bin/env python3
"""
Agentic_1A — Pont iMessage v1.0
─────────────────────────────────
Depuis iPhone : envoie "! ta question" à toi-même (ton propre numéro/email)
Le Mac reçoit, l'agent traite, tu reçois la réponse par iMessage.

Prérequis :
  - Réglages Système → Confidentialité → Accès complet au disque → Terminal ✓
  - Messages.app ouvert sur le Mac
  - Ollama démarré (ollama serve)
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

# ── Chemins ────────────────────────────────────────────────────────────────────
AGENT_DIR   = Path(__file__).parent
CONFIG_FILE = Path.home() / ".agentic_imessage.json"
MESSAGES_DB = Path.home() / "Library" / "Messages" / "chat.db"

# ── Paramètres ─────────────────────────────────────────────────────────────────
TRIGGER      = "!"    # Préfixe déclencheur — envoie "! ta question"
POLL_SECS    = 3      # Fréquence de sondage en secondes
MAX_MSG_LEN  = 1800   # Longueur max par fragment iMessage

# ── Import de l'agent (outils, boucle ReAct, etc.) ────────────────────────────
sys.path.insert(0, str(AGENT_DIR))
try:
    import agent as _a
except ImportError as e:
    print(f"[Erreur] Impossible d'importer agent.py : {e}")
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
    """Assistant de configuration initiale (run once)."""
    print("\n══════════════════════════════════════════")
    print("  Agentic_1A — Configuration iMessage")
    print("══════════════════════════════════════════\n")
    print("Tu vas envoyer des commandes à toi-même depuis iPhone.")
    print("Le pont a besoin de ton identifiant iMessage pour filtrer les messages.\n")
    print("Format accepté : +33612345678  ou  tonemail@icloud.com\n")

    handle  = input("Ton numéro / email iMessage : ").strip()
    project = input(f"Dossier projet par défaut [{Path.home() / 'Desktop'}] : ").strip()

    if not project:
        project = str(Path.home() / "Desktop")

    cfg = {"handle": handle, "project_root": project}
    save_config(cfg)
    print(f"\n✓ Sauvegardé dans {CONFIG_FILE}")
    print(f"  Handle  : {handle}")
    print(f"  Projet  : {project}\n")
    return cfg


# ── Lecture Messages ──────────────────────────────────────────────────────────

def _decode_attributed_body(data: bytes) -> str | None:
    """
    Extrait le texte d'un blob attributedBody (NSKeyedArchive).
    Nécessaire sur macOS Ventura+ où le champ text est parfois NULL.
    """
    if not data:
        return None
    try:
        blob = bytes(data)
        # Motif principal observé dans les bplists iMessage
        m = re.search(rb'\x01\+(.*?)(\x00\x00|\x86|\x85|\x84)', blob, re.DOTALL)
        if m:
            raw = m.group(1)
            txt = raw.decode("utf-8", errors="replace").strip()
            if txt:
                return txt
        # Fallback : extraire toutes les chaînes ASCII/UTF-8 lisibles
        strings = re.findall(rb'[\x20-\x7e\xc0-\xff]{3,}', blob)
        parts   = [s.decode("utf-8", errors="ignore") for s in strings]
        parts   = [p for p in parts if not p.startswith("NS") and len(p) > 2]
        return " ".join(parts[:8]).strip() or None
    except Exception:
        return None


def _get_text(text, attributed_body) -> str | None:
    """Retourne le texte d'un message, quel que soit le format."""
    if text:
        return str(text).strip()
    return _decode_attributed_body(attributed_body)


def get_max_rowid() -> int:
    """Retourne le ROWID max actuel (pour ignorer l'historique au démarrage)."""
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
    Retourne les nouveaux messages reçus depuis since_rowid.
    Filtre sur handle_filter si défini.
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
        # Filtre handle : si configuré, n'accepter que ce contact
        if handle_filter:
            # Correspondance flexible (numéro ↔ email, préfixe international)
            norm_filter = re.sub(r"[\s\-\(\)]", "", handle_filter).lower()
            norm_handle = re.sub(r"[\s\-\(\)]", "", h_id).lower()
            if norm_filter not in norm_handle and norm_handle not in norm_filter:
                continue
        results.append((rowid, msg, h_id))

    return results


# ── Envoi iMessage ─────────────────────────────────────────────────────────────

def send_imessage(to: str, text: str) -> bool:
    """Envoie un iMessage via AppleScript (découpe si > MAX_MSG_LEN)."""
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
            print(f"[iMessage] Erreur envoi : {r.stderr.strip()}")
            ok = False
        if len(chunks) > 1:
            time.sleep(0.8)  # Anti-spam entre fragments
    return ok


# ── Agent ──────────────────────────────────────────────────────────────────────

def init_agent(project_root: Path):
    """Initialise les globaux de l'agent avant usage."""
    agentic_dir = AGENT_DIR / ".agentic"
    agentic_dir.mkdir(exist_ok=True)
    (agentic_dir / "snapshots").mkdir(exist_ok=True)

    _a.PROJECT_ROOT  = project_root
    _a._AUDIT_LOG    = agentic_dir / f"imessage_{datetime.now().strftime('%Y%m%d')}.log"
    _a._SNAPSHOT_DIR = agentic_dir / "snapshots"

    os.chdir(project_root)


def run_agent(command: str, project_root: Path) -> str:
    """Exécute l'agent pour une commande iMessage et retourne la réponse."""
    init_agent(project_root)

    system_prompt = (
        _a.make_system_prompt(project_root)
        + "\n\nTu réponds via iMessage depuis un iPhone. "
          "Sois concis, clair, et bien structuré. "
          "Remplace les blocs de code longs par des descriptions si non demandés. "
          "Utilise des emojis avec modération pour la lisibilité mobile."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": command},
    ]

    try:
        return _a.run_agent(messages, _a.DEFAULT_MODEL)
    except Exception as e:
        return f"❌ Erreur : {e}"


# ── Boucle principale ──────────────────────────────────────────────────────────

def main():
    # ── Vérifications ─────────────────────────────────────────────────────────
    if not MESSAGES_DB.exists():
        print(f"\n[Erreur] Base de données Messages introuvable :")
        print(f"  {MESSAGES_DB}")
        print(f"\n→ Accorder l'accès dans :")
        print(f"  Réglages Système → Confidentialité → Accès complet au disque → Terminal ✓\n")
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

    # Ignorer les anciens messages au démarrage
    last_rowid = get_max_rowid()

    # ── Header ─────────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%H:%M:%S")
    console.print()
    console.print("─" * 50)
    console.print(f"  [bold cyan]Agentic_1A — Pont iMessage[/bold cyan]")
    console.print(f"  Démarré à [yellow]{ts}[/yellow]")
    console.print(f"  Handle   : [green]{handle_filter or 'tous les contacts'}[/green]")
    console.print(f"  Projet   : [white]{project_root}[/white]")
    console.print(f"  Trigger  : [yellow]{TRIGGER}[/yellow]  (ex: [dim]{TRIGGER} quelle heure est-il ?[/dim])")
    console.print(f"  Polling  : toutes les {POLL_SECS}s")
    console.print("─" * 50)
    console.print()
    console.print(f"[dim]En attente de messages... (Ctrl+C pour arrêter)[/dim]")

    # Vérifier qu'Ollama est disponible
    if not _a.check_ollama(_a.DEFAULT_MODEL):
        console.print("[red]Lance Ollama avant de démarrer le pont : ollama serve[/red]")
        sys.exit(1)

    # ── Boucle de polling ──────────────────────────────────────────────────────
    try:
        while True:
            new_msgs = get_new_messages(last_rowid, handle_filter)

            for rowid, text, handle in new_msgs:
                last_rowid = max(last_rowid, rowid)

                stripped = text.strip()
                if not stripped.startswith(TRIGGER):
                    continue  # Pas le bon trigger

                command = stripped[len(TRIGGER):].strip()
                if not command:
                    continue

                ts_now = datetime.now().strftime("%H:%M:%S")
                console.print(f"\n[{ts_now}] [cyan]📩 {handle}[/cyan] : {command[:80]}")

                # ── Accusé de réception immédiat ──────────────────────────
                send_imessage(handle_filter or handle, "⏳")

                # ── Traitement agent ───────────────────────────────────────
                t0       = time.time()
                response = run_agent(command, project_root)
                elapsed  = time.time() - t0

                # ── Envoi réponse ──────────────────────────────────────────
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
