"""Harness Framework — Skill Management API.

GET    /admin/skills               — List skills
GET    /admin/skills/report         — Skill execution report
POST   /admin/skills/import         — Import skill (.harness-skill zip)
GET    /admin/skills/export/{name}  — Export skill
POST   /admin/skills/{name}/toggle  — Enable/disable skill
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/skills", tags=["admin-skills"])


@router.get("")
async def get_skills():
    """Get all registered skills with status and version info."""
    try:
        from harness.skills.registry import skill_registry
        return {
            "total": len(skill_registry.list_all()),
            "skills": skill_registry.get_stats(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_skill_report(
    skill_name: Optional[str] = Query(default=None),
    hours: int = Query(default=168, ge=1, le=720),
):
    """Get skill execution report with daily aggregation."""
    try:
        from harness.observability.tracer import get_tracer

        tracer = get_tracer()
        return tracer.get_skill_report(skill_name=skill_name, hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_skill(
    file: UploadFile = File(...),
    overwrite: bool = Query(default=False),
):
    """Import a skill from a .harness-skill zip archive."""
    if not file.filename or not file.filename.endswith(".harness-skill"):
        raise HTTPException(
            status_code=400,
            detail="Only .harness-skill files are accepted",
        )

    temp_path = f"/tmp/{file.filename}"
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        from harness.skills.importer import SkillImporter
        importer = SkillImporter(skills_dir="skills")
        skill_name = importer.import_skill(temp_path, overwrite=overwrite)

        # Reload skills registry
        from harness.skills.manager import skill_manager
        skill_manager.load_from_directory()

        return {
            "status": "success",
            "skill_name": skill_name,
            "message": f"Skill '{skill_name}' imported successfully",
        }
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/export/{skill_name}")
async def export_skill(skill_name: str):
    """Export a skill as a .harness-skill zip file download."""
    try:
        from harness.skills.importer import SkillImporter
        importer = SkillImporter(skills_dir="skills")
        output_path = importer.export_skill(skill_name)

        with open(output_path, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{skill_name}.harness-skill"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_name}/toggle")
async def toggle_skill(skill_name: str):
    """Enable or disable a skill."""
    from harness.skills.manager import skill_manager

    result = skill_manager.toggle_skill(skill_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{skill_name}")
async def get_skill_detail(skill_name: str):
    """Get detailed information about a specific skill."""
    from harness.skills.registry import skill_registry

    skill = skill_registry.get(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    return {
        "name": skill.name,
        "manifest": skill.manifest.model_dump(),
        "status": skill.status.value,
    }
