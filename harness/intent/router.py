"""意图路由器 — 关键词匹配 + 规则路由"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json
import os


@dataclass
class IntentRule:
    """意图规则"""
    name: str                          # 意图名称
    description: str                   # 描述
    keywords: List[str]                # 触发关键词
    negative_keywords: List[str] = field(default_factory=list)  # 排除关键词
    bound_skill: str = ""              # 绑定的 Skill
    priority: int = 0                  # 优先级（越大越优先）
    examples: List[str] = field(default_factory=list)  # 示例问法
    is_active: bool = True
    hit_count: int = 0


class IntentRouter:
    """意图路由器

    策略：
    1. 关键词匹配计算得分
    2. 排除词降权
    3. 多意图时返回 Top-N
    4. 未知意图返回 "unknown"
    """

    # 默认意图库
    DEFAULT_INTENTS = [
        IntentRule(
            name="parse_report",
            description="解析基金诊断报告",
            keywords=["解析", "报告", "基金", "诊断", "分析这份", "PDF", "文档", "提取"],
            negative_keywords=["总结"],
            bound_skill="report_parser",
            priority=10,
            examples=["帮我解析这份基金诊断报告", "分析这个PDF文档", "提取报告里的数据"],
        ),
        IntentRule(
            name="generate_summary",
            description="生成客户总结",
            keywords=["总结", "汇总", "账户", "持仓", "私募", "客户", "概况", "一键生成"],
            negative_keywords=["解析", "报告"],
            bound_skill="summary_generator",
            priority=10,
            examples=["帮我生成王总的账户总结", "汇总一下私募持仓情况", "客户账户分析总结"],
        ),
        IntentRule(
            name="query_status",
            description="查询系统运行状态",
            keywords=["状态", "运行", "统计", "报表", "成功率", "调用量", "Skill", "Agent"],
            negative_keywords=[],
            bound_skill="status_query",
            priority=5,
            examples=["今天Agent运行情况怎么样", "Skill调用统计", "查看系统报表"],
        ),
        IntentRule(
            name="manage_skill",
            description="管理 Skill",
            keywords=["导入", "导出", "安装", "卸载", "启用", "禁用"],
            negative_keywords=[],
            bound_skill="skill_manager",
            priority=5,
            examples=["导入一个新的Skill", "导出报告解析Skill", "启用总结生成Skill"],
        ),
    ]

    def __init__(self):
        self.intents: Dict[str, IntentRule] = {}
        self._load_defaults()

    def _load_defaults(self):
        """加载默认意图"""
        for intent in self.DEFAULT_INTENTS:
            self.intents[intent.name] = intent

    # ── 意图 CRUD ───────────────────────────────────

    def add_intent(self, rule: IntentRule) -> None:
        """添加意图"""
        self.intents[rule.name] = rule

    def update_intent(self, name: str, **kwargs) -> bool:
        """更新意图"""
        if name not in self.intents:
            return False
        rule = self.intents[name]
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        return True

    def delete_intent(self, name: str) -> bool:
        """删除意图"""
        if name in self.intents:
            del self.intents[name]
            return True
        return False

    def get_intent(self, name: str) -> Optional[IntentRule]:
        """获取意图"""
        return self.intents.get(name)

    def list_intents(self) -> List[IntentRule]:
        """列出所有意图"""
        return list(self.intents.values())

    # ── 路由 ────────────────────────────────────────

    def route(self, user_input: str) -> Tuple[List[str], List[float], List[str]]:
        """路由用户输入到意图

        Args:
            user_input: 用户输入文本

        Returns:
            (matched_intents, confidences, matched_skills)
        """
        results = []
        for intent in self.intents.values():
            if not intent.is_active:
                continue
            score = self._calculate_score(user_input, intent)
            if score > 0:
                results.append((intent, score))

        if not results:
            return (["unknown"], [0.0], [""])

        # 按得分排序
        results.sort(key=lambda x: x[1], reverse=True)
        max_score = results[0][1]

        # 返回得分 > 阈值的结果（支持多意图）
        threshold = max_score * 0.3  # 相对阈值
        matched = [(i, s) for i, s in results if s >= threshold]

        intents = [i.name for i, _ in matched]
        confidences = [min(s / 10.0, 1.0) for _, s in matched]  # 归一化到 0-1
        skills = [i.bound_skill for i, _ in matched]

        # 更新命中计数
        for intent, _ in matched:
            intent.hit_count += 1

        return intents, confidences, skills

    def route_single(self, user_input: str) -> Tuple[str, float, str]:
        """单意图路由（取最高分），低置信时 fallback 到 LLM"""
        return self._route_single_sync(user_input)

    async def route_single_async(self, user_input: str) -> Tuple[str, float, str]:
        """Async version with LLM fallback."""
        intents, confidences, skills = self.route(user_input)
        if not intents or intents[0] == "unknown" or confidences[0] < 0.3:
            # Keyword matching failed or low confidence → try LLM
            return await self._llm_route(user_input)
        return intents[0], confidences[0], skills[0]

    def _route_single_sync(self, user_input: str) -> Tuple[str, float, str]:
        """同步版本（不触发 LLM）"""
        intents, confidences, skills = self.route(user_input)
        if not intents or intents[0] == "unknown":
            return ("unknown", 0.0, "")
        return intents[0], confidences[0], skills[0]

    # ── 评分 ────────────────────────────────────────

    async def _llm_route(self, user_input: str) -> Tuple[str, float, str]:
        """LLM-based intent classification fallback.

        Used when keyword matching produces low confidence results.
        """
        from harness.llm import get_llm

        llm = get_llm()

        # Build intent catalog
        intents_desc = "\n".join(
            f"- {i.name}: {i.description} (e.g., {', '.join(i.examples[:2])})"
            for i in self.intents.values() if i.is_active
        )

        prompt = f"""你是意图分类器。根据用户输入，判断意图并返回 JSON。

