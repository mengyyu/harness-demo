"""Harness Framework — FastAPI Application Entry Point.

Modular REST API with routes for:
- /chat — Agent conversation endpoint
- /admin/agents — Agent execution logs and reports
- /admin/skills — Skill management (CRUD, import/export)
- /admin/intents — Intent library configuration
- /admin/mcp — MCP server and tool management
- /admin/memory — Memory browsing and management
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.middleware import setup_middleware
from api.routes import chat, agents, skills, intents, mcp, memory

# ══════════════════════════════════════════════════════════
# App Factory
# ══════════════════════════════════════════════════════════


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Harness Framework API",
        description=(
            "Agent orchestration framework built on DeepAgents + LangGraph + "
            "LangChain + LangFuse + Mem0. Provides chat, admin, and management APIs."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Setup middleware (CORS, logging, error handling)
    setup_middleware(app)

    # Register route modules
    app.include_router(chat.router)
    app.include_router(agents.router)
    app.include_router(skills.router)
    app.include_router(intents.router)
    app.include_router(mcp.router)
    app.include_router(memory.router)

    # Health check
    @app.get("/health", tags=["system"])
    async def health():
        """Health check endpoint with system status."""
        from harness.skills.registry import skill_registry
        from harness.mcp.registry import mcp_registry

        return {
            "status": "ok",
            "version": "0.2.0",
            "skills_registered": len(skill_registry.list_all()),
            "mcp_servers": len(mcp_registry.get_stats().get("servers", [])),
            "mcp_tools": mcp_registry.get_stats().get("total_tools", 0),
        }

    # Root redirect
    @app.get("/", tags=["system"])
    async def root():
        return {
            "service": "Harness Framework API",
            "version": "0.2.0",
            "docs": "/docs",
            "health": "/health",
        }

    # ── Startup: Initialize Harness framework ──
    @app.on_event("startup")
    async def startup_event():
        """Initialize the Harness framework on app startup."""
        from run_demo import init_harness
        init_harness()

    return app


# ══════════════════════════════════════════════════════════
# Application Instance
# ══════════════════════════════════════════════════════════

app = create_app()

# Backward compatibility: re-export for run_demo.py and tests
__all__ = ["app", "create_app"]
