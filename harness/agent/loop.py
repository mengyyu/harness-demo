"""Agent Loop — 基于 LangGraph 的 Plan→Execute→Observe→Reflect 循环"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated

from ..skills.registry import skill_registry
from ..mcp.manager import mcp_manager
from ..memory.store import memory_store
from ..intent.router import intent_router
from ..tracker import execution_tracker
from ..config import config


# ═══════════════════════════════════════════════════
# State 定义
# ═══════════════════════════════════════════════════

class AgentState(TypedDict):
    """Agent 状态"""
    session_id: str
    user_id: str
    user_input: str

    # 意图路由结果
    intent: str
    confidence: float
    matched_skill: str
    all_intents: List[str]
    all_skills: List[str]

    # 执行状态
    plan_steps: List[str]          # 计划执行步骤
    current_step: int              # 当前步骤索引
    loop_count: int                # 已执行循环次数

    # 中间结果
    tool_results: List[Dict]       # MCP Tool 调用结果
    skill_results: List[Dict]      # Skill 执行结果
    memory_context: Dict           # 检索到的记忆

    # 输出
    final_output: str
    status: str                    # running, success, failed
    error_message: str

    # 步骤详细记录
    steps_log: List[Dict]


# ═══════════════════════════════════════════════════
# Node 函数
# ═══════════════════════════════════════════════════

async def _generate_plan(intent: str, user_input: str) -> list:
    """Generate execution plan using LLM, with hardcoded fallback."""
    from harness.llm import get_llm

    llm = get_llm()

    if llm.is_mock():
        # Hardcoded fallback for mock mode
        plans = {
            "parse_report": [
                "检测文档格式并选择合适的解析器",
                "调用 MCP parse_document 提取文本和表格",
                "执行 report_parser skill 结构化提取关键字段",
                "校验提取结果的完整性和合理性",
            ],
            "generate_summary": [
                "调用 MCP get_account_analysis 获取客户账户数据",
                "调用 MCP get_holding_report 获取私募持仓数据",
                "对齐两份数据源的时间维度和资产分类标准",
                "生成包含账户总览、持仓分析、风险提示的综合总结",
            ],
            "query_status": [
                "查询 Agent 运行统计（调用量、成功率、延迟）",
                "查询 Skill 运行统计（调用排行、错误详情）",
                "汇总系统运行状态并输出报表",
            ],
            "manage_skill": [
                "解析 Skill 管理指令的具体操作",
                "执行对应的 Skill 操作（导入/导出/启用/禁用）",
            ],
        }
        return plans.get(intent, ["分析用户需求", "执行对应操作", "返回结果"])

    # Real LLM plan generation
    prompt = f"""你是任务规划器。根据用户意图和输入，将任务分解为 3-5 个具体步骤。

意图：{intent}
用户输入：{user_input}

