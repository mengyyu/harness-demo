"""全局配置管理"""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class HarnessConfig:
    """Harness 框架全局配置"""

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("LLM_MODEL", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")

    # Agent Loop
    agent_max_loops: int = int(os.getenv("AGENT_MAX_LOOPS", "5"))
    agent_timeout_seconds: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))

    # Memory
    memory_max_session: int = int(os.getenv("MEMORY_MAX_SESSION", "100"))
    memory_max_user: int = int(os.getenv("MEMORY_MAX_USER", "500"))
    memory_max_entity: int = int(os.getenv("MEMORY_MAX_ENTITY", "1000"))

    # Paths
    skills_dir: str = os.getenv("SKILLS_DIR", "skills")
    mcp_servers_dir: str = os.getenv("MCP_SERVERS_DIR", "mcp_servers")

    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    admin_port: int = int(os.getenv("ADMIN_PORT", "8501"))


# 全局单例
config = HarnessConfig()
