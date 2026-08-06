#!/usr/bin/env bash
# Lance l'agent Agentic_1A
#
# Usage :
#   bash launch.sh                                → démarre dans le dossier courant
#   bash launch.sh ~/Desktop/MonProjet             → démarre avec MonProjet comme racine
#   bash launch.sh ~/Desktop/MonProjet --safe      → + mode sûr (ordre des args libre)
#   bash launch.sh ~/Desktop/MonProjet --sandbox   → + sandbox Docker (ordre des args libre)
#   bash launch.sh ~/Desktop/MonProjet --private   → session privée non journalisée (éphémère)
#
set -e

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"   # Dossier de l'agent (Agentic_1A/)

SAFE_FLAG=""
SANDBOX_FLAG=""
PRIVATE_FLAG=""
POSITIONAL=()
PASSTHROUGH=()          # --run / --recipe and their argument, relayed untouched
while [ $# -gt 0 ]; do
    case "$1" in
        --safe)                  SAFE_FLAG="--safe"; shift ;;
        --sandbox)               SANDBOX_FLAG="--sandbox"; shift ;;
        --private|--incognito)   PRIVATE_FLAG="--private"; shift ;;
        --run|--recipe)          PASSTHROUGH+=("$1" "$2"); shift 2 ;;
        *)                       POSITIONAL+=("$1"); shift ;;
    esac
done
PROJECT_ROOT="${POSITIONAL[0]:-$(pwd)}"       # 1er arg non-flag, ou dossier courant

# Créer le venv si absent
if [ ! -d "$AGENT_DIR/.venv" ]; then
    echo "→ Creating the virtual environment..." >&2
    python3 -m venv "$AGENT_DIR/.venv"
fi

# Installer / mettre à jour les dépendances
echo "→ Checking dependencies..." >&2
"$AGENT_DIR/.venv/bin/pip" install -r "$AGENT_DIR/requirements.txt" -q

if [ ${#PASSTHROUGH[@]} -eq 0 ]; then
    echo "→ Project: $PROJECT_ROOT"
    echo ""
fi

# Lancer l'agent avec le dossier projet
"$AGENT_DIR/.venv/bin/python" "$AGENT_DIR/agent.py" "$PROJECT_ROOT" \
    $SAFE_FLAG $SANDBOX_FLAG $PRIVATE_FLAG "${PASSTHROUGH[@]}"
