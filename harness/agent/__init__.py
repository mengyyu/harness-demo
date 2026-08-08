"""Harness Framework — Agent Layer.

Provides:
- create_harness_agent(): DeepAgents-powered agent factory
- HarnessAgent: Fallback agent using custom LangGraph loop
- Custom middleware: Intent routing, session tracking, skill execution
"""

from .loop import HarnessAgent, harness_agent, build_agent_graph

# DeepAgents factory — optional, may fail if langchain not installed
try:
    from .factory import (
        create_harness_agent,
        HARNESS_SYSTEM_PROMPT,
        get_default_subagents,
    )
    from .middleware import (
        IntentRoutingMiddleware,
        SessionTrackingMiddleware,
        SkillExecutionMiddleware,
    )
    _factory_available = True
except ImportError:
    _factory_available = False
    create_harness_agent = None
    HARNESS_SYSTEM_PROMPT = ""
    get_default_subagents = None
    IntentRoutingMiddleware = None
    SessionTrackingMiddleware = None
    SkillExecutionMiddleware = None

__all__ = [
    "HarnessAgent",
    "harness_agent",
    "build_agent_graph",
    "create_harness_agent",
    "HARNESS_SYSTEM_PROMPT",
    "get_default_subagents",
    "IntentRoutingMiddleware",
    "SessionTrackingMiddleware",
    "SkillExecutionMiddleware",
]
