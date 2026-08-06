"""Harness Framework — Custom Span Definitions.

Pre-defined span trackers for key business logic points:
- Intent routing
- Skill execution
- MCP tool calls
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from .tracer import get_tracer


# ══════════════════════════════════════════════════════════
# Intent Routing Span
# ══════════════════════════════════════════════════════════


@contextmanager
def track_intent_routing(user_input: str, router=None):
    """Track an intent routing operation.

    Usage:
        with track_intent_routing("parse this report") as span:
            intent, confidence, skill = router.route_single(user_input)
            span.update(output={"intent": intent, "confidence": confidence})
    """
    tracer = get_tracer()
    with tracer.span(
        "intent_routing",
        input_data={"user_input": user_input[:200]},
        metadata={"type": "intent_routing"},
    ) as span:
        yield span


# ══════════════════════════════════════════════════════════
# Skill Execution Span
# ══════════════════════════════════════════════════════════


@contextmanager
def track_skill_execution(skill_name: str, input_data: dict | None = None):
    """Track a skill execution.

    Usage:
        with track_skill_execution("report_parser", {"file_path": "..."}) as span:
            result = await skill.execute(context)
            span.update(output=result.to_dict())
    """
    tracer = get_tracer()
    with tracer.span(
        f"skill:{skill_name}",
        input_data=input_data,
        metadata={"type": "skill_execution", "skill_name": skill_name},
    ) as span:
        yield span


# ══════════════════════════════════════════════════════════
# MCP Call Span
# ══════════════════════════════════════════════════════════


@contextmanager
def track_mcp_call(tool_name: str, arguments: dict | None = None):
    """Track an MCP tool call.

    Usage:
        with track_mcp_call("parse_document", {"file_path": "..."}) as span:
            result = await mcp_registry.call_tool("parse_document", args)
            span.update(output=result)
    """
    tracer = get_tracer()
    with tracer.span(
        f"mcp:{tool_name}",
        input_data=arguments,
        metadata={"type": "mcp_call", "tool_name": tool_name},
    ) as span:
        yield span
