"""Harness Framework — Skill System.

Provides:
- BaseSkill: Abstract base class for all skills
- SkillManifest, SkillContext, SkillResult: Core models
- SkillRegistry: Global skill registration
- SkillManager: Lifecycle management (load, unload, enable/disable)
- SkillImporter: Import/export skills as .harness-skill zip archives
- SkillLoader: Dynamically load skills from disk
"""

from .base import BaseSkill, SkillManifest, SkillResult, SkillContext, SkillStatus
from .registry import SkillRegistry, skill_registry
from .importer import SkillImporter
from .loader import SkillLoader
from .manager import SkillManager, skill_manager

__all__ = [
    "BaseSkill",
    "SkillManifest",
    "SkillResult",
    "SkillContext",
    "SkillStatus",
    "SkillRegistry",
    "skill_registry",
    "SkillImporter",
    "SkillLoader",
    "SkillManager",
    "skill_manager",
]
