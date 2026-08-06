"""Tests for the Skill System."""

import pytest
from harness.skills.base import (
    BaseSkill,
    SkillManifest,
    SkillContext,
    SkillResult,
    SkillStatus,
)


class TestSkillManifest:
    def test_create_valid_manifest(self):
        manifest = SkillManifest(
            name="test_skill",
            version="1.0.0",
            description="A test skill",
            intents=["test_intent"],
        )
        assert manifest.name == "test_skill"
        assert manifest.version == "1.0.0"

    def test_default_values(self):
        manifest = SkillManifest(name="minimal")
        assert manifest.version == "1.0.0"
        assert manifest.timeout == 300
        assert manifest.intents == []


class TestSkillContext:
    def test_create_context(self):
        ctx = SkillContext(
            session_id="s1",
            user_id="u1",
            intent="test_intent",
            params={"key": "value"},
        )
        assert ctx.session_id == "s1"
        assert ctx.user_id == "u1"
        assert ctx.params == {"key": "value"}

    def test_default_values(self):
        ctx = SkillContext(session_id="s1")
        assert ctx.user_id == "default"
        assert ctx.intent == ""


class TestSkillResult:
    def test_success_result(self):
        result = SkillResult(
            success=True,
            skill_name="test",
            data={"output": "hello"},
            summary="Test completed",
        )
        assert result.success is True
        assert result.summary == "Test completed"

    def test_failure_result(self):
        result = SkillResult(
            success=False,
            skill_name="test",
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestSkillRegistry:
    def test_register_skill(self):
        from harness.skills.registry import SkillRegistry
        registry = SkillRegistry()

        class TestSkill(BaseSkill):
            async def execute(self, context):
                return SkillResult(success=True, skill_name=self.name)

        manifest = SkillManifest(name="test_skill", version="1.0.0")
        skill = TestSkill(manifest)
        registry.register(skill)

        assert registry.get("test_skill") is skill
        assert len(registry.list_all()) == 1

    def test_find_by_intent(self):
        from harness.skills.registry import SkillRegistry
        registry = SkillRegistry()

        class TestSkill(BaseSkill):
            async def execute(self, context):
                return SkillResult(success=True, skill_name=self.name)

        manifest = SkillManifest(name="test_skill", intents=["parse_report"])
        skill = TestSkill(manifest)
        registry.register(skill)

        matched = registry.get_by_intent("parse_report")
        assert len(matched) == 1
        assert matched[0].name == "test_skill"

        unmatched = registry.get_by_intent("unknown_intent")
        assert len(unmatched) == 0
