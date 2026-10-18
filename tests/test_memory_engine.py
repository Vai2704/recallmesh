import os
import uuid

import pytest

from memory.graph_store import GraphStore


@pytest.fixture(scope="module")
def store():
    repository = GraphStore()
    ok, message = repository.connection_test()
    if not ok:
        pytest.skip(f"real FalkorDB required: {message}")
    return repository


def test_create_retrieve_update_and_user_isolation(store):
    tenant = f"test_{uuid.uuid4().hex[:10]}"
    first = store.create_memory(tenant, "m1", "alice", "personal", "semantic", "Alice prefers tea")
    assert first
    assert len(store.retrieve_relevant_memory(tenant, "alice", "tea")) == 1
    assert store.retrieve_relevant_memory(tenant, "bob", "tea") == []

    store.supersede_memory(tenant, "m1", "m2", "alice", "personal", "semantic", "Alice prefers coffee")
    assert store.retrieve_relevant_memory(tenant, "alice", "tea") == []
    assert len(store.retrieve_relevant_memory(tenant, "alice", "coffee")) == 1


def test_three_memory_types_persist_and_update(store):
    tenant = f"types_{uuid.uuid4().hex[:10]}"
    from agents.memory_agent import MemoryAgent
    agent = MemoryAgent(store)
    saved, _ = agent.persist(tenant, "maya", "Hi my name is maya. My preferred stack is Python. Our release process is tests then deploy.")
    kinds = {item["memory_type"] for item in saved}
    assert kinds == {"semantic", "procedural"}
    episodic, _ = agent.persist(tenant, "maya", "I finished the demo setup today")
    assert episodic[0]["memory_type"] == "episodic"
    _, superseded = agent.persist(tenant, "maya", "My preferred stack is Python and FalkorDB.")
    assert superseded
    current = store.retrieve_relevant_memory(tenant, "maya", "preferred stack")
    assert any("FalkorDB" in item["content"] for item in current)


def test_shared_memory_is_available_within_tenant(store):
    tenant = f"shared_{uuid.uuid4().hex[:10]}"
    store.create_memory(tenant, "shared1", "alice", "shared", "procedural", "Deploy with docker compose")
    assert len(store.retrieve_relevant_memory(tenant, "bob", "docker")) == 1

