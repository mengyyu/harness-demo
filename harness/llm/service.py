"""Harness LLM Service — Unified LLM interface.

Supports:
- Anthropic Claude (via langchain-anthropic)
- OpenAI GPT (via langchain-openai)
- Mock fallback (zero-dependency, returns structured responses)

Usage:
    from harness.llm import get_llm
    llm = get_llm()
    response = await llm.ainvoke("Hello")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Mock LLM (fallback when no API key configured)
# ══════════════════════════════════════════════════════════


class MockLLM:
    """Mock LLM that returns structured responses for known patterns.

    Used when LLM_PROVIDER="mock" or when API key is unavailable.
    Generates realistic-looking responses based on input patterns.
    """

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """Generate a mock response based on prompt content."""
        return self._mock_response(prompt)

    def invoke(self, prompt: str, **kwargs) -> str:
        """Synchronous version."""
        return self._mock_response(prompt)

    def _mock_response(self, prompt: str) -> str:
        """Pattern-match prompt to generate appropriate response."""
        p = prompt.lower()

        # Intent classification
        if "意图" in p and "分类" in p:
            if "解析" in p or "报告" in p or "pdf" in p:
                return '{"intent": "parse_report", "confidence": 0.95}'
            elif "总结" in p or "账户" in p or "持仓" in p:
                return '{"intent": "generate_summary", "confidence": 0.92}'
            elif "状态" in p or "统计" in p:
                return '{"intent": "query_status", "confidence": 0.88}'
            return '{"intent": "unknown", "confidence": 0.5}'

        # Plan generation
        if "计划" in p and "步骤" in p:
            if "报告" in p or "解析" in p:
                return json.dumps([
                    "检测文档格式并选择合适的解析器",
                    "提取文档中的文本和表格数据",
                    "识别关键字段并结构化提取",
                    "校验提取结果的完整性和合理性",
                ], ensure_ascii=False)
            elif "总结" in p or "账户" in p:
                return json.dumps([
                    "获取客户账户分析数据",
                    "获取私募持仓报告数据",
                    "对齐两份数据的时间维度和资产分类",
                    "基于数据生成综合性投资总结",
                ], ensure_ascii=False)
            return json.dumps(["分析用户需求", "执行对应操作", "返回结果"], ensure_ascii=False)

        # Report extraction
        if "基金" in p and ("提取" in p or "字段" in p or "结构化" in p):
            return json.dumps({
                "fund_name": "演示稳健增长混合型基金",
                "fund_code": "DEMO001",
                "fund_manager": "张三",
                "diagnosis_date": "2024-06-30",
                "performance_metrics": {
                    "return_1m": 2.35, "return_3m": 5.82, "return_1y": 15.67,
                    "annual_volatility": 18.5, "sharpe_ratio": 1.23, "max_drawdown": -15.8,
                },
                "risk_assessment": {"risk_level": "R3", "risk_score": 65},
                "holdings_analysis": {
                    "sector_distribution": {"消费": 28.5, "科技": 22.3, "金融": 18.7},
                    "concentration_ratio": 0.35,
                },
                "diagnosis_conclusion": {
                    "overall_score": 78,
                    "strengths": ["行业配置均衡", "风控能力较强"],
                    "weaknesses": ["近期换手率偏高"],
                    "suggestions": ["维持当前配置", "关注科技板块估值回调风险"],
                },
            }, ensure_ascii=False)

        # Summary generation
        if "总结" in p and ("账户" in p or "数据" in p):
            return """【客户账户综合总结】

客户：王总 | 报告期：2024-06-30 | 风险等级：平衡型（R3）

━━━ 账户总览 ━━━
总资产规模：5,000 万元 | 期间收益率：+12.50% | 基准收益率：+8.30% | 超额收益：+4.20%

━━━ 私募持仓分析 ━━━
私募产品数量：3 只 | 行业覆盖：消费、科技、金融、医药、新能源 | 第一大行业：消费（28.5%）

