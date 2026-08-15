"""Harness Framework — 用户工作台 (User-facing App)

面向业务用户（投顾/理财师）的日常操作界面：
- 💬 智能助手：与 Agent 自然语言对话
- 📄 报告解析：上传基金诊断报告，一键提取结构化数据
- 📊 客户总结：选择客户，一键生成投资组合综合总结
- 🕐 历史记录：查看历史执行记录

Streamlit Cloud 部署：Main file path = user/app.py
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

# ══════════════════════════════════════════════════════════
# 页面配置
# ══════════════════════════════════════════════════════════

st.set_page_config(
    page_title="投顾智能助手",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════
# 框架初始化（缓存，只初始化一次）
# ══════════════════════════════════════════════════════════


@st.cache_resource
def init_framework():
    """初始化 Harness 框架"""
    from run_demo import init_harness
    init_harness()
    return True


init_framework()


@st.cache_resource
def get_agent():
    """获取 Agent 单例"""
    from harness.agent.loop import harness_agent
    return harness_agent


def run_agent(user_input: str) -> dict:
    """同步包装：在 Streamlit 中运行 async Agent"""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(get_agent().run(user_input))
        return result
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════
# 侧边栏
# ══════════════════════════════════════════════════════════

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/briefcase.png", width=48)
    st.title("投顾智能助手")
    st.caption("AI 投资顾问工作台")

    st.divider()

    page = st.radio(
        "导航",
        ["💬 智能助手", "📄 报告解析", "📊 客户总结", "🕐 历史记录"],
        label_visibility="collapsed",
    )

    st.divider()

    # 系统状态
    from harness.skills.registry import skill_registry
    from harness.llm import get_llm

    st.subheader("系统状态")
    st.markdown(f"🧠 **模型**: {get_llm().model_name}")
    st.markdown(f"🔧 **能力**: {len(skill_registry.list_all())} 个 Skill")

    st.divider()
    st.caption("v0.2.0 · 仅供演示")


# ══════════════════════════════════════════════════════════
# 页面 1: 智能助手（对话）
# ══════════════════════════════════════════════════════════

if page == "💬 智能助手":
    st.header("💬 智能助手")
    st.caption("用自然语言描述你的需求，AI 会自动理解意图并执行")

    # 初始化聊天历史
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 快捷指令
    quick_prompts = [
        "帮我解析一份基金诊断报告",
        "生成王总账户的持仓总结",
        "分析李总的私募持仓风险",
        "查询系统最近运行状态",
    ]

    cols = st.columns(4)
    for i, prompt in enumerate(quick_prompts):
        with cols[i]:
            if st.button(f"⚡ {prompt[:14]}...", key=f"quick_{i}", use_container_width=True):
                st.session_state.pending_input = prompt

    st.divider()

    # 显示历史消息
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 输入框
    user_input = st.chat_input("输入你的需求，例如：生成王总的持仓总结...")
    pending = st.session_state.pop("pending_input", None)
    if pending:
        user_input = pending

    if user_input:
        # 用户消息
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Agent 执行
        with st.chat_message("assistant"):
            with st.spinner("🤖 Agent 执行中..."):
                result = run_agent(user_input)

            if result["status"] == "success":
                st.markdown(result["output"])

                # 执行详情（折叠）
                with st.expander(f"📋 执行详情（意图: {result['intent']} · 耗时 {result['latency_ms']:.0f}ms）"):
                    st.markdown(f"**计划步骤：**")
                    for step in result.get("plan", []):
                        st.markdown(f"- {step}")
                    st.markdown("**执行轨迹：**")
                    for s in result.get("steps", []):
                        st.caption(f"{s.get('step', '')} — {s.get('detail', '')}")
            else:
                st.error(f"执行失败: {result.get('error', '未知错误')}")
                if result.get("output"):
                    st.markdown(result["output"])

        st.session_state.chat_history.append(
            {"role": "assistant", "content": result.get("output", "执行失败")}
        )


# ══════════════════════════════════════════════════════════
# 页面 2: 报告解析
# ══════════════════════════════════════════════════════════

elif page == "📄 报告解析":
    st.header("📄 基金诊断报告解析")
    st.caption("上传基金诊断报告，AI 自动提取业绩、风险、持仓等结构化数据")

    col_upload, col_result = st.columns([1, 2])

    with col_upload:
        st.subheader("上传报告")
        uploaded_file = st.file_uploader(
            "支持 PDF / Word / 图片 / 文本",
            type=["pdf", "docx", "doc", "png", "jpg", "txt"],
            help="Demo 模式下文件内容不会被真实解析",
        )

        if uploaded_file:
            st.success(f"✅ 已上传: {uploaded_file.name} ({uploaded_file.size // 1024} KB)")

            if st.button("🚀 开始解析", type="primary", use_container_width=True):
                with st.spinner("解析中..."):
                    result = run_agent(f"帮我解析这份基金诊断报告: {uploaded_file.name}")
                    st.session_state.parse_result = result
                    st.session_state.parse_file = uploaded_file.name

    with col_result:
        st.subheader("解析结果")

        if "parse_result" in st.session_state:
            result = st.session_state.parse_result

            if result["status"] == "success":
                # 从 skill_results 提取结构化数据
                skill_data = None
                for sr in result.get("skill_results", []):
                    if sr.get("data"):
                        skill_data = sr["data"]

                if skill_data:
                    # 基本信息卡片
                    st.markdown("#### 📌 基本信息")
                    info_cols = st.columns(4)
                    with info_cols[0]:
                        st.metric("基金名称", skill_data.get("fund_name", "N/A"))
                    with info_cols[1]:
                        st.metric("基金代码", skill_data.get("fund_code", "N/A"))
                    with info_cols[2]:
                        st.metric("基金经理", skill_data.get("fund_manager", "N/A"))
                    with info_cols[3]:
                        st.metric("诊断日期", skill_data.get("diagnosis_date", "N/A"))

                    # 业绩指标
                    perf = skill_data.get("performance_metrics", {})
                    if perf:
                        st.markdown("#### 📈 业绩表现")
                        perf_cols = st.columns(5)
                        metrics = [
                            ("近1月", perf.get("return_1m")),
                            ("近3月", perf.get("return_3m")),
                            ("近1年", perf.get("return_1y")),
                            ("夏普比率", perf.get("sharpe_ratio")),
                            ("最大回撤", perf.get("max_drawdown")),
                        ]
                        for i, (label, value) in enumerate(metrics):
                            with perf_cols[i]:
                                suffix = "%" if value is not None and "return" in label or "回撤" in label else ""
                                st.metric(label, f"{value}{suffix}" if value is not None else "N/A")

                    # 风险与结论
                    risk = skill_data.get("risk_assessment", {})
                    conclusion = skill_data.get("diagnosis_conclusion", {})
                    if risk or conclusion:
                        st.markdown("#### ⚠️ 风险评估与诊断结论")
                        col_risk, col_concl = st.columns(2)
                        with col_risk:
                            st.markdown(f"**风险等级**: {risk.get('risk_level', 'N/A')}")
                            st.markdown(f"**风险评分**: {risk.get('risk_score', 'N/A')}")
                        with col_concl:
                            st.markdown(f"**综合评分**: {conclusion.get('overall_score', 'N/A')}")
                            strengths = conclusion.get("strengths", [])
                            if strengths:
                                st.markdown(f"**优势**: {'、'.join(strengths)}")
                            weaknesses = conclusion.get("weaknesses", [])
                            if weaknesses:
                                st.markdown(f"**劣势**: {'、'.join(weaknesses)}")

                    # 完整 JSON
                    with st.expander("查看完整结构化数据"):
                        st.json(skill_data)
                else:
                    st.markdown(result["output"])
            else:
                st.error(f"解析失败: {result.get('error', '未知错误')}")
        else:
            st.info("👈 上传报告后点击「开始解析」")

    # 示例报告
    st.divider()
    st.subheader("没有报告文件？试试示例")
    if st.button("🔍 解析示例报告", use_container_width=True):
        with st.spinner("解析中..."):
            result = run_agent("帮我解析这份基金诊断报告")
            st.session_state.parse_result = result
            st.session_state.parse_file = "demo_report.pdf"
            st.rerun()


# ══════════════════════════════════════════════════════════
# 页面 3: 客户总结
# ══════════════════════════════════════════════════════════

elif page == "📊 客户总结":
    st.header("📊 客户投资组合总结")
    st.caption("选择客户，一键生成包含账户分析 + 私募持仓的综合总结")

    # 客户选择
    customers = {
        "王总": "wang_001",
        "李总": "li_001",
        "张总": "zhang_001",
    }

    col_selector, col_action = st.columns([1, 1])
    with col_selector:
        selected_customer = st.selectbox("选择客户", list(customers.keys()))
    with col_action:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📝 生成总结", type="primary", use_container_width=True):
            with st.spinner(f"正在生成 {selected_customer} 的综合总结..."):
                result = run_agent(f"生成{selected_customer}账户的持仓总结")
                st.session_state.summary_result = result
                st.session_state.summary_customer = selected_customer

    st.divider()

    if "summary_result" in st.session_state:
        result = st.session_state.summary_result

        if result["status"] == "success":
            # 显示执行信息
            st.caption(
                f"客户: {st.session_state.summary_customer} · "
                f"意图: {result['intent']} · "
                f"耗时: {result['latency_ms']:.0f}ms"
            )
            st.markdown(result["output"])

            # 结构化摘要卡片
            skill_data = None
            for sr in result.get("skill_results", []):
                if sr.get("data"):
                    skill_data = sr["data"]

            if skill_data:
                st.divider()
                st.markdown("#### 📌 结构化摘要")

                tab_overview, tab_risk, tab_suggest = st.tabs(["总览", "风险提示", "建议"])

                with tab_overview:
                    st.markdown(skill_data.get("account_overview", "N/A"))
                    st.markdown(skill_data.get("holding_analysis", "N/A"))

                with tab_risk:
                    for alert in skill_data.get("risk_alerts", []):
                        st.warning(alert)

                with tab_suggest:
                    for sugg in skill_data.get("suggestions", []):
                        st.success(sugg)
        else:
            st.error(f"生成失败: {result.get('error', '未知错误')}")
    else:
        st.info("👆 选择客户后点击「生成总结」")

    # 客户速览
    st.divider()
    st.subheader("客户速览")
    demo_cols = st.columns(3)
    for i, (name, cid) in enumerate(customers.items()):
        with demo_cols[i]:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                if cid == "wang_001":
                    st.caption("总资产 5,000 万 · R3 平衡型 · 3 只私募")
                elif cid == "li_001":
                    st.caption("总资产 8,000 万 · R2 稳健型 · 2 只私募")
                else:
                    st.caption("总资产 12,000 万 · R4 进取型 · 3 只私募")


# ══════════════════════════════════════════════════════════
# 页面 4: 历史记录
# ══════════════════════════════════════════════════════════

elif page == "🕐 历史记录":
    st.header("🕐 历史执行记录")
    st.caption("查看 Agent 的历史执行情况")

    from harness.tracker import execution_tracker

    records = execution_tracker.get_records(limit=50)

    if records:
        # 汇总统计
        summary = execution_tracker.get_summary(hours=24)
        stat_cols = st.columns(4)
        with stat_cols[0]:
            st.metric("24h 执行", summary.get("total_executions", 0))
        with stat_cols[1]:
            st.metric("成功率", f"{summary.get('success_rate', 0)}%")
        with stat_cols[2]:
            st.metric("平均延迟", f"{summary.get('avg_latency_ms', 0):.0f}ms")
        with stat_cols[3]:
            st.metric("失败数", summary.get("failed_count", 0))

        st.divider()

        for r in records:
            icon = "✅" if r.status == "success" else "❌"
            with st.expander(
                f"{icon} {r.timestamp[:19]} · {r.intent} → {r.skill_name} ({r.latency_ms:.0f}ms)"
            ):
                st.caption(f"输入: {r.input_text[:200]}")
                st.caption(f"输出: {r.output_text[:300]}")
                if r.steps:
                    steps_summary = " → ".join(s.get("step", "") for s in r.steps[:6])
                    st.caption(f"步骤: {steps_summary}")
                if r.error:
                    st.error(r.error)
    else:
        st.info("暂无执行记录。去「智能助手」页面发一条消息试试")
