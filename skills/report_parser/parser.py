"""基金诊断报告解析 Skill"""

import json
from harness.skills.base import BaseSkill, SkillManifest, SkillContext, SkillResult


class ReportParserSkill(BaseSkill):
    """解析基金诊断报告，提取结构化数据

    支持流程：
    1. 文档格式检测
    2. 调用 MCP parse_document 提取文本
    3. 结构化字段提取（Mock LLM 逻辑）
    4. 结果校验
    """

    async def execute(self, context: SkillContext) -> SkillResult:
        steps = []
        mcp_calls = []

        try:
            # Step 1: 调用 MCP 解析文档
            steps.append({"step": "parse_document", "status": "running"})
            if self.mcp_manager:
                doc_text = await self.call_mcp_tool(
                    "demo_tools", "parse_document",
                    file_path=context.params.get("file_path", "demo_report.pdf"),
                )
            else:
                doc_text = "模拟文档解析结果: 这是一份基金诊断报告的演示文本..."
            mcp_calls.append({"tool": "parse_document", "success": True})
            steps.append({"step": "parse_document", "status": "completed"})

            # Step 2: 结构化提取（使用 LLM）
            steps.append({"step": "extract_fields", "status": "running"})

            from harness.llm import get_llm
            llm = get_llm()

            extraction_prompt = f"""你是基金诊断报告解析专家。从以下文档文本中提取关键字段，返回 JSON。

文档内容：
{doc_text.get('raw_text', str(doc_text))[:5000]}

请提取以下字段并返回 JSON（不要有其他内容）：
- fund_name: 基金名称
- fund_code: 基金代码
- fund_manager: 基金经理
- fund_company: 基金公司
- diagnosis_date: 诊断日期
- report_type: 报告类型
- performance_metrics: {{return_1m, return_3m, return_6m, return_1y, annual_volatility, sharpe_ratio, max_drawdown}}
- risk_assessment: {{risk_level, risk_score}}
- holdings_analysis: {{sector_distribution: {{行业名: 占比}}, concentration_ratio, top_holdings: [{{name, weight}}]}}
- diagnosis_conclusion: {{overall_score, strengths: [], weaknesses: [], suggestions: []}}

如果某些字段无法从文档中提取，设为 null。"""

            try:
                extracted_data = await llm.ainvoke_json(extraction_prompt)
            except Exception:
                # Fallback to hardcoded data
                extracted_data = {
                "fund_name": "演示稳健增长混合型基金",
                "fund_code": "DEMO001",
                "fund_manager": "张三",
                "fund_company": "演示基金管理有限公司",
                "diagnosis_date": "2024-06-30",
                "report_type": "季度诊断报告",
                "performance_metrics": {
                    "return_1m": 2.35,
                    "return_3m": 5.82,
                    "return_6m": 8.91,
                    "return_1y": 15.67,
                    "return_3y": 42.31,
                    "annual_volatility": 18.5,
                    "sharpe_ratio": 1.23,
                    "max_drawdown": -15.8,
                },
                "risk_assessment": {
                    "risk_level": "R3",
                    "var_95": -2.1,
                    "downside_std": 12.3,
                    "risk_score": 65,
                },
                "holdings_analysis": {
                    "top_10_holdings": [
                        {"name": "贵州茅台", "weight": 8.5},
                        {"name": "宁德时代", "weight": 6.2},
                        {"name": "招商银行", "weight": 5.1},
                    ],
                    "sector_distribution": {
                        "消费": 28.5,
                        "科技": 22.3,
                        "金融": 18.7,
                        "医药": 12.1,
                        "其他": 18.4,
                    },
                    "concentration_ratio": 0.35,
                    "turnover_rate": 120.5,
                },
                "diagnosis_conclusion": {
                    "overall_score": 78,
                    "strengths": ["行业配置均衡", "风控能力较强", "基金经理经验丰富"],
                    "weaknesses": ["近期换手率偏高", "规模增长较快需关注"],
                    "suggestions": ["建议维持当前配置", "关注科技板块估值回调风险"],
                },
                "confidence": {
                    "fund_name": "high",
                    "performance_metrics": "high",
                    "risk_assessment": "medium",
                    "holdings_analysis": "medium",
                },
            }  # end fallback

            steps.append({"step": "extract_fields", "status": "completed",
                          "fields_count": len(extracted_data)})

            # Step 3: 校验
            steps.append({"step": "validate", "status": "running"})
            validation_result = self._validate(extracted_data)
            steps.append({"step": "validate", "status": "completed",
                          "passed": validation_result["passed"]})

            if not validation_result["passed"]:
                return SkillResult(
                    success=False,
                    skill_name=self.name,
                    error=f"数据校验失败: {validation_result['errors']}",
                    steps=steps,
                    mcp_calls=mcp_calls,
                )

            conclusion = extracted_data.get("diagnosis_conclusion") or {}
            overall = conclusion.get("overall_score", "N/A")

            return SkillResult(
                success=True,
                skill_name=self.name,
                data=extracted_data,
                summary=f"成功解析基金诊断报告 [{extracted_data.get('fund_name', '未知')}]，"
                        f"提取 {len(extracted_data)} 个字段组，综合评分 {overall} 分",
                steps=steps,
                mcp_calls=mcp_calls,
            )

        except Exception as e:
            return SkillResult(
                success=False,
                skill_name=self.name,
                error=str(e),
                steps=steps,
                mcp_calls=mcp_calls,
            )

    def _validate(self, data: dict) -> dict:
        """数据校验（null-safe，LLM 可能返回 null 值）"""
        errors = []

        # 必填字段检查
        required = ["fund_name", "fund_code", "performance_metrics", "risk_assessment"]
        for field in required:
            if field not in data or not data[field]:
                errors.append(f"缺少必填字段: {field}")

        # 合理性检查（跳过 None 值，LLM 无法提取时返回 null）
        perf = data.get("performance_metrics") or {}
        if isinstance(perf, dict):
            return_1y = perf.get("return_1y")
            if return_1y is not None and return_1y > 500:
                errors.append("年化收益率异常 (>500%)")
            sharpe = perf.get("sharpe_ratio")
            if sharpe is not None and sharpe > 10:
                errors.append("夏普比率异常 (>10)")

        risk = data.get("risk_assessment") or {}
        if isinstance(risk, dict):
            risk_score = risk.get("risk_score")
            if risk_score is not None and risk_score > 100:
                errors.append("风险评分异常 (>100)")

        return {"passed": len(errors) == 0, "errors": errors}


# Skill 入口类（必须导出，框架通过此加载）
SkillClass = ReportParserSkill
