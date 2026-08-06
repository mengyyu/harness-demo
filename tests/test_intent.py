"""Tests for the Intent Router."""

import pytest
from harness.intent.router import IntentRouter, IntentRule


class TestIntentRouter:
    @pytest.fixture
    def router(self):
        r = IntentRouter()
        # Clear defaults and add test intents
        r.intents.clear()
        r.add_intent(IntentRule(
            name="parse_report",
            description="Parse reports",
            keywords=["解析", "报告", "基金"],
            bound_skill="report_parser",
            priority=10,
        ))
        r.add_intent(IntentRule(
            name="generate_summary",
            description="Generate summary",
            keywords=["总结", "汇总", "持仓"],
            negative_keywords=["解析"],
            bound_skill="summary_generator",
            priority=10,
        ))
        return r

    def test_single_route(self, router):
        intent, confidence, skill = router.route_single("帮我解析这份基金诊断报告")
        assert intent == "parse_report"
        assert confidence > 0
        assert skill == "report_parser"

    def test_route_summary(self, router):
        intent, confidence, skill = router.route_single("生成持仓总结")
        assert intent == "generate_summary"
        assert skill == "summary_generator"

    def test_negative_keyword(self, router):
        # "解析" is a negative keyword for generate_summary
        intent, confidence, skill = router.route_single("解析这份报告并生成总结")
        assert intent == "parse_report"  # parse_report should win

    def test_unknown_intent(self, router):
        intent, confidence, skill = router.route_single("abc def ghi jkl mno pqr stu vwx yz")
        assert intent == "unknown"
        assert confidence == 0.0

    def test_multi_route(self, router):
        intents, confidences, skills = router.route("解析基金报告并生成持仓总结")
        assert len(intents) > 0

    def test_disable_intent(self, router):
        router.update_intent("parse_report", is_active=False)
        intent, confidence, skill = router.route_single("帮我解析这份基金诊断报告")
        assert intent != "parse_report"  # Should not match disabled intent

    def test_crud(self, router):
        router.add_intent(IntentRule(name="test", description="Test", keywords=["测试"]))
        assert router.get_intent("test") is not None

        router.update_intent("test", description="Updated")
        assert router.get_intent("test").description == "Updated"

        router.delete_intent("test")
        assert router.get_intent("test") is None
