"""Harness Framework — Intent Data Models.

Pydantic models for intent definitions, used for validation
and serialization between YAML, DB, and in-memory representations.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class IntentModel(BaseModel):
    """Pydantic model for an intent definition."""

    name: str = Field(..., description="Unique intent identifier")
    display_name: str = Field(default="", description="Human-readable name")
    description: str = Field(default="", description="Intent description")
    keywords: list[str] = Field(default_factory=list, description="Trigger keywords")
    negative_keywords: list[str] = Field(default_factory=list, description="Exclusion keywords")
    skill_name: str = Field(default="", description="Bound skill name")
    priority: int = Field(default=0, description="Priority (higher = more important)")
    enabled: bool = Field(default=True, description="Whether this intent is active")
    examples: list[str] = Field(default_factory=list, description="Example queries")
    hit_count: int = Field(default=0, description="Number of times matched")

    def to_router_rule(self):
        """Convert this model to an IntentRule for the router."""
        from harness.intent.router import IntentRule

        return IntentRule(
            name=self.name,
            description=self.description,
            keywords=self.keywords,
            negative_keywords=self.negative_keywords,
            bound_skill=self.skill_name,
            priority=self.priority,
            examples=self.examples,
            is_active=self.enabled,
            hit_count=self.hit_count,
        )
