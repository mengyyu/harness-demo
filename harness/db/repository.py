"""Harness Framework — Data Repository (CRUD abstraction over SQLAlchemy)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .engine import get_session
from .models import (
    AgentRun,
    AgentStep,
    SkillRun,
    SkillDefinition,
    IntentDefinition,
)

# ─────────────────────────────────────────────────────────────
# Agent Runs
# ─────────────────────────────────────────────────────────────


class AgentRunRepository:
    """CRUD operations for AgentRun records."""

    @staticmethod
    def create(
        session: Session,
        session_id: str,
        user_id: str | None = None,
        input_text: str = "",
        agent_name: str = "harness",
    ) -> AgentRun:
        run = AgentRun(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            session_id=session_id,
            user_id=user_id,
            input_preview=input_text[:500],
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.commit()
        return run

    @staticmethod
    def update(
        session: Session,
        run_id: str,
        **kwargs,
    ) -> AgentRun | None:
        run = session.query(AgentRun).filter_by(id=run_id).first()
        if not run:
            return None
        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)
        session.commit()
        return run

    @staticmethod
    def finish(
        session: Session,
        run_id: str,
        status: str = "success",
        output_text: str = "",
        error: str | None = None,
        total_tokens: int = 0,
        total_cost: float = 0.0,
        latency_ms: float = 0.0,
    ) -> AgentRun | None:
        return AgentRunRepository.update(
            session,
            run_id,
            status=status,
            output_preview=output_text[:1000] if output_text else "",
            error_message=error,
            total_tokens=total_tokens,
            total_cost=total_cost,
            latency_ms=latency_ms,
            finished_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def get_recent(
        session: Session,
        limit: int = 50,
        skill_name: str | None = None,
        status: str | None = None,
        hours: int | None = None,
    ) -> list[AgentRun]:
        q = session.query(AgentRun)
        if skill_name:
            q = q.filter_by(skill_name=skill_name)
        if status:
            q = q.filter_by(status=status)
        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            q = q.filter(AgentRun.created_at >= cutoff)
        return q.order_by(AgentRun.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_stats(
        session: Session,
        hours: int = 24,
    ) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        total = session.query(func.count(AgentRun.id)).filter(
            AgentRun.created_at >= cutoff
        ).scalar() or 0

        success = session.query(func.count(AgentRun.id)).filter(
            AgentRun.created_at >= cutoff,
            AgentRun.status == "success",
        ).scalar() or 0

        failed = session.query(func.count(AgentRun.id)).filter(
            AgentRun.created_at >= cutoff,
            AgentRun.status == "failed",
        ).scalar() or 0

        avg_latency = session.query(func.avg(AgentRun.latency_ms)).filter(
            AgentRun.created_at >= cutoff,
            AgentRun.latency_ms > 0,
        ).scalar() or 0.0

        avg_tokens = session.query(func.avg(AgentRun.total_tokens)).filter(
            AgentRun.created_at >= cutoff,
        ).scalar() or 0.0

        total_cost = session.query(func.sum(AgentRun.total_cost)).filter(
            AgentRun.created_at >= cutoff,
        ).scalar() or 0.0

        return {
            "period_hours": hours,
            "total_executions": total,
            "success_count": success,
            "failed_count": failed,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_tokens_per_run": round(avg_tokens, 1),
            "total_cost": round(total_cost, 6),
        }


# ─────────────────────────────────────────────────────────────
# Agent Steps
# ─────────────────────────────────────────────────────────────


class AgentStepRepository:
    """CRUD operations for AgentStep records."""

    @staticmethod
    def create(
        session: Session,
        run_id: str,
        step_number: int,
        step_type: str,
        step_name: str | None = None,
        content: str | None = None,
        tool_name: str | None = None,
        tool_input: dict | None = None,
        tool_output: str | None = None,
        duration_ms: int | None = None,
        token_count: int | None = None,
    ) -> AgentStep:
        step = AgentStep(
            id=str(uuid.uuid4()),
            run_id=run_id,
            step_number=step_number,
            step_type=step_type,
            step_name=step_name,
            content=content,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
            token_count=token_count,
        )
        session.add(step)
        session.commit()
        return step

    @staticmethod
    def get_by_run(session: Session, run_id: str) -> list[AgentStep]:
        return (
            session.query(AgentStep)
            .filter_by(run_id=run_id)
            .order_by(AgentStep.step_number)
            .all()
        )


# ─────────────────────────────────────────────────────────────
# Skill Runs
# ─────────────────────────────────────────────────────────────


class SkillRunRepository:
    """CRUD operations for SkillRun records."""

    @staticmethod
    def create(
        session: Session,
        skill_name: str,
        run_id: str,
        session_id: str | None = None,
        user_id: str | None = None,
        input_data: dict | None = None,
    ) -> SkillRun:
        skill_run = SkillRun(
            id=str(uuid.uuid4()),
            skill_name=skill_name,
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            input_data=input_data,
            status="running",
        )
        session.add(skill_run)
        session.commit()
        return skill_run

    @staticmethod
    def finish(
        session: Session,
        skill_run_id: str,
        status: str = "success",
        output_data: dict | None = None,
        error: str | None = None,
        duration_ms: int = 0,
        token_count: int = 0,
    ) -> SkillRun | None:
        run = session.query(SkillRun).filter_by(id=skill_run_id).first()
        if not run:
            return None
        run.status = status
        run.output_data = output_data
        run.error_message = error
        run.duration_ms = duration_ms
        run.token_count = token_count
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        return run

    @staticmethod
    def get_stats_by_skill(
        session: Session,
        skill_name: str | None = None,
        hours: int = 168,
    ) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = session.query(
            SkillRun.skill_name,
            func.count(SkillRun.id).label("total"),
            func.sum(
                func.case((SkillRun.status == "success", 1), else_=0)
            ).label("success_count"),
            func.avg(SkillRun.duration_ms).label("avg_duration"),
        ).filter(SkillRun.created_at >= cutoff)

        if skill_name:
            q = q.filter(SkillRun.skill_name == skill_name)

        q = q.group_by(SkillRun.skill_name).order_by(func.count(SkillRun.id).desc())

        return [
            {
                "skill_name": row.skill_name,
                "total": row.total,
                "success": row.success_count or 0,
                "failed": (row.total - (row.success_count or 0)),
                "success_rate": round(
                    (row.success_count or 0) / row.total * 100, 1
                ) if row.total else 0,
                "avg_duration_ms": round(row.avg_duration or 0, 1),
            }
            for row in q.all()
        ]


# ══════════════════════════════════════════════════════════════
# Unified Repository (convenience accessor)
# ══════════════════════════════════════════════════════════════


class Repository:
    """Unified repository providing access to all entity repositories."""

    agent_runs = AgentRunRepository
    agent_steps = AgentStepRepository
    skill_runs = SkillRunRepository
