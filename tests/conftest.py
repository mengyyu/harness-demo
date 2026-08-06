"""Harness Framework — Test Configuration & Fixtures."""

import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import tempfile
import os


@pytest.fixture(scope="session")
def project_root():
    """Return the project root path."""
    return PROJECT_ROOT


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    yield db_url

    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def settings_override():
    """Override settings for testing."""
    from config.settings import Settings
    return Settings(
        DATABASE_URL="sqlite:///./data/test_harness.db",
        LANGFUSE_ENABLED=False,
        MEM0_ENABLED=False,
        LLM_PROVIDER="mock",
        DEBUG=True,
    )
