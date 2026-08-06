"""Harness Framework — Agent Management API.

GET  /admin/agents/logs     — Agent execution logs
GET  /admin/agents/report   — Aggregated agent report
GET  /admin/agents/detail/{id} — Single run detail
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


@router.get("/logs")
async def get_agent_logs(
    limit: int = Query(default=50, ge=5, le=200),
    skill_name: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    hours: Optional[int] = Query(default=None),
):
    """Get recent agent execution logs.

    Supports filtering by skill, status, and time window.
    """
    try:
        from harness.observability.tracer import get_tracer

        tracer = get_tracer()
        records = tracer.get_execution_records(
            limit=limit,
            status=status,
        )

        # Apply skill_name filter client-side
        if skill_name:
            records = [r for r in records if r.get("skill_name") == skill_name]

        return {
            "total": len(records),
            "records": records,
        }
    except Exception as e:
        logger.error("Agent logs query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_agent_report(hours: int = Query(default=24, ge=1, le=720)):
    """Get aggregated agent execution report for the specified time window."""
    try:
        from harness.observability.tracer import get_tracer

        tracer = get_tracer()
        return tracer.get_agent_report(hours=hours)
    except Exception as e:
        logger.error("Agent report query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{run_id}")
async def get_agent_detail(run_id: str):
    """Get detailed information about a single agent run, including all steps."""
    try:
        from harness.db.engine import get_session
        from harness.db.models import AgentRun, AgentStep

        with get_session() as s:
            run = s.query(AgentRun).filter_by(id=run_id).first()
            if not run:
                raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

            steps = (
                s.query(AgentStep)
                .filter_by(run_id=run_id)
                .order_by(AgentStep.step_number)
                .all()
            )

            return {
                "run": {
                    "id": run.id,
                    "session_id": run.session_id,
                    "user_id": run.user_id,
                    "intent": run.intent,
                    "skill_name": run.skill_name,
                    "status": run.status,
                    "input_preview": run.input_preview,
                    "output_preview": run.output_preview,
                    "total_steps": run.total_steps,
                    "total_tokens": run.total_tokens,
                    "total_cost": run.total_cost,
                    "latency_ms": run.latency_ms,
                    "error": run.error_message,
                    "langfuse_trace_id": run.langfuse_trace_id,
                    "started_at": run.started_at.isoformat() if run.started_at else "",
                    "finished_at": run.finished_at.isoformat() if run.finished_at else "",
                },
                "steps": [
                    {
                        "step_number": step.step_number,
                        "step_type": step.step_type,
                        "step_name": step.step_name,
                        "content": step.content,
                        "tool_name": step.tool_name,
                        "tool_input": step.tool_input,
                        "tool_output": step.tool_output,
                        "duration_ms": step.duration_ms,
                    }
                    for step in steps
                ],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Agent detail query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
