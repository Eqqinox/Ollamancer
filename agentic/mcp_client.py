"""Agentic_1A — MCP (Model Context Protocol) client.

Connects to third-party MCP servers listed in `~/.agentic_1a_mcp.json` — the same
`{"mcpServers": {...}}` format as Claude Desktop and Claude Code, so an existing config is
reusable as-is — and exposes their tools to the model under `mcp__<server>__<tool>`, alongside
the native ones.

**The sync-to-async bridge is the delicate part.** agent.py is entirely synchronous; the MCP
SDK is async. Each server's whole lifecycle — connect, serve calls, shut down — runs inside a
single persistent asyncio Task on a dedicated thread with its own event loop. That is not
incidental: the anyio cancel scopes ClientSession uses internally are bound to the Task that
opened them, so servicing calls from different Tasks (the naive one-run_coroutine_threadsafe-
per-call approach) breaks shutdown. This design was prototyped and verified in isolation
before integration — connect, two sequential calls on one session, clean shutdown with no
orphaned subprocess, and a clean failure rather than a crash when a server won't start.

Everything degrades quietly. The `mcp` package is an optional dependency: without it
`_MCP_AVAILABLE` is False and the whole feature disables itself. A server that fails to start
is logged and skipped, never blocking the others or the agent.

MCP tools are treated as risky by default in safe mode — a server can do anything a local
tool can, so it must not bypass the approval gate.
"""

import asyncio
import json
import threading
from concurrent.futures import Future

from agentic import config, ui

try:
    from mcp import ClientSession, StdioServerParameters, stdio_client
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False  # MCP support silently disables itself; rest of the agent unaffected

_MCP_SHUTDOWN = object()


class _MCPServerConnection:
    """One live MCP session (one server), carried by a dedicated thread + a
    persistent asyncio loop. Raises directly from __init__ if the connection
    fails — the caller (_init_mcp) catches that per server so one broken
    server never prevents the others from starting."""

    def __init__(self, name: str, command: str, args: list, env: dict | None = None):
        self.name = name
        self._loop = asyncio.new_event_loop()
        self._queue = None
        self._ready = threading.Event()
        self._ready_error = None
        self._thread = threading.Thread(
            target=self._thread_main, args=(command, args, env), daemon=True, name=f"mcp-{name}"
        )
        self._thread.start()
        self._ready.wait(timeout=20)
        if self._ready_error is not None:
            raise self._ready_error
        if not self._ready.is_set():
            raise TimeoutError(f"MCP server '{name}' did not respond within 20s")

    def _thread_main(self, command, args, env):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._session_main(command, args, env))
        finally:
            self._loop.close()

    async def _session_main(self, command, args, env):
        self._queue = asyncio.Queue()
        try:
            params = StdioServerParameters(command=command, args=args, env=env)
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    self._ready.set()
                    while True:
                        item = await self._queue.get()
                        if item is _MCP_SHUTDOWN:
                            break
                        coro_factory, fut = item
                        try:
                            result = await coro_factory(session)
                            if not fut.done():
                                fut.set_result(result)
                        except Exception as e:
                            if not fut.done():
                                fut.set_exception(e)
        except Exception as e:
            self._ready_error = e
            self._ready.set()

    def _submit(self, coro_factory, timeout=30):
        fut = Future()
        def _enqueue():
            self._queue.put_nowait((coro_factory, fut))
        self._loop.call_soon_threadsafe(_enqueue)
        return fut.result(timeout=timeout)

    def list_tools(self):
        return self._submit(lambda session: session.list_tools())

    def call_tool(self, name: str, args: dict) -> tuple:
        """Returns (CallToolResult, list of progress notifications received during
        the call). Without a progress_callback the MCP SDK receives and silently
        discards those notifications — neither the human (console) nor the model
        (tool-result text) ever saw them, even for a tool that genuinely sends
        them (confirmed in real conditions: `trigger-long-running-operation`
        showed only a final message)."""
        progress_events: list[str] = []

        async def _on_progress(progress: float, total: float | None, message: str | None) -> None:
            label = message or (f"{progress}/{total}" if total else str(progress))
            progress_events.append(label)
            ui.console.print(f"[dim]  ↳ MCP progress ({self.name}/{name}): {label}[/dim]")

        result = self._submit(lambda session: session.call_tool(name, args, progress_callback=_on_progress))
        return result, progress_events

    def close(self):
        if not self._thread.is_alive():
            return
        def _enqueue_shutdown():
            self._queue.put_nowait(_MCP_SHUTDOWN)
        try:
            self._loop.call_soon_threadsafe(_enqueue_shutdown)
        except Exception:
            return
        self._thread.join(timeout=10)


MCP_CONNECTIONS: dict[str, "_MCPServerConnection"] = {}   # server name -> connection


MCP_TOOL_MAP: dict[str, tuple] = {}                        # tool name  -> (connection, real_tool_name)


MCP_TOOL_SCHEMAS: list = []                                 # dict schemas appended to tools=


def _mcp_result_to_text(result, progress_events: list | None = None) -> str:
    """Flatten an MCP CallToolResult (a list of text/image/... blocks) into the
    same plain-text format every other tool already returns — nothing downstream
    (audit, result panel, safe mode) needs to know the source is an MCP server
    rather than a local Python function. Progress notifications (if there were
    any) are prefixed to the result — without that, the model has no way
    whatsoever to know a long-running tool reported progress, only the final
    message."""
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(f"[non-text content: {type(block).__name__}]")
    text = "\n".join(parts) if parts else "(empty result)"
    if getattr(result, "is_error", False):
        text = f"⚠️ MCP tool error: {text}"
    if progress_events:
        progress_block = "\n".join(f"- {e}" for e in progress_events)
        text = f"[Progress notifications received during this call:\n{progress_block}]\n\n{text}"
    return text


def _init_mcp() -> None:
    """Connect each configured MCP server. A server that fails to start is
    logged and skipped — it never prevents the other servers or the rest of
    the agent from working."""
    if not _MCP_AVAILABLE:
        return
    if not config.MCP_CONFIG_FILE.exists():
        return
    try:
        mcp_config = json.loads(config.MCP_CONFIG_FILE.read_text())
    except Exception as e:
        ui.console.print(f"[yellow]MCP: could not parse {config.MCP_CONFIG_FILE} — {e}[/yellow]")
        return

    servers = mcp_config.get("mcpServers", {})
    for server_name, server_cfg in servers.items():
        command = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env")
        if not command:
            ui.console.print(f"[yellow]MCP: server '{server_name}' has no \"command\", skipped.[/yellow]")
            continue
        try:
            conn = _MCPServerConnection(server_name, command, args, env)
            tools_result = conn.list_tools()
        except Exception as e:
            ui.console.print(f"[yellow]MCP: server '{server_name}' failed to start — {type(e).__name__}: {e}[/yellow]")
            continue

        MCP_CONNECTIONS[server_name] = conn
        for tool in tools_result.tools:
            qualified_name = f"mcp__{server_name}__{tool.name}"
            MCP_TOOL_MAP[qualified_name] = (conn, tool.name)
            MCP_TOOL_SCHEMAS.append({
                "type": "function",
                "function": {
                    "name": qualified_name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema or {"type": "object", "properties": {}},
                },
            })
        ui.console.print(f"[dim]MCP: connected '{server_name}' ({len(tools_result.tools)} tool(s)).[/dim]")


def _cleanup_mcp() -> None:
    for conn in list(MCP_CONNECTIONS.values()):
        try:
            conn.close()
        except Exception:
            pass
