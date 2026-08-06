"""Harness Framework — Configuration loader (backward-compatible wrapper).

Loads settings from config/settings.py and exposes as a simple dataclass-like object
for backward compatibility with the original harness-demo code.
"""

import os
from dataclasses import dataclass, field

from config.settings import settings as pydantic_settings


@dataclass
class HarnessConfig:
    """Backward-compatible config object matching the original harness.config API."""

    # LLM
    llm_provider: str = field(default_factory=lambda: pydantic_settings.LLM_PROVIDER)
    llm_model: str = field(default_factory=lambda: pydantic_settings.LLM_MODEL)
    llm_api_key: str = field(default_factory=lambda: pydantic_settings.LLM_API_KEY or "")

    # Agent Loop
    agent_max_loops: int = field(default_factory=lambda: pydantic_settings.AGENT_MAX_LOOPS)
    agent_timeout_seconds: int = field(default_factory=lambda: pydantic_settings.AGENT_TIMEOUT_SECONDS)

    # Memory
    memory_max_session: int = field(default_factory=lambda: pydantic_settings.MEMORY_MAX_SESSION)
    memory_max_user: int = field(default_factory=lambda: pydantic_settings.MEMORY_MAX_USER)
    memory_max_entity: int = field(default_factory=lambda: pydantic_settings.MEMORY_MAX_ENTITY)

    # Paths
    skills_dir: str = field(default_factory=lambda: pydantic_settings.SKILLS_DIR)
    mcp_servers_dir: str = field(default_factory=lambda: "mcp_servers")

    # API
    api_host: str = field(default_factory=lambda: pydantic_settings.API_HOST)
    api_port: int = field(default_factory=lambda: pydantic_settings.API_PORT)
    admin_port: int = field(default_factory=lambda: pydantic_settings.ADMIN_PORT)


# Global singleton (backward-compatible)
config = HarnessConfig()
