"""Harness Framework — Metrics Aggregator.

Provides aggregated metrics for admin dashboards and reports.
Queries both LangFuse (when available) and local DB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregate metrics from DB and LangFuse for dashboard display."""

    def __init__(self):
        self._db = None

    @property
    def db_session(self):
        if self._db is None:
            from harness.db.engine import get_session
            self._db = get_session
        return self._db

    # ── Agent Metrics ────────────────────────────────────

    def get_agent_dashboard_metrics(self, hours: int = 24) -> dict:
        """Get key metrics for the admin dashboard.

        Returns:
            Dict with: total_executions, success_rate, avg_latency_ms,
                       total_tokens, total_cost, intent_distribution,
                       executions_by_hour.
        """
        try:
            from harness.db.repository import AgentRunRepository

            with self.db_session() as s:
                stats = AgentRunRepository.get_stats(s, hours=hours)

                # Intent distribution
                from harness.db.models import AgentRun
                from sqlalchemy import func

                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                intent_rows = (
                    s.query(
                        AgentRun.intent,
                        func.count(AgentRun.id).label("count"),
                    )
                    .filter(AgentRun.created_at >= cutoff)
                    .group_by(AgentRun.intent)
                    .order_by(func.count(AgentRun.id).desc())
                    .all()
                )
                intent_dist = {
                    row.intent or "unknown": row.count
                    for row in intent_rows
                }

                return {
                    **stats,
                    "intent_distribution": intent_dist,
                }
        except Exception as e:
            logger.warning("Dashboard metrics query failed: %s", e)
            return {
                "total_executions": 0,
                "success_rate": 0,
                "avg_latency_ms": 0,
                "error": str(e),
            }

    def get_skill_dashboard_metrics(self, hours: int = 168) -> list[dict]:
        """Get per-skill metrics for the admin dashboard.

        Returns:
            List of dicts with: skill_name, total, success, failed,
                                success_rate, avg_duration_ms.
        """
        try:
            from harness.db.repository import SkillRunRepository

            with self.db_session() as s:
                return SkillRunRepository.get_stats_by_skill(s, hours=hours)
        except Exception as e:
            logger.warning("Skill metrics query failed: %s", e)
            return []

    def get_recent_executions(
        self,
        limit: int = 20,
        skill_name: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """Get recent execution records for the runs list view."""
        try:
            from harness.db.repository import AgentRunRepository

            with self.db_session() as s:
                runs = AgentRunRepository.get_recent(
                    s,
                    limit=limit,
                    skill_name=skill_name,
                    status=status,
                )
                return [
                    {
                        "id": r.id,
                        "session_id": r.session_id,
                        "intent": r.intent,
                        "skill_name": r.skill_name,
                        "status": r.status,
                        "input_preview": r.input_preview,
                        "output_preview": r.output_preview,
                        "latency_ms": r.latency_ms,
                        "total_tokens": r.total_tokens,
                        "total_cost": r.total_cost,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                    }
                    for r in runs
                ]
        except Exception as e:
            logger.warning("Recent executions query failed: %s", e)
            return []

    # ── System Health ────────────────────────────────────

    def get_system_health(self) -> dict:
        """Get overall system health status."""
        try:
            from harness.db.engine import get_engine
            engine = get_engine()

            # Check DB connectivity
            db_ok = False
            try:
                with engine.connect() as conn:
                    conn.execute(import_=None)
                    db_ok = True
            except Exception:
                pass

            return {
                "database": "connected" if db_ok else "disconnected",
                "langfuse_enabled": _check_langfuse(),
                "mem0_enabled": _check_mem0(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Helpers ──────────────────────────────────────────────


def _check_langfuse() -> bool:
    try:
        from config.settings import settings
        if not settings.LANGFUSE_ENABLED:
            return False
        from langfuse import get_client
        client = get_client()
        return client.auth_check()
    except Exception:
        return False


def _check_mem0() -> bool:
    try:
        from config.settings import settings
        return settings.MEM0_ENABLED
    except Exception:
        return False