返回 JSON 数组格式（不要有其他内容）：
["步骤1", "步骤2", "步骤3"]"""

    try:
        plan = await llm.ainvoke_json(prompt)
        if isinstance(plan, list) and len(plan) > 0:
            return plan
    except Exception:
        pass

    # Fallback
    return ["执行 {intent} 操作"]


async def intent_route_node(state: AgentState) -> AgentState:
    """节点 1: 意图路由"""
    execution_tracker.add_step(state["session_id"], "intent_route",
                               input_data={"user_input": state["user_input"]})

    # Try keyword routing first, fall back to LLM if confidence < 0.3
    intent, confidence, skill = await intent_router.route_single_async(state["user_input"])
    all_intents, all_confidences, all_skills = intent_router.route(state["user_input"])

    state["intent"] = intent
    state["confidence"] = confidence
    state["matched_skill"] = skill
    state["all_intents"] = all_intents
    state["all_skills"] = all_skills

    state["steps_log"].append({
        "step": "intent_route",
        "intent": intent,
        "confidence": round(confidence, 2),
        "skill": skill,
    })

    execution_tracker.add_step(state["session_id"], "intent_route",
                               output_data={"intent": intent, "skill": skill})

    # 更新 tracker 中的 intent
    execution_tracker.update_record(state["session_id"], intent=intent, skill_name=skill)

    return state


async def memory_retrieve_node(state: AgentState) -> AgentState:
    """节点 2: 记忆检索"""
    execution_tracker.add_step(state["session_id"], "memory_retrieve")

    memories = memory_store.search(
        query=state["user_input"],
        user_id=state["user_id"],
        session_id=state["session_id"],
    )
    state["memory_context"] = memories

    mem_summary = {
        "session": len(memories["session_context"]),
        "user": len(memories["user_context"]),
        "entity": len(memories["entity_context"]),
    }
    state["steps_log"].append({"step": "memory_retrieve", "results": mem_summary})
    execution_tracker.add_step(state["session_id"], "memory_retrieve", output_data=mem_summary)

    return state


async def plan_node(state: AgentState) -> AgentState:
    """节点 3: Plan — 制定执行计划"""
    execution_tracker.add_step(state["session_id"], "plan")

    intent = state["intent"]

    # Use LLM to generate plan steps (falls back to hardcoded if mock)
    state["plan_steps"] = await _generate_plan(intent, state["user_input"])

    state["current_step"] = 0
    state["loop_count"] = 0

    state["steps_log"].append({
        "step": "plan",
        "plan": state["plan_steps"],
    })
    execution_tracker.add_step(state["session_id"], "plan",
                               output_data={"plan": state["plan_steps"]})

    return state


async def execute_node(state: AgentState) -> AgentState:
    """节点 4: Execute — 执行当前步骤

    在第一个 plan step 时执行完整的 Skill 逻辑。
    后续 plan step 仅记录日志（模拟逐步执行，实际工作在第一步已完成）。
    """
    step_idx = state["current_step"]
    total_steps = len(state["plan_steps"])

    if step_idx >= total_steps:
        return state

    step_name = state["plan_steps"][step_idx]
    execution_tracker.add_step(state["session_id"], f"execute_step_{step_idx}",
                               input_data={"step": step_name, "step_index": step_idx})

    intent = state["intent"]
    skill_name = state["matched_skill"]

    # ── 只在第一步执行实际 Skill 逻辑 ──
    if step_idx == 0:
        try:
            if intent == "parse_report" and skill_name == "report_parser":
                skill = skill_registry.get("report_parser")
                if skill:
                    from ..skills.base import SkillContext
                    context = SkillContext(
                        session_id=state["session_id"],
                        user_id=state["user_id"],
                        intent=intent,
                        params={"file_path": state["user_input"]},
                        memories=state["memory_context"].get("entity_context", []),
                    )
                    result = await skill.execute(context)
                    state["skill_results"].append({
                        "skill": skill_name,
                        "success": result.success,
                        "data": result.data,
                        "summary": result.summary,
                        "steps": result.steps,
                        "error": result.error,
                    })

            elif intent == "generate_summary" and skill_name == "summary_generator":
                customer_id = "wang_001"
                if "李" in state["user_input"]:
                    customer_id = "li_001"
                elif "张" in state["user_input"]:
                    customer_id = "zhang_001"

                t0 = time.time()
                account_data = await mcp_manager.call_tool("demo_tools", "get_account_analysis",
                                                           {"customer_id": customer_id})
                execution_tracker.add_mcp_call(
                    state["session_id"], "get_account_analysis",
                    {"customer_id": customer_id}, account_data,
                    (time.time() - t0) * 1000,
                )

                t0 = time.time()
                holding_data = await mcp_manager.call_tool("demo_tools", "get_holding_report",
                                                           {"customer_id": customer_id})
                execution_tracker.add_mcp_call(
                    state["session_id"], "get_holding_report",
                    {"customer_id": customer_id}, holding_data,
                    (time.time() - t0) * 1000,
                )

                skill = skill_registry.get("summary_generator")
                if skill:
                    from ..skills.base import SkillContext
                    context = SkillContext(
                        session_id=state["session_id"],
                        user_id=state["user_id"],
                        intent=intent,
                        params={
                            "customer_id": customer_id,
                            "account_data": account_data,
                            "holding_data": holding_data,
                        },
                        memories=state["memory_context"].get("user_context", []),
                    )
                    result = await skill.execute(context)
                    state["skill_results"].append({
                        "skill": skill_name,
                        "success": result.success,
                        "data": result.data,
                        "summary": result.summary,
                        "steps": result.steps,
                        "error": result.error,
                    })

            elif intent == "query_status":
                summary = execution_tracker.get_summary()
                skill_stats = skill_registry.get_stats()
                state["skill_results"].append({
                    "skill": "status_query",
                    "success": True,
                    "data": {"agent_summary": summary, "skill_list": skill_stats},
                    "summary": f"系统运行状态: 最近24小时执行 {summary['total_executions']} 次, "
                               f"成功率 {summary['success_rate']}%",
                })

            elif intent == "manage_skill":
                state["skill_results"].append({
                    "skill": "skill_manager",
                    "success": True,
                    "data": {"registered_skills": len(skill_registry.list_all())},
                    "summary": f"Skill 管理: 当前已注册 {len(skill_registry.list_all())} 个 Skill",
                })

            else:
                state["skill_results"].append({
                    "skill": "unknown_handler",
                    "success": True,
                    "data": {},
                    "summary": f"未识别的意图 '{intent}'。试试:\n"
                               f"- 解析基金诊断报告\n- 生成客户持仓总结\n- 查询系统运行状态",
                })

        except Exception as e:
            state["skill_results"].append({
                "skill": skill_name,
                "success": False,
                "error": str(e),
            })

    # ── 记录当前步骤完成 ──
    last_result = state["skill_results"][-1] if state["skill_results"] else {}
    state["steps_log"].append({
        "step": f"execute[{step_idx}/{total_steps}]",
        "plan_step": step_name,
        "success": last_result.get("success", True),
        "detail": f"✓ {step_name}" if last_result.get("success", True) else f"✗ {step_name}",
    })

    state["current_step"] += 1
    return state


def observe_node(state: AgentState) -> AgentState:
    """节点 5: Observe — 观察执行结果"""
    execution_tracker.add_step(state["session_id"], "observe")

    # 检查最后一个 skill result
    if state["skill_results"]:
        last_result = state["skill_results"][-1]
        success = last_result["success"]
    else:
        success = False

    # 所有步骤是否执行完
    all_done = state["current_step"] >= len(state["plan_steps"])

    state["steps_log"].append({
        "step": "observe",
        "all_done": all_done,
        "last_success": success,
    })
    execution_tracker.add_step(state["session_id"], "observe",
                               output_data={"all_done": all_done, "success": success})

    return state


def reflect_node(state: AgentState) -> AgentState:
    """节点 6: Reflect — 反思与调整"""
    execution_tracker.add_step(state["session_id"], "reflect")

    state["loop_count"] += 1

    # 检查是否失败
    if state["skill_results"] and not state["skill_results"][-1]["success"]:
        # 简化反思：如果不是最后一步，跳过当前失败步骤继续
        state["steps_log"].append({
            "step": "reflect",
            "action": "skip_failed_step",
            "detail": f"步骤 {state['current_step']} 失败，跳过继续",
        })
    else:
        state["steps_log"].append({
            "step": "reflect",
            "action": "continue",
            "detail": "继续下一步",
        })

    execution_tracker.add_step(state["session_id"], "reflect",
                               output_data={"loop": state["loop_count"]})

    return state


def output_node(state: AgentState) -> AgentState:
    """节点 7: Output — 生成最终输出"""
    execution_tracker.add_step(state["session_id"], "output")

    # 汇总所有 Skill 结果
    parts = []
    for result in state["skill_results"]:
        if result.get("summary"):
            parts.append(result["summary"])
        elif result.get("data"):
            import json
            parts.append(json.dumps(result["data"], ensure_ascii=False, indent=2))

    # 失败的 Skill 结果 → 输出错误信息
    failed_results = [r for r in state["skill_results"] if not r.get("success")]
    if failed_results and not parts:
        state["final_output"] = f"执行失败: {failed_results[-1].get('error', '未知错误')}"
    elif not parts:
        # 没有执行任何 Skill
        state["final_output"] = f"没有匹配到可执行的操作。意图: {state['intent']}"
    else:
        state["final_output"] = "\n\n".join(parts)

    state["status"] = "success"
    if state["skill_results"] and all(not r["success"] for r in state["skill_results"]):
        state["status"] = "failed"
        state["error_message"] = state["skill_results"][-1].get("error", "Unknown error")

    state["steps_log"].append({
        "step": "output",
        "status": state["status"],
        "output_length": len(state["final_output"]),
    })
    execution_tracker.add_step(state["session_id"], "output",
                               output_data={"status": state["status"]})

    return state


# ═══════════════════════════════════════════════════
# 条件边逻辑
# ═══════════════════════════════════════════════════

def should_continue(state: AgentState) -> str:
    """判断下一步"""
    # 所有步骤完成 → output
    if state["current_step"] >= len(state["plan_steps"]):
        return "output"

    # 最后一步失败 → output (不再重试)
    if state["skill_results"] and not state["skill_results"][-1]["success"]:
        if state["current_step"] >= len(state["plan_steps"]):
            return "output"

    # 超过最大循环次数 → output
    if state["loop_count"] >= config.agent_max_loops:
        state["steps_log"].append({
            "step": "decision",
            "action": "force_output",
            "reason": f"超过最大循环次数 ({config.agent_max_loops})",
        })
        return "output"

    # 继续执行下一步
    return "execute"


# ═══════════════════════════════════════════════════
# Graph 构建
# ═══════════════════════════════════════════════════

def build_agent_graph() -> StateGraph:
    """构建 Agent Loop StateGraph"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("intent_route", intent_route_node)
    workflow.add_node("memory_retrieve", memory_retrieve_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("observe", observe_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("output", output_node)

    # 设置入口
    workflow.set_entry_point("intent_route")

    # 顺序边
    workflow.add_edge("intent_route", "memory_retrieve")
    workflow.add_edge("memory_retrieve", "plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "observe")

    # 条件边：observe 后决定继续执行还是输出
    workflow.add_conditional_edges(
        "observe",
        should_continue,
        {
            "execute": "execute",
            "output": "output",
        },
    )

    # observe → reflect 条件（失败时反思）
    # 简化：直接 observe → should_continue 即可

    workflow.add_edge("output", END)

    return workflow.compile()


# ═══════════════════════════════════════════════════
# Agent 主入口
# ═══════════════════════════════════════════════════

class HarnessAgent:
    """Harness Agent 主类"""

    def __init__(self):
        self.graph = build_agent_graph()
        self._session_counter = 0

    async def run(self, user_input: str, user_id: str = "default") -> Dict[str, Any]:
        """运行 Agent

        Args:
            user_input: 用户输入
            user_id: 用户 ID

        Returns:
            包含完整执行结果的字典
        """
        self._session_counter += 1
        session_id = f"session_{self._session_counter}_{int(time.time())}"

        # 开始追踪
        execution_tracker.start_session(session_id, user_id, user_input)

        # 初始化状态
        initial_state: AgentState = {
            "session_id": session_id,
            "user_id": user_id,
            "user_input": user_input,
            "intent": "",
            "confidence": 0.0,
            "matched_skill": "",
            "all_intents": [],
            "all_skills": [],
            "plan_steps": [],
            "current_step": 0,
            "loop_count": 0,
            "tool_results": [],
            "skill_results": [],
            "memory_context": {},
            "final_output": "",
            "status": "running",
            "error_message": "",
            "steps_log": [],
        }

        # 执行 Graph
        t_start = time.time()
        try:
            final_state = await self.graph.ainvoke(initial_state)
        except Exception as e:
            latency_ms = (time.time() - t_start) * 1000
            execution_tracker.finish_session(
                session_id, status="failed",
                output_text=str(e), error=str(e),
            )
            execution_tracker.update_record(session_id, latency_ms=latency_ms)
            return {
                "session_id": session_id,
                "status": "failed",
                "error": str(e),
                "steps": [],
                "output": f"执行失败: {str(e)}",
            }

        latency_ms = (time.time() - t_start) * 1000
        execution_tracker.finish_session(
            session_id,
            status=final_state.get("status", "success"),
            output_text=final_state.get("final_output", ""),
            error=final_state.get("error_message"),
        )
        execution_tracker.update_record(session_id, latency_ms=latency_ms)

        # 保存到记忆
        memory_store.add(
            content=f"用户输入: {user_input}\n输出: {final_state.get('final_output', '')[:500]}",
            user_id=user_id,
            session_id=session_id,
            memory_type="session",
        )

        return {
            "session_id": session_id,
            "status": final_state.get("status", "success"),
            "intent": final_state.get("intent", ""),
            "confidence": final_state.get("confidence", 0.0),
            "matched_skill": final_state.get("matched_skill", ""),
            "plan": final_state.get("plan_steps", []),
            "steps": final_state.get("steps_log", []),
            "skill_results": final_state.get("skill_results", []),
            "output": final_state.get("final_output", ""),
            "latency_ms": round(latency_ms, 1),
            "error": final_state.get("error_message", ""),
        }

    async def run_batch(self, inputs: List[str], user_id: str = "default") -> List[Dict]:
        """批量运行"""
        results = []
        for user_input in inputs:
            result = await self.run(user_input, user_id)
            results.append(result)
        return results


# 全局 Agent 单例
harness_agent = HarnessAgent()
