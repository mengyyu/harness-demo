"""Harness Framework — Database Engine & Session Management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_db(database_url: str | None = None) -> tuple[Engine, sessionmaker]:
    """Initialize database engine and session factory.

    Args:
        database_url: Override the default DATABASE_URL from settings.

    Returns:
        (engine, SessionLocal) tuple.
    """
    global _engine, _SessionLocal

    url = database_url or settings.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        url,
        echo=settings.DATABASE_ECHO,
        connect_args=connect_args,
    )
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    return _engine, _SessionLocal


def get_engine() -> Engine:
    """Get the database engine, initializing if needed."""
    global _engine
    if _engine is None:
        init_db()
    return _engine


def get_session_factory() -> sessionmaker:
    """Get the session factory, initializing if needed."""
    global _SessionLocal
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session as a context manager.

    Usage:
        with get_session() as session:
            session.query(AgentRun).all()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Backward-compatible alias
SessionLocal = get_session_factory
