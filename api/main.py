"""FastAPI REST API — Harness 对话接口 + 管理 API"""

import sys
import os
import io
from pathlib import Path

# 确保 harness 模块可导入
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from harness.agent.loop import harness_agent
from harness.skills.registry import skill_registry
from harness.skills.importer import SkillImporter
from harness.mcp.manager import mcp_manager
from harness.memory.store import memory_store
from harness.intent.router import intent_router
from harness.tracker import execution_tracker

# ═══════════════════════════════════════════════════
# App 初始化
# ═══════════════════════════════════════════════════

app = FastAPI(
    title="Harness Framework API",
    description="Agent 编排框架 — 对话接口与管理 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

skill_importer = SkillImporter(skills_dir="skills")


# ═══════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    status: str
    intent: str
    confidence: float
    matched_skill: str
    plan: List[str]
    steps: List[Dict]
    output: str
    latency_ms: float
    error: Optional[str] = None


class IntentTestRequest(BaseModel):
    message: str


class IntentConfigRequest(BaseModel):
    name: str
    description: str = ""
    keywords: List[str] = []
    negative_keywords: List[str] = []
    bound_skill: str = ""
    priority: int = 0
    examples: List[str] = []
    is_active: bool = True


# ═══════════════════════════════════════════════════
# 对话 API
# ═══════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口 — 发送消息给 Agent，返回执行结果"""
    result = await harness_agent.run(
        user_input=request.message,
        user_id=request.user_id,
    )
    return ChatResponse(**result)


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "version": "0.1.0",
        "skills_registered": len(skill_registry.list_all()),
        "mcp_servers": len(mcp_manager.list_servers()),
        "total_executions": len(execution_tracker.records),
    }


# ═══════════════════════════════════════════════════
# Agent 运行报表 API
# ═══════════════════════════════════════════════════

@app.get("/admin/agents/logs")
async def get_agent_logs(limit: int = 50, skill_name: str = None, status: str = None):
    """获取 Agent 运行日志"""
    records = execution_tracker.get_records(limit=limit, skill_name=skill_name, status=status)
    return {
        "total": len(records),
        "records": [
            {
                "record_id": r.record_id,
                "session_id": r.session_id,
                "user_id": r.user_id,
                "intent": r.intent,
                "skill_name": r.skill_name,
                "status": r.status,
                "input_text": r.input_text[:200],
                "output_text": r.output_text[:500],
                "latency_ms": r.latency_ms,
                "steps_count": len(r.steps),
                "mcp_calls_count": len(r.mcp_calls),
                "timestamp": r.timestamp,
                "error": r.error,
            }
            for r in records
        ],
    }


@app.get("/admin/agents/report")
async def get_agent_report(hours: int = 24):
    """获取 Agent 运行报表"""
    return execution_tracker.get_agent_report(hours=hours)


@app.get("/admin/agents/detail/{session_id}")
async def get_agent_detail(session_id: str):
    """获取单次 Agent 执行详情"""
    for r in execution_tracker.records:
        if r.session_id == session_id:
            return {
                "record_id": r.record_id,
                "session_id": r.session_id,
                "user_id": r.user_id,
                "intent": r.intent,
                "skill_name": r.skill_name,
                "status": r.status,
                "input_text": r.input_text,
                "output_text": r.output_text,
                "steps": r.steps,
                "mcp_calls": r.mcp_calls,
                "latency_ms": r.latency_ms,
                "timestamp": r.timestamp,
                "error": r.error,
            }
    raise HTTPException(status_code=404, detail="Session not found")


# ═══════════════════════════════════════════════════
# Skill 管理 API
# ═══════════════════════════════════════════════════

@app.get("/admin/skills")
async def get_skills():
    """获取所有 Skill"""
    return {
        "total": len(skill_registry.list_all()),
        "skills": skill_registry.get_stats(),
    }


@app.get("/admin/skills/report")
async def get_skill_report(skill_name: str = None, hours: int = 168):
    """获取 Skill 运行报表"""
    return execution_tracker.get_skill_report(skill_name=skill_name, hours=hours)


