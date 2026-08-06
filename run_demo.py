#!/usr/bin/env python3
"""
Harness Framework — 一键启动入口

Built on: DeepAgents + LangGraph + LangChain + LangFuse + Mem0

用法:
    python run_demo.py              # CLI 交互模式
    python run_demo.py --api        # 启动 FastAPI 服务
    python run_demo.py --admin      # 启动 Streamlit 管理后台
    python run_demo.py --all        # 同时启动 API + Admin
    python run_demo.py --demo       # 运行自动演示
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ══════════════════════════════════════════════════════════
# 框架初始化
# ══════════════════════════════════════════════════════════


def init_harness():
    """Initialize the Harness framework."""
    from config.settings import settings

    print("=" * 60)
    print(f"  🤖 Harness Framework v{settings.PROJECT_VERSION}")
    print("  DeepAgents + LangGraph + LangChain + LangFuse + Mem0")
    print("=" * 60)

    # ── Initialize Database ──
    from harness.db.engine import init_db
    init_db()
    print(f"  ✓ Database initialized: {settings.DATABASE_URL}")

    # ── Register MCP Tools ──
    from harness.mcp.registry import mcp_registry
    from mcp_servers.demo_tools import DEMO_TOOLS

    for tool in DEMO_TOOLS:
        mcp_registry.register_local_tool(
            name=tool.name,
            description=tool.description,
            handler=tool.handler,
            server_name="demo_tools",
            parameters=tool.parameters,
        )
    print(f"  ✓ MCP Tools registered: {mcp_registry.get_stats()['total_tools']} tools")

    # ── Load Skills ──
    from harness.skills.manager import skill_manager
    skill_manager.load_from_directory()
    skill_manager.inject_mcp(mcp_registry)
    print(f"  ✓ Skills loaded: {len(skill_manager.list_skills())} skills")

    # ── Initialize Memory ──
    from harness.memory.client import Mem0Client
    memory_client = Mem0Client()

    # ── Sync intents ──
    try:
        from harness.intent.store import IntentStore
        store = IntentStore()
        intents = store.load_from_yaml()
        store.sync_to_db(intents)
        print(f"  ✓ Intents synced: {len(intents)} intents")
    except Exception as e:
        print(f"  ⚠ Intent sync failed: {e}")

    # ── Summary ──
    print(f"\n  📊 框架就绪:")
    print(f"     • LLM: {settings.LLM_PROVIDER}/{settings.LLM_MODEL}")
    print(f"     • LangFuse: {'enabled' if settings.LANGFUSE_ENABLED else 'disabled'}")
    print(f"     • Mem0: {'enabled' if settings.MEM0_ENABLED else 'disabled'}")
    print(f"     • MCP Tools: {mcp_registry.get_stats()['total_tools']}")
    print(f"     • Skills: {len(skill_manager.list_skills())}")
    print(f"     • Intents: 4")
    print("=" * 60)
    print()

    return {"memory_client": memory_client}


# ══════════════════════════════════════════════════════════
# CLI 交互模式
# ══════════════════════════════════════════════════════════


async def cli_mode():
    """CLI interactive mode."""
    from harness.agent.loop import harness_agent

    print("💬 输入你的需求（输入 'quit' 退出，'demo' 运行演示）")
    print()
    print("  试试: '帮我解析基金诊断报告'")
    print("        '生成王总账户的持仓总结'")
    print("        '查询系统运行状态'")
    print()

    while True:
        try:
            user_input = input("👤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("👋 再见！")
            break

        if user_input.lower() == "demo":
            await run_auto_demo()
            continue

        print("🤖 处理中...")
        print("-" * 40)

        result = await harness_agent.run(user_input)

        print(f"  📌 意图: {result['intent']} (置信度: {result['confidence']:.2f})")
        print(f"  🔧 Skill: {result['matched_skill']}")
        print(f"  📋 计划: {' → '.join(result['plan'])}")
        print(f"  ⏱️  耗时: {result['latency_ms']:.0f}ms")
        print(f"  📊 状态: {result['status']}")
        print("-" * 40)
        print(result["output"])
        print("-" * 40)
        print()


# ══════════════════════════════════════════════════════════
# 自动演示模式
# ══════════════════════════════════════════════════════════


async def run_auto_demo():
    """Run automatic demo with multiple test cases."""
    from harness.agent.loop import harness_agent

    demos = [
        "帮我解析这份基金诊断报告",
        "生成王总账户的持仓总结，分析一下风险",
        "查询今天系统运行状态和Skill调用统计",
        "什么是基金诊断报告？",
    ]

    print("\n🎬 自动演示模式\n")
    for i, demo_input in enumerate(demos, 1):
        print(f"{'='*60}")
        print(f"  Demo {i}/{len(demos)}: {demo_input}")
        print(f"{'='*60}")

        result = await harness_agent.run(demo_input)

        print(f"  📌 意图: {result['intent']} (置信度: {result['confidence']:.2f})")
        print(f"  🔧 Skill: {result['matched_skill']}")
        print(f"  📋 计划:")
        for j, step in enumerate(result["plan"], 1):
            print(f"     {j}. {step}")
        print(f"  ⏱️  耗时: {result['latency_ms']:.0f}ms")
        print(f"  📊 状态: {result['status']}")
        if result.get("error"):
            print(f"  ❌ 错误: {result['error']}")
        print()
        print(result["output"])
        print()

        await asyncio.sleep(0.3)


# ══════════════════════════════════════════════════════════
# API 模式
# ══════════════════════════════════════════════════════════


def start_api(port: int = 8000):
    """Start FastAPI service."""
    import uvicorn
    from api.main import app

    print(f"🚀 API 服务启动: http://localhost:{port}")
    print(f"   📖 API 文档: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)


# ══════════════════════════════════════════════════════════
# Admin 模式
# ══════════════════════════════════════════════════════════


def start_admin(port: int = 8501):
    """Start Streamlit admin dashboard."""
    import subprocess

    admin_path = PROJECT_ROOT / "admin" / "app.py"
    print(f"🎛️  管理后台启动: http://localhost:{port}")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(admin_path),
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
    ])


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Harness Framework — 一键启动",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_demo.py              CLI 交互模式
  python run_demo.py --api        FastAPI 服务
  python run_demo.py --admin      Streamlit 管理后台
  python run_demo.py --all        API + Admin 同时启动
  python run_demo.py --demo       自动演示
        """,
    )
    parser.add_argument("--api", action="store_true", help="启动 FastAPI 服务")
    parser.add_argument("--admin", action="store_true", help="启动 Streamlit 管理后台")
    parser.add_argument("--all", action="store_true", help="同时启动 API + Admin")
    parser.add_argument("--demo", action="store_true", help="运行自动演示")
    parser.add_argument("--api-port", type=int, default=8000, help="API 端口 (默认 8000)")
    parser.add_argument("--admin-port", type=int, default=8501, help="Admin 端口 (默认 8501)")

    args = parser.parse_args()

    # Initialize framework
    init_harness()

    # Auto demo mode
    if args.demo:
        asyncio.run(run_auto_demo())
        return

    # CLI interactive mode (default)
    if not args.api and not args.admin and not args.all:
        asyncio.run(cli_mode())
        return

    # API mode
    if args.api and not args.all:
        start_api(args.api_port)
        return

    # Admin mode
    if args.admin and not args.all:
        start_admin(args.admin_port)
        return

    # All mode
    if args.all:
        import threading

        api_thread = threading.Thread(
            target=start_api, args=(args.api_port,), daemon=True
        )
        api_thread.start()
        print(f"🚀 API 服务已启动: http://localhost:{args.api_port}")
        print(f"🎛️  管理后台启动: http://localhost:{args.admin_port}")
        print()
        start_admin(args.admin_port)


if __name__ == "__main__":
    main()
