"""Harness Framework — Intent Persistence.

Loads intents from YAML config and syncs to the database.
Provides import/export for the intent library.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from config.settings import settings
from .models import IntentModel

logger = logging.getLogger(__name__)


class IntentStore:
    """Manages intent persistence between YAML files and database.

    Priority order:
    1. Database (SQLite/Postgres) — runtime source of truth
    2. YAML config file — initial seed on first run
    3. Code defaults — fallback if neither DB nor YAML available
    """

    def __init__(self, yaml_path: str | None = None):
        self._yaml_path = Path(yaml_path or settings.INTENTS_CONFIG_PATH)

    # ── Load ─────────────────────────────────────────────

    def load_from_yaml(self) -> list[IntentModel]:
        """Load intent definitions from the YAML config file.

        Returns:
            List of IntentModel instances.
        """
        if not self._yaml_path.exists():
            logger.info("Intents YAML not found at %s; using defaults", self._yaml_path)
            return self._get_defaults()

        try:
            with open(self._yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            intents = []
            for item in data.get("intents", []):
                model = IntentModel(**item)
                intents.append(model)

            logger.info("Loaded %d intents from %s", len(intents), self._yaml_path)
            return intents

        except Exception as e:
            logger.error("Failed to load intents from YAML: %s", e)
            return self._get_defaults()

    def sync_to_db(self, intents: list[IntentModel]):
        """Sync intent definitions to the database."""
        try:
            from harness.db.engine import get_session
            from harness.db.models import IntentDefinition

            with get_session() as session:
                for intent in intents:
                    existing = session.query(IntentDefinition).filter_by(
                        name=intent.name
                    ).first()
                    if existing:
                        existing.display_name = intent.display_name
                        existing.description = intent.description
                        existing.keywords = intent.keywords
                        existing.negative_keywords = intent.negative_keywords
                        existing.skill_name = intent.skill_name
                        existing.priority = intent.priority
                        existing.enabled = intent.enabled
                        existing.examples = intent.examples
                    else:
                        db_intent = IntentDefinition(
                            name=intent.name,
                            display_name=intent.display_name,
                            description=intent.description,
                            keywords=intent.keywords,
                            negative_keywords=intent.negative_keywords,
                            skill_name=intent.skill_name,
                            priority=intent.priority,
                            enabled=intent.enabled,
                            examples=intent.examples,
                        )
                        session.add(db_intent)
                session.commit()
            logger.info("Synced %d intents to database", len(intents))
        except Exception as e:
            logger.warning("Failed to sync intents to DB: %s", e)

    def load_from_db(self) -> list[IntentModel]:
        """Load intent definitions from the database."""
        try:
            from harness.db.engine import get_session
            from harness.db.models import IntentDefinition

            with get_session() as session:
                rows = session.query(IntentDefinition).all()
                intents = []
                for row in rows:
                    model = IntentModel(
                        name=row.name,
                        display_name=row.display_name,
                        description=row.description or "",
                        keywords=row.keywords or [],
                        negative_keywords=row.negative_keywords or [],
                        skill_name=row.skill_name or "",
                        priority=row.priority,
                        enabled=row.enabled,
                        examples=row.examples or [],
                        hit_count=row.hit_count,
                    )
                    intents.append(model)

            logger.info("Loaded %d intents from database", len(intents))
            return intents

        except Exception as e:
            logger.warning("Failed to load intents from DB: %s", e)
            return self.load_from_yaml()

    # ── Export ───────────────────────────────────────────

    def export_to_yaml(self, intents: list[IntentModel]) -> str:
        """Export intent definitions to a YAML string.

        Args:
            intents: List of intent models to export.

        Returns:
            YAML string representation.
        """
        data = {
            "intents": [
                {
                    "name": i.name,
                    "display_name": i.display_name,
                    "description": i.description,
                    "keywords": i.keywords,
                    "negative_keywords": i.negative_keywords,
                    "skill_name": i.skill_name,
                    "priority": i.priority,
                    "enabled": i.enabled,
                    "examples": i.examples,
                }
                for i in intents
            ]
        }
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def save_to_yaml(self, intents: list[IntentModel]):
        """Save intent definitions to the YAML file."""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.export_to_yaml(intents)
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Saved %d intents to %s", len(intents), self._yaml_path)

    # ── Defaults ─────────────────────────────────────────

    @staticmethod
    def _get_defaults() -> list[IntentModel]:
        """Get hardcoded default intents (fallback)."""
        return [
            IntentModel(
                name="parse_report",
                display_name="解析基金诊断报告",
                description="智能解析基金诊断报告，提取结构化数据",
                keywords=["解析", "报告", "基金", "诊断", "分析这份", "PDF", "文档", "提取"],
                negative_keywords=["总结"],
                skill_name="report_parser",
                priority=10,
                examples=["帮我解析这份基金诊断报告", "分析这个PDF文档"],
            ),
            IntentModel(
                name="generate_summary",
                display_name="生成客户总结",
                description="基于客户账户分析和私募持仓报告生成综合总结",
                keywords=["总结", "汇总", "账户", "持仓", "私募", "客户", "概况", "一键生成"],
                negative_keywords=["解析", "报告"],
                skill_name="summary_generator",
                priority=10,
                examples=["帮我生成王总的账户总结", "客户账户分析总结"],
            ),
            IntentModel(
                name="query_status",
                display_name="查询系统状态",
                description="查询 Agent 和 Skill 运行状态",
                keywords=["状态", "运行", "统计", "报表", "成功率", "调用量", "Skill", "Agent"],
                skill_name="status_query",
                priority=5,
                examples=["今天Agent运行情况怎么样", "查看系统报表"],
            ),
            IntentModel(
                name="manage_skill",
                display_name="管理 Skill",
                description="Skill 导入导出和管理操作",
                keywords=["导入", "导出", "安装", "卸载", "启用", "禁用"],
                skill_name="skill_manager",
                priority=5,
                examples=["导入一个新的Skill", "导出报告解析Skill"],
            ),
        ]
