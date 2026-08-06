"""Harness Framework — Agent Factory using DeepAgents.

Creates DeepAgents-powered agent instances with full middleware stack:
- Planning (TodoList)
- File system management
- Subagent delegation
- Context summarization
- Skill execution
- MCP tool integration
- Mem0 memory integration
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.chat_models import init_chat_model

from config.settings import settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════

HARNESS_SYSTEM_PROMPT = """You are a professional financial advisory AI assistant. You help users with:

1. **Parsing fund diagnostic reports** — Extract structured data (fund name, performance metrics,
   risk assessment, holdings analysis) from fund reports.
2. **Generating investment summaries** — Combine customer account analysis with private equity
   holding reports to create comprehensive investment portfolio summaries.
3. **Answering system queries** — Provide status reports on agent executions, skill usage,
   and system metrics.
4. **Managing skills** — Help users import/export and manage analytical skills.

## Workflow

When a user asks you to:
- Parse a report → use the `report_parser` task/subagent
- Generate a summary → use the `summary_generator` task/subagent
- Query system status → use your tools to gather and present stats

## Guidelines

- Always retrieve relevant memories before responding (use search_memory)
- Store important user context, preferences, and results for future reference (use add_memory)
- Break complex tasks into steps using the todo list
- Delegate specialized tasks to subagents when appropriate
- Present information clearly in Chinese when the user communicates in Chinese
- For financial data, cite sources and clearly distinguish facts from analysis

Current user context will be provided at the start of each conversation.
"""


# ══════════════════════════════════════════════════════════
# Agent Factory
# ══════════════════════════════════════════════════════════


def create_harness_agent(
    model: str | None = None,
    tools: list | None = None,
    subagents: list | None = None,
    memory_client=None,
    langfuse_handler=None,
    system_prompt: str | None = None,
    middleware: list | None = None,
) -> Any:
    """Create a Harness Agent using DeepAgents.

    This wraps DeepAgents' create_deep_agent() with Harness-specific
    tools, middleware, and system prompt.

    Args:
        model: Model identifier in 'provider:model_name' format.
               Defaults to settings.AGENT_DEFAULT_MODEL.
        tools: Additional LangChain tools for the agent.
        subagents: Subagent definitions for task delegation.
        memory_client: Mem0Client instance for memory tools.
        langfuse_handler: LangFuse CallbackHandler for tracing.
        system_prompt: Override the default system prompt.
        middleware: Custom middleware stack (overrides defaults).

    Returns:
        A DeepAgents agent instance ready for .invoke() or .ainvoke().
    """
    model_name = model or settings.AGENT_DEFAULT_MODEL

    try:
        model_instance = init_chat_model(model_name, temperature=settings.LLM_TEMPERATURE)
    except Exception as e:
        logger.warning(
            "Failed to initialize model '%s': %s. Falling back to mock mode.",
            model_name, e,
        )
        model_instance = _create_mock_model()

    # ── Collect tools ────────────────────────────────────
    all_tools = list(tools or [])

    # Add memory tools if client is provided
    if memory_client:
        try:
            from harness.memory.tools import create_memory_tools
            memory_tools = create_memory_tools(memory_client)
            all_tools.extend(memory_tools)
        except Exception as e:
            logger.warning("Failed to create memory tools: %s", e)

    # ── Build middleware stack ───────────────────────────
    if middleware is None:
        middleware = _build_default_middleware(model_name, all_tools, subagents)

    # ── Callbacks ────────────────────────────────────────
    callbacks = []
    if langfuse_handler:
        callbacks.append(langfuse_handler)

    # ── Create agent ─────────────────────────────────────
    try:
        from deepagents import create_deep_agent

        agent = create_deep_agent(
            model=model_instance,
            tools=all_tools,
            system_prompt=system_prompt or HARNESS_SYSTEM_PROMPT,
            middleware=middleware,
            subagents=subagents or [],
        )
        logger.info(
            "Harness agent created: model=%s, tools=%d, subagents=%d",
            model_name, len(all_tools), len(subagents or []),
        )
        return agent

    except ImportError:
        logger.warning(
            "deepagents package not installed. Falling back to custom LangGraph agent loop."
        )
        return _create_fallback_agent(model_instance, all_tools, subagents)
    except Exception as e:
        logger.error("Failed to create DeepAgents agent: %s. Using fallback.", e)
        return _create_fallback_agent(model_instance, all_tools, subagents)


def _build_default_middleware(model_name: str, tools: list, subagents: list | None) -> list:
    """Build the default middleware stack for Harness agents."""
    middleware = []

    try:
        from deepagents.middleware import (
            FilesystemMiddleware,
            SummarizationMiddleware,
        )
        from deepagents.middleware import SubAgentMiddleware
        from langchain.agents.middleware import TodoListMiddleware

        middleware.extend([
            FilesystemMiddleware(),
            TodoListMiddleware(),
            SubAgentMiddleware(
                default_model=model_name,
                default_tools=tools,
                subagents=subagents or [],
            ),
            SummarizationMiddleware(),
        ])
    except ImportError:
        logger.debug("DeepAgents middleware not available; using minimal stack")

    return middleware


def _create_fallback_agent(model_instance, tools, subagents):
    """Create a fallback agent using the custom LangGraph loop.

    This is used when the deepagents package is not installed or
    when initialization fails.
    """
    from .loop import HarnessAgent as FallbackAgent
    agent = FallbackAgent()
    agent._model = model_instance
    agent._tools = tools or []
    agent._subagents = subagents or []
    return agent


def _create_mock_model():
    """Create a mock LLM model for demo/testing without API keys.

    Returns a simple callable that echoes back what it would do.
    """
    from langchain_core.language_models.chat_models import BaseChatModel

    class MockChatModel(BaseChatModel):
        """A mock chat model for demo purposes."""

        model_name: str = "mock-harness-model"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            from langchain_core.messages import AIMessage
            return type(
                "MockResult",
                (),
                {
                    "generations": [
                        [type("MockGen", (), {"message": AIMessage(content=self._mock_response(messages))})]
                    ]
                },
            )()

        def _mock_response(self, messages) -> str:
            last_msg = messages[-1].content if messages else ""
            return f"[Mock Agent] 已收到: '{last_msg[:100]}...' — Demo 模式下仅展示流程，不执行真实 LLM 推理。"

    return MockChatModel()


# ══════════════════════════════════════════════════════════
# Convenience Functions
# ══════════════════════════════════════════════════════════


def get_default_subagents() -> list[dict]:
    """Get default subagent definitions for Harness.

    Each subagent is a dict with 'name', 'description', 'system_prompt',
    and optionally 'tools'.
    """
    return [
        {
            "name": "report-parser",
            "description": "Parse fund diagnostic reports and extract structured data. "
                           "Delegate report parsing tasks to this agent.",
            "system_prompt": (
                "You are a financial document parsing specialist. "
                "Extract structured data from fund diagnostic reports including: "
                "fund name, fund code, performance metrics, risk assessment, "
                "holdings analysis, and diagnosis conclusions. "
                "Always validate extracted data for completeness and reasonableness."
            ),
            "tools": [],  # Will be populated with MCP tools at runtime
        },
        {
            "name": "summary-generator",
            "description": "Generate comprehensive investment summaries by combining "
                           "account analysis and private equity holding data. "
                           "Delegate summary generation to this agent.",
            "system_prompt": (
                "You are a financial portfolio analyst. Generate comprehensive "
                "investment summaries that combine: customer account overview, "
                "private equity holding performance, risk analysis, and "
                "actionable suggestions. Present findings in clear Chinese."
            ),
            "tools": [],
        },
    ]
