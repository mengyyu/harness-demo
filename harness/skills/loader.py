"""Harness Framework — Skill Loader.

Dynamically discovers and loads skill modules from the filesystem.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Optional

import yaml

from .base import BaseSkill, SkillManifest

logger = logging.getLogger(__name__)


class SkillLoader:
    """Discovers and loads skills from a directory on disk.

    Expected directory structure:
        skills/
        ├── report_parser/
        │   ├── skill.yaml          # Manifest
        │   └── parser.py           # Skill class implementation
        └── summary_generator/
            ├── skill.yaml
            └── generator.py
    """

    def __init__(self, skills_dir: str = "skills"):
        self._skills_dir = Path(skills_dir)
        self._skills_dir.mkdir(parents=True, exist_ok=True)

    def discover(self) -> list[Path]:
        """Discover skill directories.

        Returns:
            List of Path objects pointing to skill directories.
        """
        if not self._skills_dir.exists():
            return []

        skill_dirs = []
        for entry in self._skills_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("__"):
                yaml_path = entry / "skill.yaml"
                if yaml_path.exists():
                    skill_dirs.append(entry)

        return skill_dirs

    def load_manifest(self, skill_dir: Path) -> Optional[SkillManifest]:
        """Load and validate a skill manifest from a directory.

        Args:
            skill_dir: Path to the skill directory.

        Returns:
            SkillManifest if valid, None otherwise.
        """
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            logger.warning("No skill.yaml found in %s", skill_dir)
            return None

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            manifest = SkillManifest(**data)
            return manifest

        except yaml.YAMLError as e:
            logger.error("Invalid YAML in %s: %s", yaml_path, e)
            return None
        except Exception as e:
            logger.error("Failed to load manifest from %s: %s", skill_dir, e)
            return None

    def load_skill_module(self, skill_dir: Path) -> Optional[type]:
        """Load the SkillClass from a skill directory.

        Looks for a 'SkillClass' attribute or a BaseSkill subclass
        in any .py file in the directory.

        Args:
            skill_dir: Path to the skill directory.

        Returns:
            A BaseSkill subclass, or None if not found.
        """
        # Find Python files (excluding __init__.py)
        py_files = [
            p for p in skill_dir.glob("*.py")
            if p.name != "__init__.py"
        ]
        if not py_files:
            logger.warning("No Python files found in %s", skill_dir)
            return None

        for py_path in py_files:
            try:
                module_name = f"skills.{skill_dir.name}.{py_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_path)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Check for explicit SkillClass export
                if hasattr(module, "SkillClass"):
                    skill_cls = module.SkillClass
                    if issubclass(skill_cls, BaseSkill):
                        logger.debug("Loaded SkillClass from %s", py_path)
                        return skill_cls

                # Auto-discover BaseSkill subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                    ):
                        logger.debug("Auto-discovered %s in %s", attr.__name__, py_path)
                        return attr

            except Exception as e:
                logger.error("Failed to load skill from %s: %s", py_path, e)
                continue

        return None

    def load_single(self, skill_dir: Path) -> Optional[BaseSkill]:
        """Load a single skill from its directory.

        Args:
            skill_dir: Path to the skill directory.

        Returns:
            A BaseSkill instance, or None if loading fails.
        """
        manifest = self.load_manifest(skill_dir)
        if manifest is None:
            return None

        skill_cls = self.load_skill_module(skill_dir)
        if skill_cls is None:
            logger.warning("No skill class found in %s", skill_dir)
            return None

        try:
            skill = skill_cls(manifest)
            logger.info("Loaded skill: %s v%s", skill.name, skill.manifest.version)
            return skill
        except Exception as e:
            logger.error("Failed to instantiate skill %s: %s", manifest.name, e)
            return None

    def discover_and_load(self) -> list[BaseSkill]:
        """Discover all skill directories and load them.

        Returns:
            List of loaded BaseSkill instances.
        """
        skill_dirs = self.discover()
        loaded = []

        for skill_dir in skill_dirs:
            skill = self.load_single(skill_dir)
            if skill is not None:
                loaded.append(skill)

        logger.info("Loaded %d/%d skills", len(loaded), len(skill_dirs))
        return loaded
