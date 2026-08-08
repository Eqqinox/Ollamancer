---
name: mcp-builder
description: Build a new MCP (Model Context Protocol) server that this agent can connect to, exposing external tools/data. Use when the user wants to create an MCP server, add a custom tool via MCP, or wrap an API/service as agent tools.
license: Apache-2.0
---

# MCP builder

Guide the user to build a working MCP server and wire it into this agent. Adapted for this
agent from Anthropic's open `mcp-builder` (anthropics/skills, Apache-2.0). This agent connects
to MCP servers listed in `~/.agentic_1a_mcp.json` (same `{"mcpServers": {...}}` format as
Claude Desktop/Claude Code), so a server you build here becomes usable as native-looking tools.

## Steps

1. **Research the target.** Understand the API/service being wrapped: its endpoints, auth, and
   the few high-value operations worth exposing. Use `search_web`/`fetch_url` for the API docs.
   Prefer a small set of clear, well-described tools over many niche ones, the local model
   picks tools by their descriptions.

2. **Pick the language.** Python (with the `mcp` package) is the smoothest fit here since this
   agent's venv already has `mcp` installed. TypeScript is fine too if the user prefers Node.

3. **Implement the server.** Create a small server exposing each operation as an MCP tool with
   a precise name + description and a typed input schema. Write it with `write_file`
   (chunk files > ~80 lines with `append_file`). For a Python server, use the official
   `mcp` SDK's server API; keep each tool's docstring/description specific about *when* to use
   it. Put secrets in env vars, never hardcoded.

4. **Test it in isolation** before wiring it in:
   - `run_command` a quick self-check (e.g. `python your_server.py --help` or a smoke import),
   - or use the MCP inspector if available: `npx @modelcontextprotocol/inspector <cmd>`.
   Confirm the server starts, lists its tools, and a sample call returns the expected data.

5. **Register it with this agent.** Add an entry to `~/.agentic_1a_mcp.json`:
   ```json
   {"mcpServers": {"myserver": {"command": "python", "args": ["/abs/path/server.py"],
                                 "env": {"API_KEY": "..."}}}}
   ```
   Read the current file first (`read_file`), merge the new server in (don't clobber existing
   ones), then `write_file` it back. Tools appear as `mcp__myserver__<tool>` on next launch.

6. **Verify.** Tell the user to **restart the agent**, then run `/mcp`, the server and its
   discovered tools should be listed. A server that fails to start is logged and skipped
   without breaking the rest of the agent.

## Notes

- MCP gives the agent *access* (tools/data); a skill gives it *judgment* (workflow). They're
  complementary, build an MCP server when you need live data/actions, a skill when you need a
  repeatable how-to.
- Confirm with the user before running installs (`pip install`, `npm i`) or editing their
  `~/.agentic_1a_mcp.json`.
