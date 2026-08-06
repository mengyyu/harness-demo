"""Harness Framework — Custom DeepAgents Middleware.

Custom middleware components that extend the DeepAgents middleware stack
with Harness-specific functionality.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Intent Routing Middleware
# ─────────────────────────────────────────────────────────


class IntentRoutingMiddleware:
    """Pre-processes user messages to detect intent before reaching the agent.

    Injects the detected intent and matched skill into the conversation
    context so the agent can make better routing decisions.
    """

    def __init__(self, intent_router=None):
        self._router = intent_router

    @property
    def router(self):
        if self._router is None:
            from harness.intent.router import intent_router
            self._router = intent_router
        return self._router

    def before_model(self, state: dict, runtime: Any = None) -> dict | None:
        """Called before each model invocation. Injects intent context."""
        messages = state.get("messages", [])
        if not messages:
            return None

        # Only process the last user message
        last_msg = messages[-1]
        content = ""
        if hasattr(last_msg, "content"):
            content = last_msg.content
        elif isinstance(last_msg, dict):
            content = last_msg.get("content", "")

        if content and self.router:
            intent, confidence, skill = self.router.route_single(content)
            if intent != "unknown":
                # Inject as system message
                context_msg = (
                    f"[Intent Detection] Detected intent: '{intent}' "
                    f"(confidence: {confidence:.2f}), matched skill: '{skill}'"
                )
                logger.debug("IntentRouting: %s", context_msg)
                # Note: This is a conceptual middleware. Actual implementation
                # depends on the DeepAgents middleware API.

        return None


# ─────────────────────────────────────────────────────────
# Session Tracking Middleware
# ─────────────────────────────────────────────────────────


class SessionTrackingMiddleware:
    """Tracks agent execution sessions and persists records to the database.

    Records: session start/end, intent, steps, tokens, latency, errors.
    """

    def __init__(self, db_session_factory=None):
        self._db_session_factory = db_session_factory
        self._active_runs: dict[str, str] = {}  # session_id → run_id

    @property
    def db(self):
        if self._db_session_factory is None:
            from harness.db.engine import get_session as _get_session
            self._db_session_factory = _get_session
        return self._db_session_factory

    def on_session_start(self, session_id: str, user_id: str, input_text: str) -> str:
        """Record session start. Returns the DB run_id."""
        from harness.db.repository import AgentRunRepository

        with self.db() as session:
            run = AgentRunRepository.create(
                session,
                session_id=session_id,
                user_id=user_id,
                input_text=input_text,
            )
            self._active_runs[session_id] = run.id
            return run.id

    def on_session_end(
        self,
        session_id: str,
        status: str = "success",
        output_text: str = "",
        error: str | None = None,
        total_tokens: int = 0,
        total_cost: float = 0.0,
        latency_ms: float = 0.0,
    ) -> None:
        """Record session completion."""
        run_id = self._active_runs.pop(session_id, None)
        if not run_id:
            return

        from harness.db.repository import AgentRunRepository

        with self.db() as session:
            AgentRunRepository.finish(
                session,
                run_id,
                status=status,
                output_text=output_text,
                error=error,
                total_tokens=total_tokens,
                total_cost=total_cost,
                latency_ms=latency_ms,
            )

    def on_step(
        self,
        run_id: str,
        step_number: int,
        step_type: str,
        step_name: str | None = None,
        content: str | None = None,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record an execution step."""
        from harness.db.repository import AgentStepRepository

        with self.db() as session:
            AgentStepRepository.create(
                session,
                run_id=run_id,
                step_number=step_number,
                step_type=step_type,
                step_name=step_name,
                content=content,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                duration_ms=duration_ms,
            )


# ─────────────────────────────────────────────────────────
# Skill Execution Middleware
# ─────────────────────────────────────────────────────────


class SkillExecutionMiddleware:
    """Tracks skill execution and records results to the database."""

    def __init__(self, db_session_factory=None):
        self._db_session_factory = db_session_factory

    @property
    def db(self):
        if self._db_session_factory is None:
            from harness.db.engine import get_session as _get_session
            self._db_session_factory = _get_session
        return self._db_session_factory

    def on_skill_start(
        self,
        skill_name: str,
        run_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
        input_data: dict | None = None,
    ) -> str:
        """Record skill execution start. Returns skill_run_id."""
        from harness.db.repository import SkillRunRepository

        with self.db() as session:
            skill_run = SkillRunRepository.create(
                session,
                skill_name=skill_name,
                run_id=run_id,
                session_id=session_id,
                user_id=user_id,
                input_data=input_data,
            )
            return skill_run.id

    def on_skill_end(
        self,
        skill_run_id: str,
        status: str = "success",
        output_data: dict | None = None,
        error: str | None = None,
        duration_ms: int = 0,
        token_count: int = 0,
    ) -> None:
        """Record skill execution completion."""
        from harness.db.repository import SkillRunRepository

        with self.db() as session:
            SkillRunRepository.finish(
                session,
                skill_run_id,
                status=status,
                output_data=output_data,
                error=error,
                duration_ms=duration_ms,
                token_count=token_count,
            )
