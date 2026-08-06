"""Harness Framework — API Middleware.

CORS, logging, error handling, and request ID injection.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uuid

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI):
    """Configure all middleware for the FastAPI application."""

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID + Logging
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        t_start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - t_start) * 1000

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s | %d | %.1fms | %s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc) if app.debug else "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
        )
