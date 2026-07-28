#!/usr/bin/env python3
"""
Harness Framework Demo — 一键启动入口

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

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════
# 初始化框架
# ═══════════════════════════════════════════════════

def init_harness():
    """初始化 Harness 框架：注册 Skill、MCP Server"""
    from harness.skills.registry import skill_registry
    from harness.skills.base import SkillManifest
    from harness.mcp.manager import mcp_manager

    print("=" * 60)
    print("  🤖 Harness Framework v0.1.0 — 初始化中...")
    print("=" * 60)

    # ── 注册 MCP Server ──
    from mcp_servers.demo_tools import DEMO_TOOLS
    mcp_manager.register_server(
        name="demo_tools",
        description="Demo MCP Server — 提供文档解析、账户分析、持仓查询",
        tools=DEMO_TOOLS,
    )
    print(f"  ✓ MCP Server 已注册: {len(mcp_manager.list_servers())} servers, "
          f"{len(mcp_manager.list_tools())} tools")

    # ── 动态加载 Skill ──
    skills_dir = PROJECT_ROOT / "skills"
    loaded_count = 0

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        yaml_path = skill_dir / "skill.yaml"
        py_path = skill_dir / f"{skill_dir.name}.py"

        # 尝试 parser.py / generator.py 等命名
        if not py_path.exists():
            py_candidates = list(skill_dir.glob("*.py"))
            py_candidates = [p for p in py_candidates if p.name != "__init__.py"]
            if py_candidates:
                py_path = py_candidates[0]

        if not yaml_path.exists() or not py_path.exists():
            print(f"  ⚠ 跳过 {skill_dir.name}: 缺少 skill.yaml 或 .py 文件")
            continue

        import yaml
        with open(yaml_path) as f:
            manifest_data = yaml.safe_load(f)
            manifest = SkillManifest(**manifest_data)

        # 动态导入 Skill 模块
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"skills.{skill_dir.name}", py_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 获取 SkillClass
        if hasattr(module, "SkillClass"):
            skill = module.SkillClass(manifest)
        else:
            # 自动查找 BaseSkill 子类
            from harness.skills.base import BaseSkill
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                        issubclass(attr, BaseSkill) and
                        attr is not BaseSkill):
                    skill = attr(manifest)
                    break
            else:
                print(f"  ⚠ 跳过 {skill_dir.name}: 未找到 SkillClass")
                continue

        skill_registry.register(skill)
        loaded_count += 1

    print(f"  ✓ Skill 已加载: {loaded_count} 个")

    # ── 注入 MCP Manager ──
    skill_registry.inject_mcp(mcp_manager)

    # ── 统计 ──
    print(f"\n  📊 框架就绪:")
    print(f"     • Agent Loop: Plan→Execute→Observe→Reflect (max {5} loops)")
    print(f"     • MCP Servers: {len(mcp_manager.list_servers())}")
    print(f"     • MCP Tools: {len(mcp_manager.list_tools())}")
    print(f"     • Skills: {len(skill_registry.list_all())}")
    print(f"     • Intents: {len(__import__('harness.intent.router', fromlist=['intent_router']).intent_router.intents)}")
    print("=" * 60)
    print()


# ═══════════════════════════════════════════════════
# CLI 交互模式
# ═══════════════════════════════════════════════════

async def cli_mode():
    """CLI 交互模式"""
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

        print(f"🤖 处理中...")
        print("-" * 40)

        result = await harness_agent.run(user_input)

        print(f"  📌 意图: {result['intent']} (置信度: {result['confidence']:.2f})")
        print(f"  🔧 Skill: {result['matched_skill']}")
        print(f"  📋 计划: {' → '.join(result['plan'])}")
        print(f"  ⏱️  耗时: {result['latency_ms']:.0f}ms")
        print(f"  📊 状态: {result['status']}")
        print("-" * 40)
        print(result['output'])
        print("-" * 40)
        print()


# ═══════════════════════════════════════════════════
# 自动演示模式
# ═══════════════════════════════════════════════════

async def run_auto_demo():
    """运行自动演示"""
    from harness.agent.loop import harness_agent

    demos = [
        "帮我解析这份基金诊断报告",
        "生成王总账户的持仓总结，分析一下风险",
        "查询今天系统运行状态和Skill调用统计",
        "什么是基金诊断报告？",  # 未知意图
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
        for step in result['plan']:
            print(f"     {result['plan'].index(step)+1}. {step}")
        print(f"  ⏱️  耗时: {result['latency_ms']:.0f}ms")
        print(f"  📊 状态: {result['status']}")
        if result.get('error'):
            print(f"  ❌ 错误: {result['error']}")
        print()
        print(result['output'])
        print()

        await asyncio.sleep(0.5)  # 演示间隔

    # 最终统计
    from harness.tracker import execution_tracker
    summary = execution_tracker.get_summary()
    print(f"{'='*60}")
    print(f"  📊 演示总结:")
    print(f"     总执行: {summary['total_executions']} 次")
    print(f"     成功率: {summary['success_rate']}%")
    print(f"     平均延迟: {summary['avg_latency_ms']:.0f}ms")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════
# API 模式
# ═══════════════════════════════════════════════════

def start_api(port: int = 8000):
    """启动 FastAPI 服务"""
    import uvicorn
    from api.main import app
    print(f"🚀 API 服务启动: http://localhost:{port}")
    print(f"   📖 API 文档: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)


# ═══════════════════════════════════════════════════
# Admin 模式
# ═══════════════════════════════════════════════════

def start_admin(port: int = 8501):
    """启动 Streamlit 管理后台"""
    import subprocess
    admin_path = PROJECT_ROOT / "admin" / "app.py"
    print(f"🎛️  管理后台启动: http://localhost:{port}")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(admin_path),
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
    ])


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Harness Framework Demo — 一键启动",
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

    # 初始化
    init_harness()

    # 自动演示模式（快速展示，不需要额外服务）
    if args.demo:
        asyncio.run(run_auto_demo())
        return

    # CLI 交互模式（默认）
    if not args.api and not args.admin and not args.all:
        asyncio.run(cli_mode())
        return

    # API 模式
    if args.api and not args.all:
        start_api(args.api_port)
        return

    # Admin 模式
    if args.admin and not args.all:
        start_admin(args.admin_port)
        return

    # All 模式
    if args.all:
        import threading
        api_thread = threading.Thread(target=start_api, args=(args.api_port,), daemon=True)
        api_thread.start()
        print(f"🚀 API 服务已启动: http://localhost:{args.api_port}")
        print(f"🎛️  管理后台启动: http://localhost:{args.admin_port}")
        print()
        start_admin(args.admin_port)


if __name__ == "__main__":
    main()
