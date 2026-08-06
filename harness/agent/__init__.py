"""Harness Framework — Agent Layer.

Provides:
- create_harness_agent(): DeepAgents-powered agent factory
- HarnessAgent: Fallback agent using custom LangGraph loop
- Custom middleware: Intent routing, session tracking, skill execution
"""

from .factory import (
    create_harness_agent,
    HARNESS_SYSTEM_PROMPT,
    get_default_subagents,
)
from .loop import HarnessAgent, harness_agent, build_agent_graph
from .middleware import (
    IntentRoutingMiddleware,
    SessionTrackingMiddleware,
    SkillExecutionMiddleware,
)

__all__ = [
    "create_harness_agent",
    "HARNESS_SYSTEM_PROMPT",
    "get_default_subagents",
    "HarnessAgent",
    "harness_agent",
    "build_agent_graph",
    "IntentRoutingMiddleware",
    "SessionTrackingMiddleware",
    "SkillExecutionMiddleware",
]
