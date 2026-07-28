"""Skill 注册中心"""

from typing import Dict, List, Optional
from .base import BaseSkill, SkillManifest


class SkillRegistry:
    """Skill 注册中心 — 管理所有已安装 Skill 的生命周期"""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}  # name -> skill instance

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill"""
        if skill.name in self._skills:
            existing = self._skills[skill.name]
            # 版本比较：如果新版本更高则替换
            if self._version_gt(skill.manifest.version, existing.manifest.version):
                print(f"[SkillRegistry] Upgrading '{skill.name}': {existing.manifest.version} → {skill.manifest.version}")
            else:
                print(f"[SkillRegistry] Keeping existing '{skill.name}' v{existing.manifest.version} (newer than v{skill.manifest.version})")
                return
        self._skills[skill.name] = skill
        print(f"[SkillRegistry] Registered: {skill.name} v{skill.manifest.version}")

    def unregister(self, name: str) -> bool:
        """卸载一个 Skill"""
        if name in self._skills:
            del self._skills[name]
            print(f"[SkillRegistry] Unregistered: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[BaseSkill]:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def get_by_intent(self, intent: str) -> List[BaseSkill]:
        """根据意图查找匹配的 Skill"""
        matched = []
        for skill in self._skills.values():
            if intent in skill.manifest.intents:
                matched.append(skill)
        # 按意图匹配精确度排序（精确匹配优先于通配）
        return matched

    def list_all(self) -> List[BaseSkill]:
        """列出所有 Skill"""
        return list(self._skills.values())

    def get_stats(self) -> List[Dict]:
        """获取所有 Skill 的统计信息"""
        return [skill.to_dict() for skill in self._skills.values()]

    def inject_mcp(self, mcp_manager) -> None:
        """为所有 Skill 注入 MCP Manager"""
        for skill in self._skills.values():
            skill.set_mcp_manager(mcp_manager)

    @staticmethod
    def _version_gt(v1: str, v2: str) -> bool:
        """比较语义版本号 v1 > v2"""
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            # 补齐长度
            while len(parts1) < 3:
                parts1.append(0)
            while len(parts2) < 3:
                parts2.append(0)
            return parts1 > parts2
        except ValueError:
            return False


# 全局 Skill 注册中心单例
skill_registry = SkillRegistry()