@app.post("/admin/skills/import")
async def import_skill(file: UploadFile = File(...), overwrite: bool = False):
    """导入 Skill（上传 .harness-skill 文件）"""
    if not file.filename.endswith(".harness-skill"):
        raise HTTPException(status_code=400, detail="Only .harness-skill files are accepted")

    # 保存临时文件
    temp_path = f"/tmp/{file.filename}"
    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        skill_name = skill_importer.import_skill(temp_path, overwrite=overwrite)
        return {"status": "success", "skill_name": skill_name, "message": f"Skill '{skill_name}' imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/admin/skills/export/{skill_name}")
async def export_skill(skill_name: str):
    """导出 Skill 为 .harness-skill 文件"""
    try:
        output_path = skill_importer.export_skill(skill_name)
        # 读取并返回文件
        with open(output_path, "rb") as f:
            content = f.read()

        from fastapi.responses import Response
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{skill_name}.harness-skill"'
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/skills/{skill_name}/toggle")
async def toggle_skill(skill_name: str):
    """启用/禁用 Skill"""
    from harness.skills.base import SkillStatus
    skill = skill_registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.status == SkillStatus.ACTIVE:
        skill.status = SkillStatus.DISABLED
    else:
        skill.status = SkillStatus.ACTIVE

    return {"skill_name": skill_name, "status": skill.status.value}


# ═══════════════════════════════════════════════════
# 意图库 API
# ═══════════════════════════════════════════════════

@app.get("/admin/intents")
async def get_intents():
    """获取意图库"""
    return {
        "total": len(intent_router.intents),
        "intents": intent_router.export_intents(),
    }


@app.post("/admin/intents")
async def create_intent(config: IntentConfigRequest):
    """新增意图"""
    from harness.intent.router import IntentRule
    rule = IntentRule(**config.model_dump())
    intent_router.add_intent(rule)
    return {"status": "success", "intent_name": rule.name}


@app.put("/admin/intents/{name}")
async def update_intent(name: str, config: IntentConfigRequest):
    """更新意图"""
    success = intent_router.update_intent(name, **config.model_dump())
    if not success:
        raise HTTPException(status_code=404, detail="Intent not found")
    return {"status": "success", "intent_name": name}


@app.delete("/admin/intents/{name}")
async def delete_intent(name: str):
    """删除意图"""
    success = intent_router.delete_intent(name)
    if not success:
        raise HTTPException(status_code=404, detail="Intent not found")
    return {"status": "success"}


@app.post("/admin/intents/test")
async def test_intent(request: IntentTestRequest):
    """测试意图路由"""
    intents, confidences, skills = intent_router.route(request.message)
    return {
        "message": request.message,
        "results": [
            {"intent": i, "confidence": round(c, 2), "skill": s}
            for i, c, s in zip(intents, confidences, skills)
        ],
    }


# ═══════════════════════════════════════════════════
# MCP 管理 API
# ═══════════════════════════════════════════════════

@app.get("/admin/mcp/servers")
async def get_mcp_servers():
    """获取 MCP Server 列表"""
    return mcp_manager.get_stats()


@app.get("/admin/mcp/tools")
async def get_mcp_tools(server_name: str = None):
    """获取 MCP Tool 列表"""
    return {
        "tools": mcp_manager.list_tools(server_name=server_name),
    }


# ═══════════════════════════════════════════════════
# 记忆管理 API
# ═══════════════════════════════════════════════════

@app.get("/admin/memory")
async def get_memories(user_id: str = None):
    """获取记忆列表"""
    memories = memory_store.get_all_memories(user_id=user_id)
    return {"total": len(memories), "memories": memories[:100]}


@app.get("/admin/memory/stats")
async def get_memory_stats():
    """获取记忆统计"""
    return memory_store.get_stats()


@app.delete("/admin/memory/{memory_id}")
async def delete_memory(memory_id: str):
    """删除记忆"""
    success = memory_store.delete(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "success"}


# ═══════════════════════════════════════════════════
# 启动
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
