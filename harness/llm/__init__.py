"""Harness LLM Service — Unified LLM interface with graceful degradation."""

from .service import LLMService, get_llm, MockLLM

__all__ = ["LLMService", "get_llm", "MockLLM"]
