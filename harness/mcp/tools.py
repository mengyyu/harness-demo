"""Harness Framework — MCP Tool → LangChain Tool converters."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import StructuredTool
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    StructuredTool = None  # type: ignore[misc]
    logger.debug("langchain_core not installed; MCP tool conversion unavailable")


def mcp_tool_to_langchain(tool_name: str, description: str, handler, args_schema=None) -> StructuredTool:
    """Convert a single MCP tool handler to a LangChain StructuredTool.

    Args:
        tool_name: The name of the tool.
        description: Human-readable tool description.
        handler: Async or sync callable.
        args_schema: Optional Pydantic model for structured input.

    Returns:
        A LangChain StructuredTool instance.
    """
    import asyncio

    if not HAS_LANGCHAIN:
        raise ImportError("langchain_core is required for MCP tool conversion")

    async def _async_wrapper(**kwargs) -> str:
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**kwargs)
        else:
            result = handler(**kwargs)
        return str(result) if not isinstance(result, str) else result

    return StructuredTool(
        name=tool_name,
        description=description,
        func=handler if not asyncio.iscoroutinefunction(handler) else None,
        coroutine=_async_wrapper,
        args_schema=args_schema,
    )


def mcp_tools_to_langchain(tools: list[dict]) -> list[StructuredTool]:
    """Convert multiple MCP tool definitions to LangChain tools.

    Args:
        tools: List of dicts with 'name', 'description', 'handler' keys.

    Returns:
        List of LangChain StructuredTool instances.
    """
    return [
        mcp_tool_to_langchain(
            tool_name=t["name"],
            description=t["description"],
            handler=t["handler"],
            args_schema=t.get("args_schema"),
        )
        for t in tools
    ]
