"""Tests for the MCP Integration."""

import pytest


class TestMCPRegistry:
    @pytest.fixture
    def registry(self):
        from harness.mcp.registry import MCPRegistry
        return MCPRegistry()

    def test_register_local_tool(self, registry):
        def my_handler(x: str) -> str:
            return f"Hello, {x}!"

        registry.register_local_tool(
            name="greet",
            description="Greet someone",
            handler=my_handler,
            server_name="test",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )

        tool = registry.get_tool("greet")
        assert tool is not None
        assert tool.name == "greet"
        assert tool.server_name == "test"

    def test_list_tools(self, registry):
        registry.register_local_tool("tool1", "First tool", lambda: "ok", server_name="test")
        registry.register_local_tool("tool2", "Second tool", lambda: "ok", server_name="test")

        tools = registry.list_tools()
        assert len(tools) == 2

        tools_by_server = registry.list_tools(server_name="test")
        assert len(tools_by_server) == 2

    def test_get_stats(self, registry):
        registry.register_local_tool("tool1", "Test tool", lambda: "ok", server_name="test")
        stats = registry.get_stats()
        assert stats["total_tools"] >= 1
        assert stats["total_servers"] >= 1

    def test_tool_not_found(self, registry):
        assert registry.get_tool("nonexistent") is None


class TestMCPToolConversion:
    def test_tool_to_langchain(self):
        import pytest
        try:
            from langchain_core.tools import StructuredTool
        except ImportError:
            pytest.skip("langchain_core not installed")

        from harness.mcp.tools import mcp_tool_to_langchain

        def handler(x: str = "") -> str:
            return f"Result: {x}"

        tool = mcp_tool_to_langchain(
            tool_name="test_tool",
            description="A test tool",
            handler=handler,
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
