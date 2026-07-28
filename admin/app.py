"""Streamlit 管理后台 — Agent 运行报表、Skill 管理、意图库配置"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from harness.agent.loop import harness_agent
from harness.skills.registry import skill_registry
from harness.skills.importer import SkillImporter
from harness.mcp.manager import mcp_manager
from harness.memory.store import memory_store
from harness.intent.router import intent_router, IntentRule
from harness.tracker import execution_tracker

# ═══════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════

st.set_page_config(
    page_title="Harness 管理后台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🤖 Harness Framework — 管理后台")
st.caption("Agent 编排框架 · Skill 管理 · 意图库配置 · 运行报表")

skill_importer = SkillImporter(skills_dir="skills")

# ═══════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════

with st.sidebar:
    st.header("📋 导航")
    tab = st.radio(
        "选择页面",
        ["📊 Dashboard", "📝 Agent 运行", "🔧 Skill 管理", "🎯 意图库", "💬 对话测试", "🧠 记忆管理"],
        label_visibility="collapsed",
    )

    st.divider()
    st.metric("已注册 Skill", len(skill_registry.list_all()))
    st.metric("MCP Server", len(mcp_manager.list_servers()))
    st.metric("MCP Tools", len(mcp_manager.list_tools()))
    st.metric("执行记录", len(execution_tracker.records))
    st.metric("意图数量", len(intent_router.intents))

# ═══════════════════════════════════════════════════
# Tab 1: Dashboard
# ═══════════════════════════════════════════════════

if tab == "📊 Dashboard":
    st.header("📊 系统运行 Dashboard")

    # 汇总指标
    summary = execution_tracker.get_summary(hours=24)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("24h 执行次数", summary.get("total_executions", 0))
    with col2:
        st.metric("成功率", f"{summary.get('success_rate', 0)}%")
    with col3:
        st.metric("平均延迟", f"{summary.get('avg_latency_ms', 0):.0f} ms")
    with col4:
        st.metric("失败次数", summary.get("failed_count", 0))

    st.divider()

    # Skill 统计
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Skill 调用排行")
        skill_stats = summary.get("skill_stats", [])
        if skill_stats:
            df_skills = pd.DataFrame(skill_stats)
            st.dataframe(df_skills, use_container_width=True, hide_index=True)
        else:
            st.info("暂无 Skill 运行数据")

    with col_right:
        st.subheader("意图分布")
        intent_dist = summary.get("intent_distribution", {})
        if intent_dist:
            df_intent = pd.DataFrame(
                [{"意图": k, "次数": v} for k, v in intent_dist.items()]
            )
            st.bar_chart(df_intent.set_index("意图"))
        else:
            st.info("暂无意图分布数据")

    # MCP 状态
    st.divider()
    st.subheader("MCP Server 状态")
    mcp_stats = mcp_manager.get_stats()
    for srv in mcp_stats.get("servers", []):
        color = "🟢" if srv["status"] == "connected" else "🔴"
        st.text(f"{color} {srv['name']} — {srv['tool_count']} tools: {', '.join(srv['tools'])}")

# ═══════════════════════════════════════════════════
# Tab 2: Agent 运行
# ═══════════════════════════════════════════════════

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

    records = execution_tracker.get_records(
        limit=limit,
        skill_name=None if skill_filter == "全部" else skill_filter,
        status=None if status_filter == "全部" else status_filter,
    )

    if records:
        for r in records:
            status_icon = "✅" if r.status == "success" else "❌"
            with st.expander(
                f"{status_icon} [{r.timestamp[:19]}] {r.intent} → {r.skill_name} "
                f"({r.latency_ms:.0f}ms) — {r.input_text[:50]}..."
            ):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.text("输入:")
                    st.code(r.input_text, language=None)
                with col_b:
                    st.text("输出:")
                    st.code(r.output_text[:1000], language=None)

                st.caption(f"Session: {r.session_id} | Steps: {len(r.steps)} | "
                          f"MCP Calls: {len(r.mcp_calls)}")

                if r.steps:
                    st.text("执行步骤:")
                    st.json(r.steps)

                if r.error:
                    st.error(f"错误: {r.error}")
    else:
        st.info("暂无执行记录，试试去「对话测试」页面发送一条消息")

# ═══════════════════════════════════════════════════
# Tab 3: Skill 管理
# ═══════════════════════════════════════════════════

elif tab == "🔧 Skill 管理":
    st.header("🔧 Skill 管理")

    # Skill 列表
    st.subheader("已安装 Skill")
    skills_data = skill_registry.get_stats()
    if skills_data:
        df = pd.DataFrame(skills_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # Skill 运行报表
    st.subheader("Skill 运行报表")
    skill_name_report = st.selectbox(
        "选择 Skill（留空看全部）",
        ["全部"] + [s.name for s in skill_registry.list_all()],
    )
    report = execution_tracker.get_skill_report(
        skill_name=None if skill_name_report == "全部" else skill_name_report,
        hours=168,
    )
    daily = report.get("daily_stats", [])
    if daily:
        df_daily = pd.DataFrame(daily)
        st.line_chart(df_daily.set_index("date")[["total", "success", "failed"]])
    else:
        st.info("暂无运行数据")

    st.divider()

    # 导入导出
    col_import, col_export = st.columns(2)

    with col_import:
        st.subheader("📥 导入 Skill")
        uploaded_file = st.file_uploader("上传 .harness-skill 文件", type=["harness-skill", "zip"])
        if uploaded_file:
            temp_path = f"/tmp/{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            try:
                skill_name = skill_importer.import_skill(temp_path, overwrite=True)
                st.success(f"✅ Skill '{skill_name}' 导入成功！刷新页面后生效")
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
                output_path = skill_importer.export_skill(export_name)
                with open(output_path, "rb") as f:
                    st.download_button(
                        "⬇️ 下载文件",
                        data=f.read(),
                        file_name=f"{export_name}.harness-skill",
                        mime="application/zip",
                    )
                st.success(f"导出成功: {output_path}")
            except Exception as e:
                st.error(f"导出失败: {e}")

# ═══════════════════════════════════════════════════
# Tab 4: 意图库
# ═══════════════════════════════════════════════════

elif tab == "🎯 意图库":
    st.header("🎯 意图库配置")

    # 意图列表
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

    # 测试路由
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

    # 新增/编辑意图
    st.subheader("➕ 新增意图")
    with st.form("new_intent_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("意图名称", placeholder="my_intent")
            new_desc = st.text_input("描述", placeholder="意图描述")
        with col2:
            new_skill = st.text_input("绑定 Skill", placeholder="skill_name")
            new_priority = st.number_input("优先级", min_value=0, max_value=100, value=5)

        new_keywords = st.text_input("关键词（逗号分隔）", placeholder="关键词1, 关键词2")
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

# ═══════════════════════════════════════════════════
# Tab 5: 对话测试
# ═══════════════════════════════════════════════════

elif tab == "💬 对话测试":
    st.header("💬 对话测试")

    st.markdown("""
    试试以下输入：
    - `帮我解析这份基金诊断报告`
    - `生成王总账户的持仓总结`
    - `查询系统运行状态`
    - `今天Skill调用统计`
    """)

    user_input = st.chat_input("输入你的需求...")

    # 显示历史
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if user_input:
        with st.spinner("Agent 执行中..."):
            result = harness_agent.run(user_input)  # 注意: 在 streamlit 中直接用 async 不太方便，用同步包装
            # 由于 run 是 async，在 streamlit 中需要特殊处理
            # 简单起见，我们直接在脚本中使用 asyncio
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(harness_agent.run(user_input))
            loop.close()

        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
        })
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": result,
        })

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                result = msg["content"]
                st.success(f"意图: {result.get('intent', 'N/A')} | "
                          f"Skill: {result.get('matched_skill', 'N/A')} | "
                          f"延迟: {result.get('latency_ms', 0):.0f}ms")

                with st.expander("📋 执行计划"):
                    st.json(result.get("plan", []))

                with st.expander("📝 详细步骤"):
                    st.json(result.get("steps", []))

                st.subheader("输出结果")
                st.markdown(result.get("output", "无输出"))

# ═══════════════════════════════════════════════════
# Tab 6: 记忆管理
# ═══════════════════════════════════════════════════

elif tab == "🧠 记忆管理":
    st.header("🧠 记忆管理")

    # 统计
    mem_stats = memory_store.get_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("会话记忆", mem_stats["session_memories"])
    with col2:
        st.metric("用户记忆", mem_stats["user_memories"])
    with col3:
        st.metric("实体记忆", mem_stats["entity_memories"])

    st.divider()

    # 记忆列表
    st.subheader("记忆列表")
    memories = memory_store.get_all_memories()
    if memories:
        for mem in memories[:50]:
            with st.expander(
                f"[{mem['id']}] {mem['content'][:80]}... "
                f"— {datetime.fromtimestamp(mem['timestamp']).strftime('%m-%d %H:%M')}"
            ):
                st.text("完整内容:")
                st.code(mem["content"], language=None)
                st.json(mem.get("metadata", {}))
                col_del, _ = st.columns([1, 5])
                with col_del:
                    if st.button(f"删除", key=f"del_{mem['id']}"):
                        memory_store.delete(mem["id"])
                        st.rerun()
    else:
        st.info("暂无记忆数据，去对话测试页面发送几条消息吧")


# ═══════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    # Streamlit 在调用时自动启动
    pass
