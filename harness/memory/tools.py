"""Harness Framework — Mem0 Memory Tools for Agent integration.

Exposes memory operations as LangChain tools so the agent can
autonomously manage memories.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import StructuredTool
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    # Define a stub so type hints don't break
    StructuredTool = None  # type: ignore[misc]
    logger.debug("langchain_core not installed; memory tools unavailable")


# ══════════════════════════════════════════════════════════
# Pydantic Schemas
# ══════════════════════════════════════════════════════════


class AddMemoryInput(BaseModel):
    """Input schema for adding a memory."""
    content: str = Field(description="The content to store in memory")
    user_id: str = Field(default="default", description="ID of the user")
    memory_type: str = Field(
        default="user",
        description="Memory category: 'session', 'user', or 'entity'",
    )


class SearchMemoryInput(BaseModel):
    """Input schema for searching memories."""
    query: str = Field(description="Natural language search query")
    user_id: str = Field(default="default", description="ID of the user to filter by")
    top_k: int = Field(default=5, description="Maximum number of results")


class GetAllMemoryInput(BaseModel):
    """Input schema for listing all memories."""
    user_id: Optional[str] = Field(default=None, description="Optional user filter")


class DeleteMemoryInput(BaseModel):
    """Input schema for deleting a memory."""
    memory_id: str = Field(description="The ID of the memory to delete")


# ══════════════════════════════════════════════════════════
# Tool Factory
# ══════════════════════════════════════════════════════════


def create_memory_tools(memory_client) -> list:
    """Create LangChain tools from a Mem0Client instance.

    Args:
        memory_client: An instance of Mem0Client.

    Returns:
        A list of StructuredTool for agent use.
        Returns empty list if langchain_core is not installed.
    """
    if not HAS_LANGCHAIN:
        logger.warning("langchain_core not installed; memory tools unavailable")
        return []

    async def _add_memory(content: str, user_id: str = "default", memory_type: str = "user") -> str:
        memory_id = memory_client.add(content=content, user_id=user_id, memory_type=memory_type)
        return f"Memory stored successfully with ID: {memory_id}"

    async def _search_memory(query: str, user_id: str = "default", top_k: int = 5) -> str:
        results = memory_client.search(query=query, user_id=user_id, top_k=top_k)
        if not results:
            return f"No memories found for query: '{query}'"

        lines = [f"Found {len(results)} memories for '{query}':"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"  {i}. [{r.get('id', '?')}] (score: {r.get('score', 0):.2f}) "
                f"{r.get('content', '')[:200]}"
            )
        return "\n".join(lines)

    async def _get_all_memories(user_id: Optional[str] = None) -> str:
        results = memory_client.get_all(user_id=user_id)
        if not results:
            return "No memories found."

        lines = [f"Total memories: {len(results)}"]
        for i, r in enumerate(results[:20], 1):
            content = r.get("content", str(r))[:150]
            lines.append(f"  {i}. [{r.get('id', '?')}] {content}")
        if len(results) > 20:
            lines.append(f"  ... and {len(results) - 20} more")
        return "\n".join(lines)

    async def _delete_memory(memory_id: str) -> str:
        success = memory_client.delete(memory_id)
        if success:
            return f"Memory '{memory_id}' deleted successfully."
        return f"Memory '{memory_id}' not found."

    return [
        StructuredTool(
            name="add_memory",
            description="Store a new piece of information in persistent memory. Use this to remember "
                        "user preferences, important facts, or conversation context for future use.",
            func=_add_memory,
            coroutine=_add_memory,
            args_schema=AddMemoryInput,
        ),
        StructuredTool(
            name="search_memory",
            description="Search through stored memories using natural language. Use this to retrieve "
                        "relevant past information, user preferences, or context before responding.",
            func=_search_memory,
            coroutine=_search_memory,
            args_schema=SearchMemoryInput,
        ),
        StructuredTool(
            name="get_all_memories",
            description="List all stored memories for a user. Use this to get an overview of what "
                        "has been remembered.",
            func=_get_all_memories,
            coroutine=_get_all_memories,
            args_schema=GetAllMemoryInput,
        ),
        StructuredTool(
            name="delete_memory",
            description="Delete a specific memory by its ID. Use this to remove outdated or "
                        "incorrect information.",
            func=_delete_memory,
            coroutine=_delete_memory,
            args_schema=DeleteMemoryInput,
        ),
    ]
