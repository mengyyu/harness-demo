"""Harness Framework — SQLAlchemy Database Models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List as ListType

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Text,
    JSON,
    Integer,
    Float,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════
# Agent Run Records
# ══════════════════════════════════════════════════════════════

class AgentRun(Base):
    """Record of a single agent execution cycle."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    agent_name: Mapped[str] = mapped_column(String(128), default="harness")
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    skill_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    input_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running | success | failed | interrupted
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict]] = mapped_column("metadata", JSON, nullable=True)
    langfuse_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AgentStep(Base):
    """Individual step within an agent run (thought / action / observation)."""

    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(32))  # thought | action | observation | final
    step_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tool_input: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    tool_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ══════════════════════════════════════════════════════════════
# Skill Records
# ══════════════════════════════════════════════════════════════

class SkillRun(Base):
    """Record of a skill execution."""

    __tablename__ = "skill_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    skill_name: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running | success | failed
    input_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    langfuse_span_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SkillDefinition(Base):
    """Registered skill definitions."""

    __tablename__ = "skill_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    module_path: Mapped[str] = mapped_column(String(512))
    intents: Mapped[Optional[ListType]] = mapped_column(JSON, nullable=True)
    config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timeout: Mapped[int] = mapped_column(Integer, default=300)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ══════════════════════════════════════════════════════════════
# Intent Records
# ══════════════════════════════════════════════════════════════

class IntentDefinition(Base):
    """Intent library configuration."""

    __tablename__ = "intent_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    examples: Mapped[Optional[ListType]] = mapped_column(JSON, nullable=True)
    skill_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    keywords: Mapped[Optional[ListType]] = mapped_column(JSON, nullable=True)
    negative_keywords: Mapped[Optional[ListType]] = mapped_column(JSON, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