━━━ 风险提示 ━━━
当前投资组合风险分散良好，无明显风险信号。前三大持仓集中度 42%，处于合理区间。

━━━ 综合建议 ━━━
组合整体跑赢基准，策略执行效果良好。建议维持当前配置，关注科技板块估值回调风险。"""

        # Default
        return f"MockLLM response to: {prompt[:100]}..."

    def bind_tools(self, tools: list) -> "MockLLM":
        """Mock tool binding (no-op)."""
        return self

    def with_structured_output(self, schema: type, **kwargs) -> "MockLLM":
        """Mock structured output (no-op)."""
        return self


# ══════════════════════════════════════════════════════════
# Real LLM via LangChain
# ══════════════════════════════════════════════════════════


class LLMService:
    """Unified LLM service with provider auto-detection and graceful fallback.

    Priority:
    1. If LLM_API_KEY is set → use real LLM (Anthropic or OpenAI)
    2. If LLM_PROVIDER="mock" → use MockLLM
    3. If real LLM import fails → fall back to MockLLM
    """

    def __init__(self):
        self._llm = None
        self._initialized = False

    @property
    def llm(self):
        """Get the underlying LLM instance (lazy init)."""
        if not self._initialized:
            self._initialize()
        return self._llm

    def _initialize(self):
        """Initialize the LLM based on settings."""
        self._initialized = True

        provider = settings.LLM_PROVIDER.lower()
        api_key = settings.LLM_API_KEY

        # If mock mode or no API key
        if provider == "mock" or not api_key:
            logger.info("LLM: Using MockLLM (provider=%s, api_key=%s)",
                        provider, "set" if api_key else "not set")
            self._llm = MockLLM()
            return

        # Try to initialize real LLM
        try:
            if provider == "anthropic":
                self._llm = self._init_anthropic(api_key)
            elif provider in ("openai", "openai_compatible"):
                self._llm = self._init_openai(api_key)
            else:
                logger.warning("Unknown LLM provider '%s', falling back to MockLLM", provider)
                self._llm = MockLLM()
                return

            logger.info("LLM: Initialized %s/%s", provider, settings.LLM_MODEL)

        except ImportError as e:
            logger.warning("LangChain provider not installed (%s), falling back to MockLLM", e)
            self._llm = MockLLM()
        except Exception as e:
            logger.error("Failed to initialize LLM: %s, falling back to MockLLM", e)
            self._llm = MockLLM()

    def _init_anthropic(self, api_key: str):
        """Initialize Anthropic Claude via LangChain."""
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.LLM_MODEL,
            api_key=api_key,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            base_url=settings.LLM_BASE_URL,
        )

    def _init_openai(self, api_key: str):
        """Initialize OpenAI GPT via LangChain."""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=api_key,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            base_url=settings.LLM_BASE_URL,
        )

    # ── Convenience Methods ────────────────────────────

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        """Send a prompt and get a text response."""
        llm = self.llm
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(prompt, **kwargs)
        else:
            response = llm.invoke(prompt, **kwargs)
        # Handle LangChain AIMessage
        if hasattr(response, "content"):
            return response.content
        return str(response)

    def invoke(self, prompt: str, **kwargs) -> str:
        """Synchronous invoke."""
        llm = self.llm
        response = llm.invoke(prompt, **kwargs)
        if hasattr(response, "content"):
            return response.content
        return str(response)

    async def ainvoke_json(self, prompt: str, **kwargs) -> dict:
        """Send a prompt and parse JSON response."""
        text = await self.ainvoke(prompt, **kwargs)
        # Try to extract JSON from the response
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    def is_mock(self) -> bool:
        """Check if using mock LLM."""
        return isinstance(self.llm, MockLLM)

    @property
    def model_name(self) -> str:
        """Get the current model name."""
        if self.is_mock():
            return "mock"
        return settings.LLM_MODEL


# ══════════════════════════════════════════════════════════
# Global singleton
# ══════════════════════════════════════════════════════════

_llm_service: Optional[LLMService] = None


def get_llm() -> LLMService:
    """Get the global LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
