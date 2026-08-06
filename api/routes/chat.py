"""Harness Framework — Chat API.

POST /chat — Main conversation endpoint.
GET /chat/stream/{session_id} — Streaming chat (SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    status: str
    intent: str
    confidence: float
    matched_skill: str
    plan: list[str]
    steps: list[dict]
    output: str
    latency_ms: float
    error: Optional[str] = None


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the Harness Agent and receive a response.

    The agent will:
    1. Detect the intent of the message
    2. Retrieve relevant memories
    3. Plan and execute the appropriate skill
    4. Return the result
    """
    from harness.agent.loop import harness_agent

    t_start = time.time()
    result = await harness_agent.run(
        user_input=request.message,
        user_id=request.user_id,
    )
    latency_ms = (time.time() - t_start) * 1000

    return ChatResponse(
        session_id=result.get("session_id", ""),
        status=result.get("status", "unknown"),
        intent=result.get("intent", ""),
        confidence=result.get("confidence", 0.0),
        matched_skill=result.get("matched_skill", ""),
        plan=result.get("plan", []),
        steps=result.get("steps", []),
        output=result.get("output", ""),
        latency_ms=round(latency_ms, 1),
        error=result.get("error"),
    )


@router.get("/stream/{session_id}")
async def chat_stream(session_id: str):
    """Stream a chat response via Server-Sent Events (future enhancement)."""
    return {"message": "Streaming not yet implemented", "session_id": session_id}
