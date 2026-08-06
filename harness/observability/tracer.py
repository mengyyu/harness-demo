"""Harness Framework — LangFuse Tracer.

Provides a unified observability layer using LangFuse for:
- Automatic LangChain/LangGraph trace capture
- Custom business-logic spans (intent routing, skill execution)
- Token usage and cost tracking
- Metric aggregation for admin dashboards
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

_langfuse_client = None
_callback_handler = None


def _get_langfuse_client():
    """Lazy-load the LangFuse client."""
    global _langfuse_client
    if _langfuse_client is None and settings.LANGFUSE_ENABLED:
        try:
            from langfuse import get_client
            _langfuse_client = get_client()
            logger.info("LangFuse client initialized")
        except ImportError:
            logger.warning("langfuse package not installed; observability disabled")
            settings.LANGFUSE_ENABLED = False
        except Exception as e:
            logger.error("Failed to initialize LangFuse: %s", e)
            settings.LANGFUSE_ENABLED = False
    return _langfuse_client


def get_callback_handler() -> Any | None:
    """Get the LangFuse CallbackHandler for LangChain/LangGraph integration.

    Returns None if LangFuse is not enabled or not installed.
    """
    global _callback_handler
    if not settings.LANGFUSE_ENABLED:
        return None

    if _callback_handler is None:
        try:
            from langfuse.langchain import CallbackHandler
            _callback_handler = CallbackHandler()
        except ImportError:
            logger.warning("langfuse.langchain not available")
            return None

    return _callback_handler


# ══════════════════════════════════════════════════════════
# Harness Tracer
# ══════════════════════════════════════════════════════════


class HarnessTracer:
    """Unified tracer for Harness agent execution.

    Combines LangFuse automatic tracing with custom business-logic spans.
    Falls back to local DB tracking when LangFuse is not available.

    Usage:
        tracer = HarnessTracer()

        # As context manager for a custom span
        with tracer.span("intent_routing", input={"query": "..."}) as span:
            result = router.route(query)
            span.update(output=result)

        # Track a session
        tracer.start_session(session_id="s1", user_id="u1", input="...")
        ...
        tracer.end_session(session_id="s1", status="success", output="...")
    """

    def __init__(self):
        self._lf = _get_langfuse_client() if settings.LANGFUSE_ENABLED else None
        self._handler = get_callback_handler()
        self._active_sessions: dict[str, dict] = {}

    @property
    def is_enabled(self) -> bool:
        return settings.LANGFUSE_ENABLED and self._lf is not None

    @property
    def callback_handler(self):
        return self._handler

    # ── Session Management ───────────────────────────────

    def start_session(
        self,
        session_id: str,
        user_id: str = "default",
        input_text: str = "",
        metadata: dict | None = None,
    ):
        """Start tracking an agent execution session."""
        self._active_sessions[session_id] = {
            "user_id": user_id,
            "input_text": input_text,
            "start_time": time.time(),
            "metadata": metadata or {},
            "steps": [],
        }

        if self.is_enabled:
            try:
                trace = self._lf.trace(
                    name="harness-agent-run",
                    user_id=user_id,
                    session_id=session_id,
                    input=input_text,
                    metadata=metadata,
                )
                self._active_sessions[session_id]["trace"] = trace
            except Exception as e:
                logger.warning("LangFuse trace creation failed: %s", e)

    def end_session(
        self,
        session_id: str,
        status: str = "success",
        output_text: str = "",
        error: str | None = None,
        tokens: int = 0,
        cost: float = 0.0,
    ):
        """End an agent execution session."""
        session_data = self._active_sessions.pop(session_id, None)
        if not session_data:
            return

        elapsed = time.time() - session_data["start_time"]

        # Update LangFuse trace
        if self.is_enabled:
            trace = session_data.get("trace")
            if trace:
                try:
                    trace.update(
                        output=output_text,
                        metadata={
                            "status": status,
                            "error": error,
                            "latency_ms": elapsed * 1000,
                            "tokens": tokens,
                            "cost": cost,
                            "steps": len(session_data["steps"]),
                        },
                    )
                except Exception as e:
                    logger.warning("LangFuse trace update failed: %s", e)

        # Also persist to local DB
        try:
            from harness.db.engine import get_session as db_session
            from harness.db.repository import AgentRunRepository

            with db_session() as s:
                run = AgentRunRepository.create(
                    s,
                    session_id=session_id,
                    user_id=session_data["user_id"],
                    input_text=session_data["input_text"],
                )
                AgentRunRepository.finish(
                    s,
                    run.id,
                    status=status,
                    output_text=output_text,
                    error=error,
                    total_tokens=tokens,
                    total_cost=cost,
                    latency_ms=elapsed * 1000,
                )
        except Exception as e:
            logger.debug("DB session recording failed: %s", e)

    # ── Span Management ──────────────────────────────────

    @contextmanager
    def span(self, name: str, input_data: Any = None, metadata: dict | None = None):
        """Create a custom span for business logic tracking.

        Usage:
            with tracer.span("intent_routing", input_data={"query": q}) as span:
                result = do_routing(q)
                span.update(output=result)
        """
        span_data: dict = {
            "name": name,
            "input": input_data,
            "metadata": metadata or {},
            "start_time": time.time(),
        }

        # LangFuse span
        lf_span = None
        if self.is_enabled:
            try:
                lf_span = self._lf.span(
                    name=name,
                    input=input_data,
                    metadata=metadata,
                )
            except Exception:
                pass

        # Create a mutable container for the output
        span_container = {"output": None, "error": None}

        class SpanHandle:
            def update(self, output=None, error=None, **kwargs):
                span_container["output"] = output
                span_container["error"] = error
                span_data["metadata"].update(kwargs)

        handle = SpanHandle()

        try:
            yield handle
        except Exception as e:
            span_container["error"] = str(e)
            raise
        finally:
            elapsed = time.time() - span_data["start_time"]
            if lf_span:
                try:
                    lf_span.update(
                        output=span_container["output"],
                        metadata={
                            "latency_ms": elapsed * 1000,
                            "error": span_container["error"],
                            **span_data["metadata"],
                        },
                    )
                except Exception:
                    pass

    # ── Score Recording ──────────────────────────────────

    def record_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ):
        """Record an evaluation score for a trace."""
        if self.is_enabled:
            try:
                self._lf.score(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                    comment=comment,
                )
            except Exception as e:
                logger.warning("LangFuse score recording failed: %s", e)

    # ── Report Queries ───────────────────────────────────

    def get_execution_records(
        self,
        limit: int = 50,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Get recent execution records.

        Tries LangFuse first, falls back to local DB.
        """
        try:
            from harness.db.engine import get_session as db_session
            from harness.db.repository import AgentRunRepository

            with db_session() as s:
                runs = AgentRunRepository.get_recent(
                    s, limit=limit, status=status
                )
                return [
                    {
                        "record_id": r.id,
                        "session_id": r.session_id,
                        "user_id": r.user_id,
                        "intent": r.intent,
                        "skill_name": r.skill_name,
                        "status": r.status,
                        "input_text": r.input_preview or "",
                        "output_text": r.output_preview or "",
                        "latency_ms": r.latency_ms,
                        "total_tokens": r.total_tokens,
                        "total_cost": r.total_cost,
                        "steps_count": r.total_steps,
                        "timestamp": r.created_at.isoformat() if r.created_at else "",
                        "error": r.error_message,
                        "langfuse_trace_id": r.langfuse_trace_id,
                    }
                    for r in runs
                ]
        except Exception as e:
            logger.warning("DB query failed: %s", e)
            return []

    def get_agent_report(self, hours: int = 24) -> dict:
        """Get aggregated agent execution report."""
        try:
            from harness.db.engine import get_session as db_session
            from harness.db.repository import AgentRunRepository

            with db_session() as s:
                return AgentRunRepository.get_stats(s, hours=hours)
        except Exception as e:
            logger.warning("Agent report query failed: %s", e)
            return {"error": str(e)}

    def get_skill_report(self, skill_name: str | None = None, hours: int = 168) -> dict:
        """Get aggregated skill execution report."""
        try:
            from harness.db.engine import get_session as db_session
            from harness.db.repository import SkillRunRepository

            with db_session() as s:
                stats = SkillRunRepository.get_stats_by_skill(
                    s, skill_name=skill_name, hours=hours
                )
                return {
                    "skill_name": skill_name or "all",
                    "period_hours": hours,
                    "skill_stats": stats,
                }
        except Exception as e:
            logger.warning("Skill report query failed: %s", e)
            return {"error": str(e)}


# ══════════════════════════════════════════════════════════
# Global Instance
# ══════════════════════════════════════════════════════════

_tracer_instance: HarnessTracer | None = None


def get_tracer() -> HarnessTracer:
    """Get the global HarnessTracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = HarnessTracer()
    return _tracer_instance
