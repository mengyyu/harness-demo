"""Harness Framework — MCP Management API.

GET /admin/mcp/servers  — List MCP servers and status
GET /admin/mcp/tools    — List all MCP tools
POST /admin/mcp/refresh — Re-discover tools from servers
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/admin/mcp", tags=["admin-mcp"])


@router.get("/servers")
async def get_mcp_servers():
    """Get all MCP server statuses."""
    try:
        from harness.mcp.registry import mcp_registry
        return mcp_registry.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_mcp_tools(
    server_name: Optional[str] = Query(default=None),
):
    """List all registered MCP tools, optionally filtered by server."""
    try:
        from harness.mcp.registry import mcp_registry
        return {
            "tools": mcp_registry.list_tools(server_name=server_name),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_mcp_tools():
    """Re-discover tools from all connected MCP servers."""
    try:
        from harness.mcp.registry import mcp_registry
        await mcp_registry.connect_all()
        return mcp_registry.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
