"""Harness Framework — MCP (Model Context Protocol) Integration.

Provides:
- MCPRegistry: Standard MCP protocol registry (stdio + SSE transports)
- MCPToolDef: Standard tool definition
- MCP tool → LangChain tool conversion
- Backward-compatible MCPManager (fallback)
"""

from .registry import (
    MCPRegistry,
    MCPToolDef,
    MCPServerConfig,
    MCPToolNotFoundError,
    MCPConnectionError,
    mcp_registry,
)
from .manager import MCPManager, MCPTool, MCPServer, mcp_manager

__all__ = [
    "MCPRegistry",
    "MCPToolDef",
    "MCPServerConfig",
    "MCPToolNotFoundError",
    "MCPConnectionError",
    "mcp_registry",
    "MCPManager",
    "MCPTool",
    "MCPServer",
    "mcp_manager",
    "mcp_tool_to_langchain",
    "mcp_tools_to_langchain",
]


def __getattr__(name: str):
    if name == "mcp_tool_to_langchain":
        from .tools import mcp_tool_to_langchain
        return mcp_tool_to_langchain
    if name == "mcp_tools_to_langchain":
        from .tools import mcp_tools_to_langchain
        return mcp_tools_to_langchain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