可用意图：
{intents_desc}

用户输入：{user_input}

返回 JSON 格式（不要有其他内容）：
{{"intent": "意图名称", "confidence": 0.0-1.0}}

如果无法匹配任何意图，返回 intent="unknown"。"""

        try:
            result = await llm.ainvoke_json(prompt)
            intent_name = result.get("intent", "unknown")
            confidence = float(result.get("confidence", 0.5))
            intent = self.intents.get(intent_name)
            skill = intent.bound_skill if intent else ""
            return (intent_name, min(confidence, 1.0), skill)
        except Exception:
            return ("unknown", 0.0, "")

    def _calculate_score(self, user_input: str, intent: IntentRule) -> float:
        """计算输入与意图的匹配得分"""
        text = user_input.lower()
        score = 0.0

        # 关键词正向匹配
        for kw in intent.keywords:
            if kw.lower() in text:
                score += 2.0
            # 部分匹配
            if len(kw) >= 2:
                for i in range(len(kw) - 1):
                    if kw[i:i+2] in text:
                        score += 0.3

        # 排除词负向匹配
        for nkw in intent.negative_keywords:
            if nkw.lower() in text:
                score -= 3.0

        # 优先级加成（仅在有实际匹配时生效）
        if score > 0:
            score += intent.priority * 0.1

        return max(score, 0.0)

    # ── 导入导出 ────────────────────────────────────

    def export_intents(self) -> List[Dict]:
        """导出意图库为 JSON"""
        return [
            {
                "name": i.name,
                "description": i.description,
                "keywords": i.keywords,
                "negative_keywords": i.negative_keywords,
                "bound_skill": i.bound_skill,
                "priority": i.priority,
                "examples": i.examples,
                "is_active": i.is_active,
                "hit_count": i.hit_count,
            }
            for i in self.intents.values()
        ]

    def import_intents(self, data: List[Dict]) -> int:
        """从 JSON 导入意图"""
        count = 0
        for item in data:
            rule = IntentRule(**item)
            self.intents[rule.name] = rule
            count += 1
        return count

    def get_stats(self) -> Dict:
        """获取路由统计"""
        total_hits = sum(i.hit_count for i in self.intents.values())
        return {
            "total_intents": len(self.intents),
            "active_intents": sum(1 for i in self.intents.values() if i.is_active),
            "total_hits": total_hits,
            "intents": [
                {
                    "name": i.name,
                    "description": i.description,
                    "bound_skill": i.bound_skill,
                    "hit_count": i.hit_count,
                    "is_active": i.is_active,
                }
                for i in sorted(self.intents.values(), key=lambda x: x.hit_count, reverse=True)
            ],
        }


# 全局意图路由器单例
intent_router = IntentRouter()
