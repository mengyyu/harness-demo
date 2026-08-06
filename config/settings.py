"""Harness Framework — Global Configuration via Pydantic Settings.

All settings are loaded from environment variables or .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # ── Project ───────────────────────────────────────────────
    PROJECT_NAME: str = "Harness Agent Framework"
    PROJECT_VERSION: str = "0.2.0"
    DEBUG: bool = Field(default=False)

    # ── LLM ───────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(default="anthropic")
    LLM_MODEL: str = Field(default="claude-sonnet-4-5-20250929")
    LLM_TEMPERATURE: float = Field(default=0.1)
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_BASE_URL: Optional[str] = Field(default=None)
    LLM_MAX_TOKENS: int = Field(default=4096)

    # ── LangFuse (Observability) ──────────────────────────────
    LANGFUSE_PUBLIC_KEY: Optional[str] = Field(default=None)
    LANGFUSE_SECRET_KEY: Optional[str] = Field(default=None)
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com")
    LANGFUSE_ENABLED: bool = Field(default=False)

    # ── Mem0 (Memory) ─────────────────────────────────────────
    MEM0_ENABLED: bool = Field(default=False)
    MEM0_CONFIG_PATH: str = Field(default="")
    MEM0_VECTOR_STORE: str = Field(default="chroma")
    MEM0_LLM_PROVIDER: str = Field(default="langchain")
    MEM0_EMBEDDER_PROVIDER: str = Field(default="langchain")

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(default="sqlite:///./data/harness.db")
    DATABASE_ECHO: bool = Field(default=False)

    # ── MCP ───────────────────────────────────────────────────
    MCP_CONFIG_PATH: str = Field(default="config/mcp_servers.yaml")
    MCP_DEFAULT_TIMEOUT: int = Field(default=30)

    # ── Application Paths ─────────────────────────────────────
    SKILLS_DIR: str = Field(default="skills")
    INTENTS_CONFIG_PATH: str = Field(default="config/intents.yaml")
    DATA_DIR: str = Field(default="data")
    LOG_DIR: str = Field(default="logs")

    # ── Agent Loop ────────────────────────────────────────────
    AGENT_MAX_ITERATIONS: int = Field(default=25)
    AGENT_RECURSION_LIMIT: int = Field(default=50)
    AGENT_INTERRUPT_ENABLED: bool = Field(default=True)
    AGENT_DEFAULT_MODEL: str = Field(default="anthropic:claude-sonnet-4-5-20250929")
    AGENT_MAX_LOOPS: int = Field(default=5)
    AGENT_TIMEOUT_SECONDS: int = Field(default=300)

    # ── API ───────────────────────────────────────────────────
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    ADMIN_PORT: int = Field(default=8501)

    # ── Memory Limits ─────────────────────────────────────────
    MEMORY_MAX_SESSION: int = Field(default=100)
    MEMORY_MAX_USER: int = Field(default=500)
    MEMORY_MAX_ENTITY: int = Field(default=1000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Global singleton
settings = Settings()

# Ensure required directories exist
for _dir in [settings.SKILLS_DIR, settings.DATA_DIR, settings.LOG_DIR]:
    Path(_dir).mkdir(parents=True, exist_ok=True)
