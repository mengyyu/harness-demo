"""Harness Framework — Observability (LangFuse Integration).

Provides:
- HarnessTracer: LangFuse CallbackHandler + custom span management
- Custom spans for business logic (intent routing, skill execution)
- Metric aggregation for dashboards and reports
"""

from .tracer import HarnessTracer, get_tracer
from .spans import track_intent_routing, track_skill_execution, track_mcp_call
from .metrics import MetricsAggregator

__all__ = [
    "HarnessTracer",
    "get_tracer",
    "track_intent_routing",
    "track_skill_execution",
    "track_mcp_call",
    "MetricsAggregator",
]
