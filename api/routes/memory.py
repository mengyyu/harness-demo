"""Harness Framework — Memory Management API.

GET    /admin/memory            — List memories
GET    /admin/memory/stats      — Memory statistics
GET    /admin/memory/search     — Semantic search memories
DELETE /admin/memory/{id}       — Delete a memory
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/admin/memory", tags=["admin-memory"])


# Lazy-init the memory client
_memory_client = None


def _get_memory_client():
    global _memory_client
    if _memory_client is None:
        from harness.memory.client import Mem0Client
        _memory_client = Mem0Client()
    return _memory_client


@router.get("")
async def get_memories(
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Get memory entries, optionally filtered by user."""
    try:
        client = _get_memory_client()
        memories = client.get_all(user_id=user_id)
        return {"total": len(memories), "memories": memories[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_memory_stats():
    """Get memory system statistics (counts by layer/type)."""
    try:
        client = _get_memory_client()
        return client.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_memories(
    query: str = Query(..., min_length=1),
    user_id: str = Query(default="default"),
    top_k: int = Query(default=10, ge=1, le=50),
):
    """Semantic search through stored memories."""
    try:
        client = _get_memory_client()
        results = client.search(query=query, user_id=user_id, top_k=top_k)
        return {"query": query, "total": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory entry by ID."""
    try:
        client = _get_memory_client()
        success = client.delete(memory_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found")
        return {"status": "success", "memory_id": memory_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session_memories(session_id: str):
    """Clear all memories for a specific session."""
    try:
        client = _get_memory_client()
        count = client.clear_session(session_id)
        return {"status": "success", "deleted": count, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
