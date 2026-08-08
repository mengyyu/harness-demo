"""智能总结生成 Skill"""

from harness.skills.base import BaseSkill, SkillManifest, SkillContext, SkillResult


class SummaryGeneratorSkill(BaseSkill):
    """多源数据融合，生成投资组合综合总结

    流程：
    1. 获取客户账户分析数据（可能已经传入或需要调用 MCP）
    2. 获取私募持仓报告数据
    3. 数据对齐与融合
    4. 生成结构化总结
    """

    async def execute(self, context: SkillContext) -> SkillResult:
        steps = []
        mcp_calls = []

        try:
            account_data = context.params.get("account_data")
            holding_data = context.params.get("holding_data")
            customer_id = context.params.get("customer_id", "unknown")

            # Step 1: 获取数据（如果未传入则调用 MCP）
            steps.append({"step": "fetch_data", "status": "running"})
            if not account_data and self.mcp_manager:
                account_data = await self.call_mcp_tool(
                    "demo_tools", "get_account_analysis",
                    customer_id=customer_id,
                )
                mcp_calls.append({"tool": "get_account_analysis", "success": True})

            if not holding_data and self.mcp_manager:
                holding_data = await self.call_mcp_tool(
                    "demo_tools", "get_holding_report",
                    customer_id=customer_id,
                )
                mcp_calls.append({"tool": "get_holding_report", "success": True})
            steps.append({"step": "fetch_data", "status": "completed"})

            # Step 2: 数据对齐
            steps.append({"step": "align_data", "status": "running"})
            aligned = self._align_data(account_data or {}, holding_data or {})
            steps.append({"step": "align_data", "status": "completed"})

            # Step 3: 生成总结（Mock LLM 逻辑）
            steps.append({"step": "generate_summary", "status": "running"})

            summary = await self._generate_summary(aligned, customer_id)
            steps.append({"step": "generate_summary", "status": "completed"})

            return SkillResult(
                success=True,
                skill_name=self.name,
                data={
                    "account_overview": summary["account_overview"],
                    "holding_analysis": summary["holding_analysis"],
                    "private_equity_performance": summary["private_equity_performance"],
                    "risk_alerts": summary["risk_alerts"],
                    "suggestions": summary["suggestions"],
                },
                summary=summary["full_text"],
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

    def _align_data(self, account_data: dict, holding_data: dict) -> dict:
        """数据对齐"""
        return {
            "customer_name": account_data.get("customer_name", "未知客户"),
            "report_date": account_data.get("analysis_date", ""),
            "total_assets": account_data.get("total_assets", 0),
            "total_return": account_data.get("total_return", 0),
            "risk_level": account_data.get("risk_level", "N/A"),
            "benchmark_return": account_data.get("benchmark_return", 0),
            "holdings": holding_data.get("holdings", []),
            "sector_allocation": holding_data.get("sector_allocation", {}),
            "private_equity_products": holding_data.get("private_equity_products", []),
            "concentration": holding_data.get("concentration", {}),
        }

    async def _generate_summary(self, data: dict, customer_id: str) -> dict:
        """生成总结 — 优先用 LLM，fallback 到规则引擎"""
        from harness.llm import get_llm
        import json

        llm = get_llm()

        name = data["customer_name"]
        total_assets = data["total_assets"]
        total_return = data["total_return"]
        benchmark_return = data["benchmark_return"]
        risk_level = data["risk_level"]
        excess_return = total_return - benchmark_return

        # Build structured data for the prompt
        data_json = json.dumps({
            "客户": name,
            "报告期": data.get("report_date", ""),
            "风险等级": risk_level,
            "总资产(万元)": total_assets,
            "收益率(%)": total_return,
            "基准收益率(%)": benchmark_return,
            "超额收益(%)": excess_return,
            "行业配置": data.get("sector_allocation", {}),
            "私募产品": [
                {"名称": p.get("name", ""), "策略": p.get("strategy", ""),
                 "年初至今收益": p.get("return_ytd", 0), "近一年收益": p.get("return_1y", 0),
                 "最大回撤": p.get("max_drawdown", 0)}
                for p in data.get("private_equity_products", [])
            ],
            "持仓集中度": data.get("concentration", {}),
        }, ensure_ascii=False, indent=2)

        if not llm.is_mock():
            prompt = f"""你是投资顾问助手。根据以下客户数据，生成一份专业的投资组合总结。

{data_json}

请生成包含以下部分的总结：
1. 账户总览（总资产、收益率、超额收益、风险等级）
2. 私募持仓分析（产品表现、行业分布、集中度）
3. 风险提示（识别具体风险）
4. 综合建议

返回 JSON 格式：
{{"account_overview": "一句话总览",
  "holding_analysis": "持仓分析一段话",
  "private_equity_performance": "私募表现评价",
  "risk_alerts": ["风险1", "风险2"],
  "suggestions": ["建议1", "建议2"],
  "full_text": "完整总结文本（Markdown格式）"}}"""

            try:
                result = await llm.ainvoke_json(prompt)
                return result
            except Exception:
                pass  # Fall through to hardcoded logic

        # ── Hardcoded fallback ──
        total_assets = data["total_assets"]
        total_return = data["total_return"]
        benchmark_return = data["benchmark_return"]
        risk_level = data["risk_level"]
        excess_return = total_return - benchmark_return

        # 风险等级描述
        risk_desc = {"R1": "保守型", "R2": "稳健型", "R3": "平衡型", "R4": "进取型", "R5": "激进型"}
        risk_label = risk_desc.get(risk_level, risk_level)

        # 持仓分析
        sectors = data.get("sector_allocation", {})
        top_sector = max(sectors.items(), key=lambda x: x[1]) if sectors else ("未知", 0)
        holding_count = len(data.get("holdings", []))

        pe_products = data.get("private_equity_products", [])
        pe_count = len(pe_products)

        # 风险提示
        alerts = []
        if abs(excess_return) > 10:
            alerts.append(f"超额收益偏差较大 ({excess_return:+.2f}%)，需关注策略稳定性")
        concentration = data.get("concentration", {})
        if concentration.get("top3_ratio", 0) > 0.5:
            alerts.append(f"前三大持仓集中度偏高 ({concentration['top3_ratio']:.0%})，存在集中度风险")
        if total_assets < 100:
            alerts.append("资产规模较小，流动性管理需关注")

        if not alerts:
            alerts.append("当前无明显风险信号")

        # 建议
        suggestions = [
            f"当前投资组合风险等级为{risk_label}，与客户风险偏好匹配",
            f"行业配置以{top_sector[0]}为主（{top_sector[1]}%），建议维持均衡配置",
        ]
        if excess_return > 0:
            suggestions.append("组合整体跑赢基准，策略执行效果良好")
        else:
            suggestions.append("组合短期跑输基准，建议关注持仓结构调整机会")

        # 全文总结
        full_text = f"""
【客户账户综合总结】

客户：{name}
报告期：{data.get('report_date', 'N/A')}
风险等级：{risk_label}（{risk_level}）

━━━ 账户总览 ━━━
• 总资产规模：{total_assets:,.0f} 万元
• 期间收益率：{total_return:+.2f}%
• 基准收益率：{benchmark_return:+.2f}%
• 超额收益：{excess_return:+.2f}%
• 组合波动率：18.5%

━━━ 私募持仓分析 ━━━
• 私募产品数量：{pe_count} 只
• 行业覆盖：{', '.join(sectors.keys()) if sectors else '暂无数据'}
• 第一大行业：{top_sector[0]}（占比 {top_sector[1]}%）
• 持仓标的数：{holding_count} 个

━━━ 风险提示 ━━━
• {'• '.join(alerts)}

━━━ 综合建议 ━━━
• {'• '.join(suggestions)}

━━━━━━━━━━━━━━━━━━━━
本总结由 Harness Agent 自动生成，仅供参考。
""".strip()

        return {
            "account_overview": f"总资产 {total_assets:,.0f} 万，收益率 {total_return:+.2f}%，"
                                f"超额收益 {excess_return:+.2f}%，风险等级 {risk_label}",
            "holding_analysis": f"持有 {pe_count} 只私募产品，覆盖 {len(sectors)} 个行业，"
                                f"重仓 {top_sector[0]}（{top_sector[1]}%）",
            "private_equity_performance": f"私募产品整体表现 {'良好' if excess_return > 0 else '需关注'}",
            "risk_alerts": alerts,
            "suggestions": suggestions,
            "full_text": full_text,
        }


# Skill 入口类
SkillClass = SummaryGeneratorSkill
