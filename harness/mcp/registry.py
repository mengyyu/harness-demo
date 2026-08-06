"""Harness Framework — Standard MCP Registry using mcp Python SDK.

Supports both stdio (subprocess) and SSE (HTTP) transport modes.
Replaces the custom MCPManager with standard MCP protocol support.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml

from config.settings import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════


@dataclass
class MCPToolDef:
    """Standard MCP tool definition."""
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    server_name: str = ""


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    description: str = ""
    transport: str = "stdio"  # stdio | sse
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    timeout: int = 30
    enabled: bool = True


class MCPToolNotFoundError(Exception):
    """Raised when a requested MCP tool is not found."""


class MCPConnectionError(Exception):
    """Raised when an MCP server connection fails."""


# ══════════════════════════════════════════════════════════
# MCP Registry
# ══════════════════════════════════════════════════════════


class MCPRegistry:
    """Standard MCP Protocol Registry.

    Manages connections to MCP servers via stdio or SSE,
    discovers tools, and provides a unified calling interface.

    Usage:
        registry = MCPRegistry()
        await registry.load_from_config("config/mcp_servers.yaml")
        tools = registry.to_langchain_tools()
    """

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._tools: dict[str, MCPToolDef] = {}
        self._sessions: dict[str, Any] = {}  # MCP ClientSession objects
        self._exit_stack = AsyncExitStack()

    # ── Configuration Loading ─────────────────────────────

    def load_config_from_yaml(self, config_path: str | None = None) -> list[MCPServerConfig]:
        """Load MCP server configurations from a YAML file.

        Args:
            config_path: Path to YAML config file. Uses settings.MCP_CONFIG_PATH if None.

        Returns:
            List of parsed server configurations.
        """
        path = config_path or settings.MCP_CONFIG_PATH
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("MCP config file not found: %s", path)
            return []

        configs = []
        for item in data.get("servers", []):
            config = MCPServerConfig(
                name=item["name"],
                description=item.get("description", ""),
                transport=item.get("transport", "stdio"),
                command=item.get("command", ""),
                args=item.get("args", []),
                url=item.get("url", ""),
                timeout=item.get("timeout", 30),
                enabled=item.get("enabled", True),
            )
            if config.enabled:
                self._servers[config.name] = config
                configs.append(config)

        logger.info("Loaded %d MCP server configs from %s", len(configs), path)
        return configs

    # ── Connection Management ─────────────────────────────

    async def connect_all(self) -> dict[str, bool]:
        """Connect to all configured MCP servers.

        Returns:
            Dict mapping server name → connection success.
        """
        results = {}
        for name, config in self._servers.items():
            try:
                await self._connect_server(config)
                results[name] = True
                logger.info("MCP server '%s' connected (%s)", name, config.transport)
            except Exception as e:
                results[name] = False
                logger.error("Failed to connect MCP server '%s': %s", name, e)
        return results

    async def _connect_server(self, config: MCPServerConfig):
        """Connect to a single MCP server and discover its tools."""
        if config.transport == "stdio":
            await self._connect_stdio(config)
        elif config.transport == "sse":
            await self._connect_sse(config)
        else:
            raise ValueError(f"Unsupported transport: {config.transport}")

    async def _connect_stdio(self, config: MCPServerConfig):
        """Connect via stdio subprocess."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning("mcp SDK not installed; falling back to demo mode for '%s'", config.name)
            return

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
        )

        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        self._sessions[config.name] = session
        await self._discover_tools(config.name, session)

    async def _connect_sse(self, config: MCPServerConfig):
        """Connect via SSE (Server-Sent Events)."""
        try:
            from mcp.client.sse import sse_client
            from mcp import ClientSession
        except ImportError:
            logger.warning("mcp SDK not installed; SSE transport unavailable for '%s'", config.name)
            return

        sse_transport = await self._exit_stack.enter_async_context(
            sse_client(config.url)
        )
        read_stream, write_stream = sse_transport
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()

        self._sessions[config.name] = session
        await self._discover_tools(config.name, session)

    async def _discover_tools(self, server_name: str, session: Any):
        """Discover tools from a connected MCP session."""
        try:
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                tool_def = MCPToolDef(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=server_name,
                )
                self._tools[tool.name] = tool_def
            logger.info("MCP server '%s': %d tools discovered", server_name, len(tools_result.tools))
        except Exception as e:
            logger.error("Failed to discover tools from '%s': %s", server_name, e)

    # ── Tool Management ───────────────────────────────────

    def register_local_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        server_name: str = "local",
        parameters: dict | None = None,
    ):
        """Register a local Python function as an MCP tool (demo/fallback mode).

        Args:
            name: Tool name.
            description: Human-readable description.
            handler: Async or sync callable.
            server_name: Logical server grouping.
            parameters: JSON Schema for tool parameters.
        """
        tool_def = MCPToolDef(
            name=name,
            description=description,
            parameters=parameters or {},
            server_name=server_name,
        )
        self._tools[name] = tool_def

        # Store handler on the tool def for direct calling
        tool_def._handler = handler  # type: ignore[attr-defined]

        # Ensure server entry exists
        if server_name not in self._servers:
            self._servers[server_name] = MCPServerConfig(
                name=server_name,
                description="Local tools (no external MCP server)",
                transport="local",
            )

    def get_tool(self, name: str) -> MCPToolDef | None:
        """Look up a tool by name across all servers."""
        return self._tools.get(name)

    def list_tools(self, server_name: str | None = None) -> list[dict]:
        """List all registered MCP tools.

        Args:
            server_name: Optional filter by server.

        Returns:
            List of tool info dicts.
        """
        tools = self._tools.values()
        if server_name:
            tools = [t for t in tools if t.server_name == server_name]

        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "server": t.server_name,
            }
            for t in tools
        ]

    def list_tools_by_server(self) -> dict[str, list[dict]]:
        """Group tools by their server."""
        result: dict[str, list[dict]] = {}
        for tool in self._tools.values():
            result.setdefault(tool.server_name, []).append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return result

    # ── Tool Execution ────────────────────────────────────

    async def call_tool(self, *args, **kwargs) -> Any:
        """Call a tool by name across all servers.

        Supports BOTH signatures for backward compatibility:

        New API: call_tool(tool_name, arguments=dict)
        Old API: call_tool(server_name, tool_name, arguments_dict)

        Args are auto-detected by position and type.
        """
        # Detect calling convention from positional args (excluding self)
        if len(args) == 0:
            raise ValueError("call_tool() requires at least a tool name")

        first = args[0]
        second = args[1] if len(args) > 1 else None
        third = args[2] if len(args) > 2 else None

        if isinstance(second, str) and not kwargs:
            # Old API: call_tool(server, tool, arguments_dict)
            tool_name = second
            arguments = third if isinstance(third, dict) else {}
        elif isinstance(second, dict) and not kwargs:
            # New API: call_tool(tool_name, arguments=dict) with positional dict
            tool_name = first
            arguments = second
        elif kwargs and not second:
            # New API: call_tool(tool_name, **kwargs) → args is keyword
            tool_name = first
            arguments = kwargs
        elif isinstance(second, str) and kwargs:
            # Old API with **kwargs: call_tool(server, tool, **kwargs)
            tool_name = second
            arguments = kwargs
        else:
            # New API: call_tool(tool_name, arguments=dict)
            tool_name = first
            arguments = second if isinstance(second, dict) else (third if isinstance(third, dict) else kwargs or {})

        tool = self._tools.get(tool_name)
        if not tool:
            raise MCPToolNotFoundError(f"Tool '{tool_name}' not found in any MCP server")

        # Local handler (demo/fallback mode)
        if hasattr(tool, "_handler"):
            handler = tool._handler
            args = arguments or {}
            if asyncio.iscoroutinefunction(handler):
                return await handler(**args)
            else:
                return handler(**args)

        # Standard MCP session call
        session = self._sessions.get(tool.server_name)
        if not session:
            raise MCPConnectionError(
                f"MCP server '{tool.server_name}' is not connected"
            )

        return await session.call_tool(tool_name, arguments or {})

    # ── LangChain Integration ─────────────────────────────

    def to_langchain_tools(self) -> list:
        """Convert all registered MCP tools to LangChain BaseTool instances.

        Returns:
            List of LangChain tools ready for use with an agent.
        """
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, create_model

        langchain_tools = []

        for tool_def in self._tools.values():
            # Build Pydantic model from JSON schema for structured input
            fields = {}
            props = tool_def.parameters.get("properties", {})
            required = tool_def.parameters.get("required", [])
            for param_name, param_info in props.items():
                param_type = self._json_type_to_python(param_info.get("type", "string"))
                default = ... if param_name in required else None
                fields[param_name] = (
                    param_type,
                    default if default is ... else default,
                )
                # For optional fields, use proper typing
                if param_name not in required:
                    from typing import Optional as Opt
                    fields[param_name] = (Opt[param_type], None)

            if fields:
                args_schema = create_model(
                    f"{tool_def.name}_args",
                    **fields,
                )
            else:
                args_schema = None

            # Create the async wrapper function
            async def _tool_func(**kwargs) -> str:
                return str(await self.call_tool(tool_def.name, kwargs))

            # Create the tool
            lc_tool = StructuredTool(
                name=tool_def.name,
                description=tool_def.description,
                func=_tool_func,
                coroutine=_tool_func,
                args_schema=args_schema,
            )
            langchain_tools.append(lc_tool)

        return langchain_tools

    @staticmethod
    def _json_type_to_python(json_type: str) -> type:
        """Map JSON Schema type to Python type."""
        mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return mapping.get(json_type, str)

    # ── Lifecycle ─────────────────────────────────────────

    async def close_all(self):
        """Close all MCP server connections."""
        for name in list(self._sessions.keys()):
            try:
                # Sessions are managed by exit stack
                pass
            except Exception as e:
                logger.error("Error closing MCP server '%s': %s", name, e)

        await self._exit_stack.aclose()
        self._tools.clear()
        self._sessions.clear()
        logger.info("All MCP connections closed")

    # ── Stats ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get registry statistics."""
        servers_info = []
        for name, config in self._servers.items():
            server_tools = [t for t in self._tools.values() if t.server_name == name]
            servers_info.append({
                "name": name,
                "description": config.description,
                "transport": config.transport,
                "status": "connected" if name in self._sessions or config.transport == "local" else "disconnected",
                "tool_count": len(server_tools),
                "tools": [t.name for t in server_tools],
            })

        return {
            "total_servers": len(self._servers),
            "connected_servers": sum(
                1 for s in servers_info if s["status"] == "connected"
            ),
            "total_tools": len(self._tools),
            "servers": servers_info,
        }


# Global singleton
mcp_registry = MCPRegistry()
