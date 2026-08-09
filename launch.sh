#!/usr/bin/env bash
# Launch the Ollamancer agent.
#
# Usage:
#   bash launch.sh                                 start in the current directory
#   bash launch.sh ~/Desktop/MyProject             start with MyProject as the root
#   bash launch.sh ~/Desktop/MyProject --safe      also approve risky tool calls
#   bash launch.sh ~/Desktop/MyProject --sandbox   also isolate shell/REPL in Docker
#   bash launch.sh ~/Desktop/MyProject --private   ephemeral session, nothing written to disk
#
# Flags may appear in any order, before or after the project path.
#
set -e

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"   # the agent's own directory

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
PROJECT_ROOT="${POSITIONAL[0]:-$(pwd)}"       # first non-flag argument, else the current directory

# Create the virtual environment if it is missing
if [ ! -d "$AGENT_DIR/.venv" ]; then
    echo "→ Creating the virtual environment..." >&2
    python3 -m venv "$AGENT_DIR/.venv"
fi

# Install or update the dependencies
echo "→ Checking dependencies..." >&2
"$AGENT_DIR/.venv/bin/pip" install -r "$AGENT_DIR/requirements.txt" -q

if [ ${#PASSTHROUGH[@]} -eq 0 ]; then
    echo "→ Project: $PROJECT_ROOT"
    echo ""
fi

# Run the agent against the project folder
"$AGENT_DIR/.venv/bin/python" "$AGENT_DIR/agent.py" "$PROJECT_ROOT" \
    $SAFE_FLAG $SANDBOX_FLAG $PRIVATE_FLAG "${PASSTHROUGH[@]}"
