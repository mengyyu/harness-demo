"""Harness Framework — Memory System.

Provides:
- Mem0Client: Persistent semantic memory via Mem0 (with in-memory fallback)
- MemoryStore: In-memory three-tier memory (fallback)
- Memory tools: LangChain tools for agent memory management
"""

from .store import MemoryStore, memory_store

# Lazy imports for heavy optional dependencies
__all__ = [
    "MemoryStore",
    "memory_store",
    "Mem0Client",
    "create_memory_tools",
]


def __getattr__(name: str):
    if name == "Mem0Client":
        from .client import Mem0Client
        return Mem0Client
    if name == "create_memory_tools":
        from .tools import create_memory_tools
        return create_memory_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
