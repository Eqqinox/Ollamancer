#!/usr/bin/env python3
"""Agentic_1A — a fully-local, terminal-first AI agent for Ollama.

This file is the entry point and a compatibility facade. The implementation lives in the
`agentic/` package:

    config.py       persisted, user-tunable settings (the 30 /parameters values)
    state.py        per-session runtime state, plus reset()
    i18n.py         the bilingual EN/FR interface strings and the system prompt
    ui.py           console, prompt, autocomplete, escape-to-stop, /parameters menu
    safety.py       blocklists, path confinement, safe mode, the Docker sandbox, audit
    checkpoints.py  the shadow-git repository behind /undo
    models.py       model discovery, context negotiation, RAM, the /model picker
    mcp_client.py   MCP servers and the sync-to-async bridge
    skills.py       SKILL.md discovery and progressive disclosure
    tools/          the 34 tools, one module per domain, registry in __init__.py
    loop.py         the ReAct loop, plumbing retries, honesty nudges, compaction
    commands.py     slash commands, architect/review, session persistence
    cli.py          argument parsing and the interactive/headless entry point

Run it directly (`python agent.py <project>`) or through `launch.sh`, which sets up the venv.

The names re-exported below exist so `import agent` keeps working for anything that used the
single-file layout. New code should import from the owning module — and note that values
rebound at runtime (config, state, ui.console) must always be reached *through* their module,
never imported by name, or the copy goes stale. See tests/test_import_rules.py.
"""

import sys

from agentic import (checkpoints, commands, config, i18n, loop, mcp_client, models, safety,
                     skills, state, tools, ui)
from agentic.cli import main
from agentic.i18n import HELP_TEXT, STR, SYSTEM_PROMPT, get_help_text, t
from agentic.tools import TOOL_MAP, TOOLS

__all__ = [
    "main", "checkpoints", "commands", "config", "i18n", "loop", "mcp_client", "models",
    "safety", "skills", "state", "tools", "ui",
    "TOOLS", "TOOL_MAP", "STR", "SYSTEM_PROMPT", "HELP_TEXT", "get_help_text", "t",
]

if __name__ == "__main__":
    main()
