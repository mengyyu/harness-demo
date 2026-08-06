"""Harness Framework — Skill Lifecycle Manager.

Manages skill loading, registration, execution tracking,
and database synchronization.
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import BaseSkill, SkillContext, SkillResult, SkillStatus
from .registry import skill_registry

logger = logging.getLogger(__name__)


class SkillManager:
    """Central manager for skill lifecycle.

    Coordinates:
    - Loading skills from disk
    - Registering with the skill registry
    - Tracking executions in the database
    - Enabling/disabling skills
    - Syncing definitions to DB
    """

    def __init__(self):
        self._mcp_manager = None
        self._registry = skill_registry

    # ── MCP Injection ────────────────────────────────────

    def inject_mcp(self, mcp_manager):
        """Inject MCP manager into all registered skills."""
        self._mcp_manager = mcp_manager
        self._registry.inject_mcp(mcp_manager)

    # ── Load & Register ──────────────────────────────────

    def load_from_directory(self, skills_dir: str = "skills") -> list[str]:
        """Load all skills from a directory.

        Args:
            skills_dir: Path to the skills directory.

        Returns:
            List of skill names that were loaded.
        """
        from .loader import SkillLoader
        loader = SkillLoader(skills_dir=skills_dir)
        loaded = loader.discover_and_load()
        for skill in loaded:
            self._registry.register(skill)
        if self._mcp_manager:
            self.inject_mcp(self._mcp_manager)
        return [s.name for s in loaded]

    def register_skill(self, skill: BaseSkill):
        """Register a single skill instance."""
        self._registry.register(skill)
        if self._mcp_manager:
            skill.set_mcp_manager(self._mcp_manager)

    def unregister_skill(self, name: str) -> bool:
        """Unregister a skill by name."""
        return self._registry.unregister(name)

    # ── Enable / Disable ─────────────────────────────────

    def enable_skill(self, name: str) -> bool:
        """Enable a skill."""
        skill = self._registry.get(name)
        if not skill:
            return False
        skill.status = SkillStatus.ACTIVE
        return True

    def disable_skill(self, name: str) -> bool:
        """Disable a skill."""
        skill = self._registry.get(name)
        if not skill:
            return False
        skill.status = SkillStatus.DISABLED
        return True

    def toggle_skill(self, name: str) -> dict:
        """Toggle a skill's active status.

        Returns:
            Dict with skill name and new status.
        """
        skill = self._registry.get(name)
        if not skill:
            return {"error": f"Skill '{name}' not found"}

        if skill.status == SkillStatus.ACTIVE:
            skill.status = SkillStatus.DISABLED
        else:
            skill.status = SkillStatus.ACTIVE

        return {"skill_name": name, "status": skill.status.value}

    # ── Query ────────────────────────────────────────────

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name."""
        return self._registry.get(name)

    def list_skills(self) -> list[BaseSkill]:
        """List all registered skills."""
        return self._registry.list_all()

    def get_stats(self) -> list[dict]:
        """Get all skill stats."""
        return self._registry.get_stats()

    def find_by_intent(self, intent: str) -> list[BaseSkill]:
        """Find skills matching an intent."""
        return self._registry.get_by_intent(intent)

    # ── DB Sync ──────────────────────────────────────────

    def sync_to_db(self):
        """Sync skill definitions to the database."""
        try:
            from harness.db.engine import get_session
            from harness.db.models import SkillDefinition as SkillDBModel

            with get_session() as session:
                for skill in self._registry.list_all():
                    existing = session.query(SkillDBModel).filter_by(
                        name=skill.name
                    ).first()
                    if existing:
                        existing.display_name = skill.manifest.description
                        existing.description = skill.manifest.description
                        existing.version = skill.manifest.version
                        existing.intents = skill.manifest.intents
                        existing.config = {
                            "timeout": skill.manifest.timeout,
                            "author": skill.manifest.author,
                        }
                        existing.enabled = skill.status == SkillStatus.ACTIVE
                    else:
                        db_skill = SkillDBModel(
                            name=skill.name,
                            display_name=skill.manifest.description,
                            description=skill.manifest.description,
                            version=skill.manifest.version,
                            module_path=f"skills.{skill.name}",
                            intents=skill.manifest.intents,
                            config={
                                "timeout": skill.manifest.timeout,
                                "author": skill.manifest.author,
                            },
                            enabled=skill.status == SkillStatus.ACTIVE,
                            author=skill.manifest.author,
                            timeout=skill.manifest.timeout,
                        )
                        session.add(db_skill)
                session.commit()
            logger.info("Synced %d skills to database", len(self._registry.list_all()))
        except Exception as e:
            logger.warning("Failed to sync skills to DB: %s", e)

    # ── Execution ────────────────────────────────────────

    async def execute_skill(
        self,
        skill_name: str,
        context: SkillContext,
    ) -> SkillResult:
        """Execute a skill and track the result.

        Args:
            skill_name: Name of the skill to execute.
            context: Execution context (session, user, params, memories).

        Returns:
            SkillResult with execution outcome.
        """
        import time

        skill = self._registry.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                skill_name=skill_name,
                error=f"Skill '{skill_name}' not found",
            )

        if skill.status != SkillStatus.ACTIVE:
            return SkillResult(
                success=False,
                skill_name=skill_name,
                error=f"Skill '{skill_name}' is {skill.status.value}",
            )

        # Track in DB
        skill_run_id = None
        try:
            from harness.db.engine import get_session
            from harness.db.repository import SkillRunRepository

            with get_session() as s:
                skill_run = SkillRunRepository.create(
                    s,
                    skill_name=skill_name,
                    run_id=context.session_id,
                    session_id=context.session_id,
                    user_id=context.user_id,
                    input_data=context.params,
                )
                skill_run_id = skill_run.id
        except Exception as e:
            logger.debug("Skill run DB tracking unavailable: %s", e)

        # Execute
        t_start = time.time()
        result = await skill.execute(context)
        elapsed_ms = int((time.time() - t_start) * 1000)

        # Update DB
        if skill_run_id:
            try:
                from harness.db.engine import get_session
                from harness.db.repository import SkillRunRepository

                with get_session() as s:
                    SkillRunRepository.finish(
                        s,
                        skill_run_id,
                        status="success" if result.success else "failed",
                        output_data=result.data,
                        error=result.error,
                        duration_ms=elapsed_ms,
                    )
            except Exception:
                pass

        return result


# Global singleton
skill_manager = SkillManager()
