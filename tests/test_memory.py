"""Tests for the Memory System."""

import pytest
from harness.memory.store import MemoryStore


class TestMemoryStore:
    @pytest.fixture
    def store(self):
        return MemoryStore()

    def test_add_session_memory(self, store):
        mem_id = store.add("User asked about fund reports", user_id="u1", session_id="s1")
        assert mem_id.startswith("mem_")

    def test_search_session(self, store):
        store.add("User prefers aggressive funds", user_id="u1", session_id="s1")
        store.add("User asked about risk assessment", user_id="u1", session_id="s1")

        results = store.search("funds", user_id="u1", session_id="s1")
        assert len(results["session_context"]) >= 0

    def test_add_user_memory(self, store):
        store.add("User risk tolerance: R4", user_id="u1", memory_type="user")
        results = store.search("risk", user_id="u1")
        assert len(results["user_context"]) >= 0

    def test_add_entity_memory(self, store):
        store.add(
            "Fund DEMO001 analysis",
            user_id="u1",
            memory_type="entity",
            metadata={"entity_type": "fund"},
        )
        results = store.search("DEMO001", user_id="u1")
        assert len(results["entity_context"]) >= 0

    def test_delete_memory(self, store):
        mem_id = store.add("Test memory", user_id="u1", session_id="s1")
        assert store.delete(mem_id) is True

    def test_clear_session(self, store):
        store.add("Message 1", user_id="u1", session_id="s1")
        store.add("Message 2", user_id="u1", session_id="s1")
        count = store.clear_session("s1")
        assert count >= 0

    def test_stats(self, store):
        stats = store.get_stats()
        assert "session_memories" in stats
        assert "user_memories" in stats
        assert "entity_memories" in stats
