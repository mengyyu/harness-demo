"""Tests for the Database Layer."""

import pytest
import tempfile
import os


class TestDatabaseModels:
    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing."""
        from harness.db.engine import init_db, get_session
        db_path = os.path.join(tempfile.gettempdir(), "test_harness.db")
        db_url = f"sqlite:///{db_path}"

        init_db(db_url)
        with get_session() as session:
            yield session

        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_create_agent_run(self, db_session):
        from harness.db.repository import AgentRunRepository

        run = AgentRunRepository.create(
            db_session,
            session_id="test-session-1",
            user_id="user-1",
            input_text="Test input",
        )
        assert run.id is not None
        assert run.status == "running"
        assert run.session_id == "test-session-1"

        # Finish the run
        AgentRunRepository.finish(
            db_session,
            run.id,
            status="success",
            output_text="Test output",
            latency_ms=1234,
            total_tokens=500,
        )

        # Verify
        from harness.db.models import AgentRun
        updated = db_session.query(AgentRun).filter_by(id=run.id).first()
        assert updated.status == "success"
        assert updated.output_preview == "Test output"
        assert updated.latency_ms == 1234
        assert updated.total_tokens == 500

    def test_create_agent_step(self, db_session):
        from harness.db.repository import AgentRunRepository, AgentStepRepository

        run = AgentRunRepository.create(
            db_session, session_id="s1", input_text="Test"
        )

        step = AgentStepRepository.create(
            db_session,
            run_id=run.id,
            step_number=1,
            step_type="action",
            step_name="intent_route",
            tool_name="router",
            duration_ms=50,
        )
        assert step.id is not None
        assert step.run_id == run.id
        assert step.step_number == 1

    def test_create_skill_run(self, db_session):
        from harness.db.repository import SkillRunRepository

        run = SkillRunRepository.create(
            db_session,
            skill_name="report_parser",
            run_id="run-1",
            session_id="session-1",
        )
        assert run.id is not None
        assert run.skill_name == "report_parser"
        assert run.status == "running"

        SkillRunRepository.finish(
            db_session,
            run.id,
            status="success",
            duration_ms=500,
            token_count=200,
        )

        from harness.db.models import SkillRun
        updated = db_session.query(SkillRun).filter_by(id=run.id).first()
        assert updated.status == "success"
        assert updated.duration_ms == 500

    def test_get_stats(self, db_session):
        from harness.db.repository import AgentRunRepository
        import time

        # Create some runs
        AgentRunRepository.create(db_session, session_id="s1", input_text="Test 1")
        time.sleep(0.1)
        AgentRunRepository.create(db_session, session_id="s2", input_text="Test 2")

        stats = AgentRunRepository.get_stats(db_session, hours=24)
        assert stats["total_executions"] >= 2
        assert "success_rate" in stats
        assert "avg_latency_ms" in stats
