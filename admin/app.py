"""Harness Framework — Streamlit Admin Dashboard (Enhanced).

Multi-tab admin interface for:
- Dashboard: KPI metrics, skill ranking, intent distribution
- Agent Runs: Execution logs with filtering and detail view
- Skill Management: List, enable/disable, import/export, reports
- Intent Library: CRUD, route testing, hit statistics
- Chat Test: Interactive agent conversation testing
- Memory Browser: Browse/search/delete memories
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Harness 管理后台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🤖 Harness Framework — 管理后台")
st.caption("Agent 编排框架 · DeepAgents + LangGraph + LangChain + LangFuse + Mem0")

# ══════════════════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════════════════


@st.cache_resource
def init_harness():
    """Initialize the Harness framework."""
    from harness.skills.manager import skill_manager
    from harness.mcp.registry import mcp_registry
    from harness.memory.client import Mem0Client

    # Load skills
    skill_manager.load_from_directory()

    # Register demo MCP tools
    from mcp_servers.demo_tools import DEMO_TOOLS
    for tool in DEMO_TOOLS:
        mcp_registry.register_local_tool(
            name=tool.name,
            description=tool.description,
            handler=tool.handler,
            server_name="demo_tools",
            parameters=tool.parameters,
        )

    # Inject MCP into skills
    skill_manager.inject_mcp(mcp_registry)

    # Init DB
    from harness.db.engine import init_db
    init_db()

    return {
        "skill_manager": skill_manager,
        "mcp_registry": mcp_registry,
        "memory_client": Mem0Client(),
    }


harness = init_harness()

# ══════════════════════════════════════════════════════════
# Sidebar Navigation
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📋 导航")
    tab = st.radio(
        "选择页面",
        [
            "📊 Dashboard",
            "📝 Agent 运行",
            "🔧 Skill 管理",
            "🎯 意图库",
            "💬 对话测试",
            "🧠 记忆管理",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    from harness.skills.registry import skill_registry
    from harness.mcp.registry import mcp_registry

    st.metric("已注册 Skill", len(skill_registry.list_all()))
    mcp_stats = mcp_registry.get_stats()
    st.metric("MCP Server", mcp_stats.get("total_servers", 0))
    st.metric("MCP Tools", mcp_stats.get("total_tools", 0))
    st.metric("意图数量", 4)

    st.divider()
    st.caption("v0.2.0 | DeepAgents + LangGraph + LangFuse + Mem0")

# ══════════════════════════════════════════════════════════
# Tab 1: Dashboard
# ══════════════════════════════════════════════════════════

if tab == "📊 Dashboard":
    st.header("📊 系统运行 Dashboard")

    # KPI cards
    try:
        from harness.observability.metrics import MetricsAggregator
        agg = MetricsAggregator()
        metrics_data = agg.get_agent_dashboard_metrics(hours=24)
    except Exception:
        metrics_data = {"total_executions": 0, "success_rate": 0, "avg_latency_ms": 0, "total_cost": 0}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("24h 执行次数", metrics_data.get("total_executions", 0))
    with col2:
        st.metric("成功率", f"{metrics_data.get('success_rate', 0)}%")
    with col3:
        st.metric("平均延迟", f"{metrics_data.get('avg_latency_ms', 0):.0f} ms")
    with col4:
        st.metric("预估费用", f"${metrics_data.get('total_cost', 0):.4f}")

    st.divider()

    # Skill ranking
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Skill 调用排行")
        try:
            skill_metrics = agg.get_skill_dashboard_metrics(hours=168)
            if skill_metrics:
                df_skills = pd.DataFrame(skill_metrics)
                st.dataframe(df_skills, use_container_width=True, hide_index=True)
            else:
                st.info("暂无 Skill 运行数据")
        except Exception:
            st.info("暂无 Skill 运行数据")

    with col_right:
        st.subheader("意图分布")
        intent_dist = metrics_data.get("intent_distribution", {})
        if intent_dist:
            df_intent = pd.DataFrame(
                [{"意图": k, "次数": v} for k, v in intent_dist.items()]
            )
            st.bar_chart(df_intent.set_index("意图"))
        else:
            st.info("暂无意图分布数据")

    # MCP Status
    st.divider()
    st.subheader("MCP Server 状态")
    for srv in mcp_stats.get("servers", []):
        icon = "🟢" if srv["status"] == "connected" else "🔴"
        tool_names = ", ".join(srv.get("tools", []))
        st.text(f"{icon} {srv['name']} ({srv['transport']}) — {srv['tool_count']} tools: {tool_names}")

# ══════════════════════════════════════════════════════════
# Tab 2: Agent Runs
# ══════════════════════════════════════════════════════════

elif tab == "📝 Agent 运行":
    st.header("📝 Agent 运行日志")

    col1, col2, col3 = st.columns(3)
    with col1:
        limit = st.number_input("显示条数", min_value=5, max_value=200, value=30)
    with col2:
        skill_filter = st.selectbox(
            "按 Skill 筛选",
            ["全部"] + [s.name for s in skill_registry.list_all()],
        )
    with col3:
        status_filter = st.selectbox("按状态筛选", ["全部", "success", "failed"])

    from harness.observability.tracer import get_tracer
    tracer = get_tracer()

    records = tracer.get_execution_records(
        limit=limit,
        status=None if status_filter == "全部" else status_filter,
    )

    if skill_filter != "全部":
        records = [r for r in records if r.get("skill_name") == skill_filter]

    if records:
        for r in records:
            icon = "✅" if r["status"] == "success" else "❌"
            ts = r.get("timestamp", "")[:19]
            with st.expander(
                f"{icon} [{ts}] {r.get('intent', 'N/A')} → "
                f"{r.get('skill_name', 'N/A')} ({r.get('latency_ms', 0):.0f}ms)"
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.text("输入:")
                    st.code(r.get("input_text", "")[:500], language=None)
                with col_b:
                    st.text("输出:")
                    st.code(r.get("output_text", "")[:1000], language=None)

                st.caption(
                    f"Session: {r.get('session_id', '?')} | "
                    f"Tokens: {r.get('total_tokens', 0)} | "
                    f"Cost: ${r.get('total_cost', 0):.6f}"
                )
                if r.get("langfuse_trace_id"):
                    st.caption(f"🔗 LangFuse: {r['langfuse_trace_id']}")

                if r.get("error"):
                    st.error(f"错误: {r['error']}")
    else:
        st.info("暂无执行记录，去「对话测试」页面试试")

# ══════════════════════════════════════════════════════════
# Tab 3: Skill Management
# ══════════════════════════════════════════════════════════

elif tab == "🔧 Skill 管理":
    st.header("🔧 Skill 管理")

    st.subheader("已安装 Skill")
    skills_data = skill_registry.get_stats()
    if skills_data:
        df = pd.DataFrame(skills_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Enable/disable buttons
        st.divider()
        st.subheader("启用/禁用")
        for skill in skill_registry.list_all():
            col1, col2, _ = st.columns([3, 1, 4])
            with col1:
                icon = "🟢" if skill.status.value == "active" else "⚫"
                st.text(f"{icon} {skill.name} v{skill.manifest.version}")
            with col2:
                from harness.skills.base import SkillStatus
                new_status = "禁用" if skill.status == SkillStatus.ACTIVE else "启用"
                if st.button(new_status, key=f"toggle_{skill.name}"):
                    from harness.skills.manager import skill_manager
                    skill_manager.toggle_skill(skill.name)
                    st.rerun()

    st.divider()

    # Skill reports
    st.subheader("Skill 运行报表")
    skill_name_report = st.selectbox(
        "选择 Skill（留空看全部）",
        ["全部"] + [s.name for s in skill_registry.list_all()],
    )
    try:
        report = tracer.get_skill_report(
            skill_name=None if skill_name_report == "全部" else skill_name_report,
            hours=168,
        )
        stats = report.get("skill_stats", [])
        if stats:
            df_stats = pd.DataFrame(stats)
            st.dataframe(df_stats, use_container_width=True, hide_index=True)
        else:
            st.info("暂无运行数据")
    except Exception:
        st.info("暂无运行数据")

    st.divider()

    # Import/Export
    col_import, col_export = st.columns(2)

    with col_import:
        st.subheader("📥 导入 Skill")
        uploaded_file = st.file_uploader("上传 .harness-skill 文件", type=["harness-skill", "zip"])
        if uploaded_file:
            import os
            temp_path = f"/tmp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            try:
                from harness.skills.importer import SkillImporter
                importer = SkillImporter(skills_dir="skills")
                skill_name = importer.import_skill(temp_path, overwrite=True)

                # Reload
                from harness.skills.manager import skill_manager
                skill_manager.load_from_directory()

                st.success(f"✅ Skill '{skill_name}' 导入成功！")
                st.rerun()
            except Exception as e:
                st.error(f"导入失败: {e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    with col_export:
        st.subheader("📤 导出 Skill")
        export_name = st.selectbox(
            "选择要导出的 Skill",
            [s.name for s in skill_registry.list_all()],
        )
        if st.button("导出 Skill", type="primary"):
            try:
                from harness.skills.importer import SkillImporter
                importer = SkillImporter(skills_dir="skills")
                output_path = importer.export_skill(export_name)
                with open(output_path, "rb") as f:
                    st.download_button(
                        "⬇️ 下载",
                        data=f.read(),
                        file_name=f"{export_name}.harness-skill",
                        mime="application/zip",
                    )
                st.success(f"导出成功")
            except Exception as e:
                st.error(f"导出失败: {e}")

# ══════════════════════════════════════════════════════════
# Tab 4: Intent Library
# ══════════════════════════════════════════════════════════

elif tab == "🎯 意图库":
    st.header("🎯 意图库配置")

    from harness.intent.router import intent_router, IntentRule

    # Intent list
    st.subheader("当前意图")
    intents_data = intent_router.export_intents()
    if intents_data:
        df = pd.DataFrame(intents_data)
        st.dataframe(
            df[["name", "description", "bound_skill", "hit_count", "is_active"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # Test routing
    st.subheader("🧪 测试意图路由")
    test_msg = st.text_input("输入测试语句", placeholder="帮我解析这份基金报告")
    if test_msg and st.button("测试路由"):
        intents, confidences, skills = intent_router.route(test_msg)
        st.json({
            "input": test_msg,
            "results": [
                {"intent": i, "confidence": round(c, 2), "skill": s}
                for i, c, s in zip(intents, confidences, skills)
            ],
        })

    st.divider()

    # Add intent
    st.subheader("➕ 新增意图")
    with st.form("new_intent_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("意图名称", placeholder="my_intent")
            new_desc = st.text_input("描述", placeholder="意图描述")
        with col2:
            new_skill = st.text_input("绑定 Skill", placeholder="skill_name")
            new_priority = st.number_input("优先级", min_value=0, max_value=100, value=5)

        new_keywords = st.text_input("关键词（逗号分隔）", placeholder="解析, 报告, 基金")
        new_negative = st.text_input("排除词（逗号分隔）", placeholder="排除词1")
        new_examples = st.text_area("示例问法（每行一个）", placeholder="示例1\n示例2")

        if st.form_submit_button("保存意图"):
            if new_name:
                rule = IntentRule(
                    name=new_name,
                    description=new_desc,
                    keywords=[k.strip() for k in new_keywords.split(",") if k.strip()],
                    negative_keywords=[k.strip() for k in new_negative.split(",") if k.strip()],
                    bound_skill=new_skill,
                    priority=new_priority,
                    examples=[e.strip() for e in new_examples.split("\n") if e.strip()],
                )
                intent_router.add_intent(rule)
                st.success(f"意图 '{new_name}' 已保存")
                st.rerun()
            else:
                st.error("意图名称不能为空")

# ══════════════════════════════════════════════════════════
# Tab 5: Chat Test
# ══════════════════════════════════════════════════════════

elif tab == "💬 对话测试":
    st.header("💬 对话测试")

    st.markdown("""
    试试以下输入：
    - `帮我解析这份基金诊断报告`
    - `生成王总账户的持仓总结`
    - `查询系统运行状态`
    """)

    user_input = st.chat_input("输入你的需求...")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if user_input:
        with st.spinner("Agent 执行中..."):
            import asyncio
            from harness.agent.loop import harness_agent

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(harness_agent.run(user_input))
            loop.close()

        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.chat_history.append({"role": "assistant", "content": result})

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                result = msg["content"]
                st.success(
                    f"意图: {result.get('intent', 'N/A')} | "
                    f"Skill: {result.get('matched_skill', 'N/A')} | "
                    f"延迟: {result.get('latency_ms', 0):.0f}ms"
                )

                with st.expander("📋 执行计划"):
                    st.json(result.get("plan", []))

                with st.expander("📝 详细步骤"):
                    st.json(result.get("steps", []))

                st.subheader("输出结果")
                st.markdown(result.get("output", "无输出"))

# ══════════════════════════════════════════════════════════
# Tab 6: Memory Browser
# ══════════════════════════════════════════════════════════

elif tab == "🧠 记忆管理":
    st.header("🧠 记忆管理")

    memory_client = harness["memory_client"]
    mem_stats = memory_client.get_stats()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总记忆数", mem_stats.get("total_memories", mem_stats.get("session_memories", 0)))
    with col2:
        backend = mem_stats.get("backend", "unknown")
        st.metric("后端", backend)
    with col3:
        if backend == "mem0":
            st.metric("向量存储", mem_stats.get("vector_store", "N/A"))

    st.divider()

    # Semantic search
    st.subheader("🔍 语义搜索")
    search_query = st.text_input("搜索记忆", placeholder="输入关键词搜索...")
    if search_query and st.button("搜索"):
        results = memory_client.search(search_query, top_k=10)
        if results:
            for r in results:
                with st.expander(
                    f"[{r.get('id', '?')}] Score: {r.get('score', 0):.2f} — "
                    f"{r.get('content', '')[:80]}..."
                ):
                    st.code(r.get("content", ""), language=None)
                    st.json(r.get("metadata", {}))
        else:
            st.info("无匹配结果")

    st.divider()

    # All memories
    st.subheader("全部记忆")
    memories = memory_client.get_all()
    if memories:
        for mem in memories[:50]:
            mem_id = mem.get("id", "?")
            content = str(mem.get("content", mem))[:120]
            with st.expander(f"[{mem_id}] {content}..."):
                st.code(str(mem.get("content", mem)), language=None)
                if st.button("删除", key=f"del_{mem_id}"):
                    memory_client.delete(mem_id)
                    st.rerun()
    else:
        st.info("暂无记忆数据")


if __name__ == "__main__":
    pass
