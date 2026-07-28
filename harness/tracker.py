"""执行追踪器 — 模拟 LangFuse 记录 Agent/Skill 运行"""

import time
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class ExecutionRecord:
    """一次执行记录"""
    record_id: str
    session_id: str
    user_id: str
    intent: str
    skill_name: str
    status: str               # running, success, failed
    input_text: str
    output_text: str
    steps: List[Dict] = field(default_factory=list)
    mcp_calls: List[Dict] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ExecutionTracker:
    """执行追踪器

    职责：
    1. 记录每次 Agent/Skill 执行
    2. 提供聚合查询（报表用）
    3. 内存存储，重启丢失
    """

    def __init__(self, max_records: int = 1000):
        self.records: List[ExecutionRecord] = []
        self.max_records = max_records
        self._active_sessions: Dict[str, ExecutionRecord] = {}

    # ── 记录 ────────────────────────────────────────

    def start_session(self, session_id: str, user_id: str,
                      input_text: str) -> ExecutionRecord:
        """开始一次执行会话"""
        record = ExecutionRecord(
            record_id=str(uuid.uuid4())[:8],
            session_id=session_id,
            user_id=user_id,
            intent="",
            skill_name="",
            status="running",
            input_text=input_text,
            output_text="",
        )
        self._active_sessions[session_id] = record
        return record

    def update_record(self, session_id: str, **kwargs) -> Optional[ExecutionRecord]:
        """更新执行记录"""
        record = self._active_sessions.get(session_id)
        if not record:
            # 尝试在已完成记录中查找
            for r in self.records:
                if r.session_id == session_id:
                    record = r
                    break
        if not record:
            return None

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        return record

    def finish_session(self, session_id: str, status: str = "success",
                       output_text: str = "", error: str = None) -> Optional[ExecutionRecord]:
        """结束执行会话"""
        record = self._active_sessions.pop(session_id, None)
        if not record:
            return None

        record.status = status
        record.output_text = output_text
        record.error = error
        record.timestamp = datetime.now().isoformat()

        self.records.append(record)
        # 超过上限则清理旧记录
        while len(self.records) > self.max_records:
            self.records.pop(0)

        return record

    def add_step(self, session_id: str, step_name: str,
                 input_data: Dict = None, output_data: Dict = None,
                 status: str = "completed") -> None:
        """添加执行步骤（对应 Agent Loop 的每一步）"""
        record = self._active_sessions.get(session_id)
        if record:
            record.steps.append({
                "name": step_name,
                "status": status,
                "input": input_data,
                "output": output_data,
                "timestamp": datetime.now().isoformat(),
            })

    def add_mcp_call(self, session_id: str, tool_name: str,
                     arguments: Dict, result: Any, latency_ms: float) -> None:
        """记录 MCP Tool 调用"""
        record = self._active_sessions.get(session_id)
        if record:
            record.mcp_calls.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": str(result)[:500],  # 截断
                "latency_ms": latency_ms,
                "timestamp": datetime.now().isoformat(),
            })

    # ── 查询（报表）──────────────────────────────────

    def get_records(self, limit: int = 50, skill_name: str = None,
                    status: str = None) -> List[ExecutionRecord]:
        """查询执行记录"""
        results = self.records
        if skill_name:
            results = [r for r in results if r.skill_name == skill_name]
        if status:
            results = [r for r in results if r.status == status]
        return list(reversed(results))[:limit]

    def get_summary(self, hours: int = 24) -> Dict:
        """获取摘要统计"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [r for r in self.records
                  if datetime.fromisoformat(r.timestamp) > cutoff]

        if not recent:
            return {"total_executions": 0, "message": "No executions in this period"}

        success = [r for r in recent if r.status == "success"]
        failed = [r for r in recent if r.status == "failed"]

        # 按 Skill 统计
        skill_stats = {}
        for r in recent:
            if r.skill_name not in skill_stats:
                skill_stats[r.skill_name] = {"total": 0, "success": 0, "failed": 0}
            skill_stats[r.skill_name]["total"] += 1
            if r.status == "success":
                skill_stats[r.skill_name]["success"] += 1
            elif r.status == "failed":
                skill_stats[r.skill_name]["failed"] += 1

        # 按意图统计
        intent_stats = {}
        for r in recent:
            intent_stats[r.intent] = intent_stats.get(r.intent, 0) + 1

        # 延迟统计
        latencies = [r.latency_ms for r in recent if r.latency_ms > 0]
        latencies.sort()
        p50 = latencies[len(latencies)//2] if latencies else 0
        p99 = latencies[int(len(latencies)*0.99)] if len(latencies) > 1 else (latencies[0] if latencies else 0)

        return {
            "period_hours": hours,
            "total_executions": len(recent),
            "success_count": len(success),
            "failed_count": len(failed),
            "success_rate": round(len(success) / len(recent) * 100, 1),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "p50_latency_ms": p50,
            "p99_latency_ms": p99,
            "skill_stats": [
                {"skill_name": k, **v, "success_rate": round(v["success"]/v["total"]*100, 1)}
                for k, v in sorted(skill_stats.items(), key=lambda x: x[1]["total"], reverse=True)
            ],
            "intent_distribution": dict(sorted(intent_stats.items(), key=lambda x: x[1], reverse=True)),
        }

    def get_skill_report(self, skill_name: str = None, hours: int = 168) -> Dict:
        """获取 Skill 运行报表"""
        cutoff = datetime.now() - timedelta(hours=hours)
        records = [r for r in self.records
                   if datetime.fromisoformat(r.timestamp) > cutoff]
        if skill_name:
            records = [r for r in records if r.skill_name == skill_name]

        # 按天聚合
        daily = {}
        for r in records:
            day = r.timestamp[:10]
            if day not in daily:
                daily[day] = {"total": 0, "success": 0, "failed": 0, "avg_latency": 0}
            daily[day]["total"] += 1
            if r.status == "success":
                daily[day]["success"] += 1
            elif r.status == "failed":
                daily[day]["failed"] += 1

        return {
            "skill_name": skill_name or "all",
            "period_hours": hours,
            "daily_stats": [
                {"date": k, **v, "success_rate": round(v["success"]/v["total"]*100, 1) if v["total"] else 0}
                for k, v in sorted(daily.items())
            ],
            "total_calls": len(records),
        }

    def get_agent_report(self, hours: int = 24) -> Dict:
        """获取 Agent 运行报表"""
        return self.get_summary(hours=hours)

    def clear(self) -> int:
        """清空记录"""
        count = len(self.records)
        self.records.clear()
        self._active_sessions.clear()
        return count


# 全局 Execution Tracker 单例
execution_tracker = ExecutionTracker()
