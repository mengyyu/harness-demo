"""Skill 导入导出"""

import os
import io
import yaml
import zipfile
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple
from .base import SkillManifest


class SkillImporter:
    """Skill 导入导出管理器

    格式：.harness-skill 压缩包，内部结构:
        skill.yaml          # 清单文件（必需）
        skill.py            # Skill 代码（必需）
        requirements.txt    # Python 依赖（可选）
        prompts/            # Prompt 模板（可选）
    """

    ARCHIVE_EXT = ".harness-skill"
    REQUIRED_FILES = ["skill.yaml", "skill.py"]

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def export_skill(self, skill_name: str, output_path: Optional[str] = None) -> str:
        """导出 Skill 为 .harness-skill 压缩包

        Args:
            skill_name: Skill 名称
            output_path: 输出路径，默认 skills_dir/{name}.harness-skill

        Returns:
            导出的文件路径
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

        if output_path is None:
            output_path = str(self.skills_dir / f"{skill_name}{self.ARCHIVE_EXT}")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in skill_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(self.skills_dir))
                    zf.write(file_path, arcname)

        print(f"[SkillImporter] Exported: {skill_name} → {output_path}")
        return output_path

    def validate_archive(self, archive_path: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """校验 Skill 压缩包

        Returns:
            (是否有效, 错误信息, manifest_dict)
        """
        if not os.path.exists(archive_path):
            return False, f"Archive not found: {archive_path}", None

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                file_list = zf.namelist()

                # 检查必需文件
                skill_name = None
                for name in file_list:
                    if name.endswith("/"):
                        skill_name = name.rstrip("/")
                        break

                if skill_name is None:
                    return False, "Archive must contain a skill directory", None

                # 检查 skill.yaml
                yaml_path = f"{skill_name}/skill.yaml"
                if yaml_path not in file_list:
                    return False, f"Missing {yaml_path}", None

                # 检查 skill.py
                py_path = f"{skill_name}/skill.py"
                if py_path not in file_list:
                    return False, f"Missing {py_path}", None

                # 校验 manifest
                manifest_data = yaml.safe_load(zf.read(yaml_path))
                SkillManifest(**manifest_data)  # Pydantic 校验

                return True, None, manifest_data

        except zipfile.BadZipFile:
            return False, "Invalid zip file", None
        except Exception as e:
            return False, str(e), None

    def import_skill(self, archive_path: str, overwrite: bool = False) -> str:
        """导入 Skill 压缩包

        Args:
            archive_path: .harness-skill 文件路径
            overwrite: 是否覆盖已有 Skill

        Returns:
            导入的 Skill 名称
        """
        # 校验
        valid, error, manifest = self.validate_archive(archive_path)
        if not valid:
            raise ValueError(f"Invalid skill archive: {error}")

        skill_name = manifest["name"]
        target_dir = self.skills_dir / skill_name

        # 检查是否已存在
        if target_dir.exists() and not overwrite:
            raise FileExistsError(f"Skill '{skill_name}' already exists. Use overwrite=True to replace.")

        # 清理旧目录
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # 解压
        with zipfile.ZipFile(archive_path, "r") as zf:
            # 找到 skill 目录前缀
            for name in zf.namelist():
                if name.endswith("/") and not name.startswith("__"):
                    prefix = name
                    break
            else:
                prefix = ""

            # 提取所有文件
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                # 去除前缀目录名，直接放在 skills_dir/{skill_name}/ 下
                rel_path = member
                if prefix and member.startswith(prefix):
                    rel_path = member[len(prefix):]
                target_path = target_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

        print(f"[SkillImporter] Imported: {skill_name} v{manifest['version']} from {archive_path}")
        return skill_name

    def get_archive_info(self, archive_path: str) -> Optional[Dict]:
        """获取压缩包信息（不解压）"""
        valid, error, manifest = self.validate_archive(archive_path)
        if valid:
            return manifest
        return None
