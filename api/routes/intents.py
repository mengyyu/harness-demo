"""Harness Framework — Intent Library API.

GET    /admin/intents             — List intents
POST   /admin/intents             — Create intent
PUT    /admin/intents/{name}      — Update intent
DELETE /admin/intents/{name}      — Delete intent
POST   /admin/intents/test        — Test intent routing
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/admin/intents", tags=["admin-intents"])


class IntentConfigRequest(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    keywords: list[str] = []
    negative_keywords: list[str] = []
    skill_name: str = ""
    priority: int = 0
    enabled: bool = True
    examples: list[str] = []


class IntentTestRequest(BaseModel):
    message: str


# ── CRUD ─────────────────────────────────────────────────

@router.get("")
async def get_intents():
    """Get all configured intents."""
    from harness.intent.router import intent_router
    return {
        "total": len(intent_router.intents),
        "intents": intent_router.export_intents(),
    }


@router.post("")
async def create_intent(config: IntentConfigRequest):
    """Create a new intent rule."""
    from harness.intent.router import IntentRule, intent_router

    rule = IntentRule(
        name=config.name,
        description=config.description,
        keywords=config.keywords,
        negative_keywords=config.negative_keywords,
        bound_skill=config.skill_name,
        priority=config.priority,
        examples=config.examples,
        is_active=config.enabled,
    )
    intent_router.add_intent(rule)

    # Sync to DB
    try:
        from harness.intent.store import IntentStore
        from harness.intent.models import IntentModel
        store = IntentStore()
        all_intents = [
            IntentModel(
                name=i.name,
                display_name=i.description,
                description=i.description,
                keywords=i.keywords,
                negative_keywords=i.negative_keywords,
                skill_name=i.bound_skill,
                priority=i.priority,
                enabled=i.is_active,
                examples=i.examples,
                hit_count=i.hit_count,
            )
            for i in intent_router.list_intents()
        ]
        store.sync_to_db(all_intents)
    except Exception:
        pass

    return {"status": "success", "intent_name": rule.name}


@router.put("/{name}")
async def update_intent(name: str, config: IntentConfigRequest):
    """Update an existing intent rule."""
    from harness.intent.router import intent_router

    success = intent_router.update_intent(
        name,
        description=config.description,
        keywords=config.keywords,
        negative_keywords=config.negative_keywords,
        bound_skill=config.skill_name,
        priority=config.priority,
        is_active=config.enabled,
        examples=config.examples,
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Intent '{name}' not found")

    return {"status": "success", "intent_name": name}


@router.delete("/{name}")
async def delete_intent(name: str):
    """Delete an intent rule."""
    from harness.intent.router import intent_router

    success = intent_router.delete_intent(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Intent '{name}' not found")

    return {"status": "success"}


# ── Test Routing ─────────────────────────────────────────

@router.post("/test")
async def test_intent_route(request: IntentTestRequest):
    """Test intent routing with a message.

    Returns the matched intents with confidence scores.
    """
    from harness.intent.router import intent_router

    intents, confidences, skills = intent_router.route(request.message)
    return {
        "message": request.message,
        "results": [
            {"intent": i, "confidence": round(c, 2), "skill": s}
            for i, c, s in zip(intents, confidences, skills)
        ],
    }
