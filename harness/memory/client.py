"""Harness Framework — Mem0 Client Integration.

Provides a wrapper around Mem0 for persistent semantic memory
with fallback to the in-memory store when Mem0 is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


class Mem0Client:
    """Mem0 Memory Client — Persistent semantic memory with vector search.

    When MEM0_ENABLED=true, uses the real Mem0 library.
    When MEM0_ENABLED=false, delegates to the in-memory fallback store.

    Usage:
        client = Mem0Client()
        client.add("User prefers aggressive growth funds", user_id="user_123")
        results = client.search("investment preferences", user_id="user_123")
    """

    def __init__(self, mem0_config: dict | None = None):
        self._enabled = settings.MEM0_ENABLED
        self._memory = None
        self._fallback = None

        if self._enabled:
            self._init_mem0(mem0_config)
        else:
            logger.info("Mem0 disabled; using in-memory fallback store")
            self._init_fallback()

    def _init_mem0(self, config_override: dict | None = None):
        """Initialize the real Mem0 client."""
        try:
            from mem0 import Memory

            if config_override:
                config = config_override
            else:
                config = {
                    "vector_store": {
                        "provider": settings.MEM0_VECTOR_STORE,
                        "config": {
                            "collection_name": "mem0",
                            "path": "data/mem0_chroma",
                        },
                    },
                    "llm": {
                        "provider": settings.MEM0_LLM_PROVIDER,
                        "config": {
                            "model": settings.LLM_MODEL,
                        },
                    },
                    "embedder": {
                        "provider": settings.MEM0_EMBEDDER_PROVIDER,
                        "config": {
                            "model": "text-embedding-3-small",
                        },
                    },
                }

            self._memory = Memory.from_config(config)
            logger.info("Mem0 client initialized (vector_store=%s)", settings.MEM0_VECTOR_STORE)

        except ImportError:
            logger.warning("mem0ai package not installed; falling back to in-memory store")
            self._enabled = False
            self._init_fallback()
        except Exception as e:
            logger.error("Failed to initialize Mem0: %s; falling back to in-memory store", e)
            self._enabled = False
            self._init_fallback()

    def _init_fallback(self):
        """Initialize the in-memory fallback store."""
        from .store import memory_store as fallback
        self._fallback = fallback

    @property
    def is_enabled(self) -> bool:
        """Whether the real Mem0 backend is active."""
        return self._enabled and self._memory is not None

    # ── Core Operations ───────────────────────────────────

    def add(
        self,
        content: str,
        user_id: str = "default",
        session_id: str = "",
        agent_id: str = "harness",
        metadata: dict | None = None,
        memory_type: str = "session",
    ) -> str:
        """Add a memory entry.

        Args:
            content: The text content to remember.
            user_id: ID of the user this memory belongs to.
            session_id: Current session ID (for session-scoped memories).
            agent_id: ID of the agent creating this memory.
            metadata: Additional structured metadata.
            memory_type: Memory category (session, user, entity).

        Returns:
            Memory ID.
        """
        if self.is_enabled:
            result = self._memory.add(
                content,
                user_id=user_id,
                agent_id=agent_id,
                metadata={
                    **(metadata or {}),
                    "session_id": session_id,
                    "memory_type": memory_type,
                },
            )
            return str(result.get("id", "")) if isinstance(result, dict) else str(result)
        else:
            return self._fallback.add(
                content=content,
                user_id=user_id,
                session_id=session_id,
                memory_type=memory_type,
                metadata=metadata,
            )

    def search(
        self,
        query: str,
        user_id: str = "default",
        session_id: str = "",
        top_k: int = 10,
        **filters,
    ) -> list[dict]:
        """Search memories by semantic similarity.

        Args:
            query: Natural language search query.
            user_id: Filter by user.
            session_id: Filter by session.
            top_k: Max results to return.
            **filters: Additional Mem0 filter parameters.

        Returns:
            List of memory entries with 'id', 'memory' (content), 'score', 'metadata'.
        """
        if self.is_enabled:
            results = self._memory.search(
                query,
                user_id=user_id,
                limit=top_k,
                **filters,
            )
            return [
                {
                    "id": r.get("id", ""),
                    "content": r.get("memory", ""),
                    "score": r.get("score", 0.0),
                    "metadata": r.get("metadata", {}),
                }
                for r in (results or [])
            ]
        else:
            raw = self._fallback.search(
                query=query,
                user_id=user_id,
                session_id=session_id,
                top_k=top_k,
            )
            # Flatten the three-tier result
            flattened = []
            for layer_name in ["session_context", "user_context", "entity_context"]:
                for entry in raw.get(layer_name, []):
                    flattened.append({
                        "id": entry.get("id", ""),
                        "content": entry.get("content", ""),
                        "score": entry.get("_score", 0.0),
                        "layer": layer_name,
                        "metadata": entry.get("metadata", {}),
                    })
            return flattened

    def get_all(
        self,
        user_id: str | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """Get all memories, optionally filtered.

        Args:
            user_id: Optional user filter.
            filters: Optional additional filters.

        Returns:
            List of memory entries.
        """
        if self.is_enabled:
            return self._memory.get_all(
                user_id=user_id,
                **(filters or {}),
            )
        else:
            return self._fallback.get_all_memories(user_id=user_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry by ID.

        Args:
            memory_id: The memory ID to delete.

        Returns:
            True if deleted successfully.
        """
        if self.is_enabled:
            self._memory.delete(memory_id)
            return True
        else:
            return self._fallback.delete(memory_id)

    def clear_session(self, session_id: str) -> int:
        """Clear all memories for a specific session.

        Args:
            session_id: The session ID to clear.

        Returns:
            Number of memories deleted.
        """
        if self.is_enabled:
            # Mem0 doesn't have a native clear_session; use search + delete
            results = self._memory.search("", filters={"session_id": session_id})
            count = 0
            for r in (results or []):
                self._memory.delete(r.get("id", ""))
                count += 1
            return count
        else:
            return self._fallback.clear_session(session_id)

    def get_stats(self) -> dict:
        """Get memory store statistics."""
        if self.is_enabled:
            all_memories = self._memory.get_all()
            return {
                "backend": "mem0",
                "total_memories": len(all_memories or []),
                "vector_store": settings.MEM0_VECTOR_STORE,
            }
        else:
            stats = self._fallback.get_stats()
            stats["backend"] = "in_memory"
            return stats
