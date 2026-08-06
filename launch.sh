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
for arg in "$@"; do
    if [ "$arg" = "--safe" ]; then
        SAFE_FLAG="--safe"
    elif [ "$arg" = "--sandbox" ]; then
        SANDBOX_FLAG="--sandbox"
    elif [ "$arg" = "--private" ] || [ "$arg" = "--incognito" ]; then
        PRIVATE_FLAG="--private"
    else
        POSITIONAL+=("$arg")
    fi
done
PROJECT_ROOT="${POSITIONAL[0]:-$(pwd)}"       # 1er arg non-flag, ou dossier courant

# Créer le venv si absent
if [ ! -d "$AGENT_DIR/.venv" ]; then
    echo "→ Création de l'environnement virtuel..."
    python3 -m venv "$AGENT_DIR/.venv"
fi

# Installer / mettre à jour les dépendances
echo "→ Vérification des dépendances..."
"$AGENT_DIR/.venv/bin/pip" install -r "$AGENT_DIR/requirements.txt" -q

echo "→ Projet : $PROJECT_ROOT"
echo ""

# Lancer l'agent avec le dossier projet
"$AGENT_DIR/.venv/bin/python" "$AGENT_DIR/agent.py" "$PROJECT_ROOT" $SAFE_FLAG $SANDBOX_FLAG $PRIVATE_FLAG
