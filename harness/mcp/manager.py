"""MCP Manager — MCP Server 注册、Tool 发现、统一调用"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class MCPTool:
    """MCP Tool 定义"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None  # Demo 模式：直接调用函数


@dataclass
class MCPServer:
    """MCP Server 定义"""
    name: str
    description: str
    tools: List[MCPTool] = field(default_factory=list)
    status: str = "disconnected"


class MCPManager:
    """MCP 协议管理器

    职责：
    1. 注册/注销 MCP Server
    2. 发现并索引所有 Tool
    3. 统一 Tool 调用入口
    4. 连接健康检查
    """

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
        self._tool_index: Dict[str, MCPTool] = {}       # tool_name -> MCPTool
        self._tool_server_map: Dict[str, str] = {}       # tool_name -> server_name

    # ── Server 管理 ─────────────────────────────────

    def register_server(self, name: str, description: str = "",
                        tools: List[MCPTool] = None) -> MCPServer:
        """注册一个 MCP Server"""
        server = MCPServer(
            name=name,
            description=description,
            tools=tools or [],
            status="connected",
        )
        self._servers[name] = server

        # 索引所有 Tool
        for tool in server.tools:
            self._tool_index[tool.name] = tool
            self._tool_server_map[tool.name] = name

        print(f"[MCPManager] Server registered: {name} ({len(server.tools)} tools)")
        return server

    def unregister_server(self, name: str) -> bool:
        """注销 MCP Server"""
        if name not in self._servers:
            return False

        # 清理 tool 索引
        server = self._servers[name]
        for tool in server.tools:
            self._tool_index.pop(tool.name, None)
            self._tool_server_map.pop(tool.name, None)

        del self._servers[name]
        print(f"[MCPManager] Server unregistered: {name}")
        return True

    def get_server(self, name: str) -> Optional[MCPServer]:
        """获取 Server 信息"""
        return self._servers.get(name)

    def list_servers(self) -> List[MCPServer]:
        """列出所有 Server"""
        return list(self._servers.values())

    # ── Tool 管理 ───────────────────────────────────

    def list_tools(self, server_name: Optional[str] = None) -> List[Dict]:
        """列出 Tool"""
        if server_name:
            server = self._servers.get(server_name)
            if not server:
                return []
            return [self._tool_to_dict(t) for t in server.tools]

        return [self._tool_to_dict(t) for t in self._tool_index.values()]

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """按名称获取 Tool"""
        return self._tool_index.get(name)

    async def call_tool(self, server_name: str, tool_name: str,
                        arguments: Dict[str, Any]) -> Any:
        """调用 Tool

        Args:
            server_name: MCP Server 名称（或 "any" 自动查找）
            tool_name: Tool 名称
            arguments: Tool 参数

        Returns:
            Tool 执行结果
        """
        tool = self._tool_index.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        if server_name != "any":
            actual_server = self._tool_server_map.get(tool_name)
            if actual_server and actual_server != server_name:
                raise ValueError(f"Tool '{tool_name}' belongs to '{actual_server}', not '{server_name}'")

        if tool.handler is None:
            raise RuntimeError(f"Tool '{tool_name}' has no handler registered")

        # Demo 模式：直接调用 Python 函数
        print(f"  [MCP] Calling: {tool_name}({arguments})")
        import asyncio
        if asyncio.iscoroutinefunction(tool.handler):
            result = await tool.handler(**arguments)
        else:
            result = tool.handler(**arguments)
        return result

    def get_all_tools_for_agent(self) -> List[Dict]:
        """获取所有 Tool 描述（供 Agent 使用）"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "server": self._tool_server_map.get(tool.name, "unknown"),
            }
            for tool in self._tool_index.values()
        ]

    # ── 辅助方法 ────────────────────────────────────

    @staticmethod
    def _tool_to_dict(tool: MCPTool) -> Dict:
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    def get_stats(self) -> Dict:
        """获取 MCP 统计"""
        return {
            "total_servers": len(self._servers),
            "total_tools": len(self._tool_index),
            "servers": [
                {
                    "name": s.name,
                    "status": s.status,
                    "tool_count": len(s.tools),
                    "tools": [t.name for t in s.tools],
                }
                for s in self._servers.values()
            ],
        }


# 全局 MCP Manager 单例
mcp_manager = MCPManager()
