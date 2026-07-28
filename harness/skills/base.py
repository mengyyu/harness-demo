"""Skill 基类定义"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SkillStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class SkillManifest(BaseModel):
    """Skill 清单文件模型（对应 skill.yaml）"""
    name: str = Field(..., description="Skill 唯一标识")
    version: str = Field(default="1.0.0", description="语义版本号")
    description: str = Field(default="", description="Skill 描述")
    intents: List[str] = Field(default_factory=list, description="触发的意图列表")
    required_mcp_tools: List[str] = Field(default_factory=list, description="依赖的 MCP Tool")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="输入 JSON Schema")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="输出 JSON Schema")
    timeout: int = Field(default=300, description="超时秒数")
    author: str = Field(default="", description="作者")


class SkillResult(BaseModel):
    """Skill 执行结果"""
    success: bool
    skill_name: str
    data: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    error: Optional[str] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    mcp_calls: List[Dict[str, Any]] = Field(default_factory=list)


class SkillContext(BaseModel):
    """Skill 执行上下文"""
    session_id: str
    user_id: str = "default"
    intent: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    memories: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class BaseSkill(ABC):
    """Skill 抽象基类"""

    def __init__(self, manifest: SkillManifest):
        self.manifest = manifest
        self.status = SkillStatus.ACTIVE
        self._mcp_manager = None  # 由框架注入

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def mcp_manager(self):
        """获取 MCP Manager（由框架注入）"""
        return self._mcp_manager

    def set_mcp_manager(self, manager):
        self._mcp_manager = manager

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """执行 Skill 逻辑，子类必须实现"""
        ...

    async def validate_input(self, context: SkillContext) -> bool:
        """输入校验，默认通过"""
        return True

    async def call_mcp_tool(self, server: str, tool: str, **kwargs) -> Any:
        """便捷调用 MCP Tool"""
        if not self._mcp_manager:
            raise RuntimeError("MCP Manager not initialized for this skill")
        return await self._mcp_manager.call_tool(server, tool, kwargs)

    def to_dict(self) -> Dict:
        return {
            "name": self.manifest.name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "intents": self.manifest.intents,
            "status": self.status.value,
            "required_mcp_tools": self.manifest.required_mcp_tools,
        }
