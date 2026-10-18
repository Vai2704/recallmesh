import uuid

import pytest

from agents.chat_agent import DeterministicChatAgent
from memory.graph_store import GraphStore


@pytest.fixture(scope="module")
def store():
    repository = GraphStore()
    ok, message = repository.connection_test()
    if not ok:
        pytest.skip(f"real FalkorDB required: {message}")
    return repository


def test_chat_persists_across_sessions_and_uses_graph_memory(store):
    tenant = f"chat_{uuid.uuid4().hex[:10]}"
    user = "alice"
    first_session = f"session_{uuid.uuid4().hex[:10]}"
    second_session = f"session_{uuid.uuid4().hex[:10]}"
    agent = DeterministicChatAgent(store)

    saved = agent.handle(tenant, user, first_session, "My preferred stack is Python, FastAPI and FalkorDB.")
    assert saved.saved_memory[0]["memory_type"] == "semantic"

    asked = agent.handle(tenant, user, second_session, "What is my preferred stack?")
    assert asked.retrieved_memories
    assert "Python, FastAPI and FalkorDB" in asked.response
    assert store.get_turns(tenant, second_session)
    assert store.get_recent_turns(tenant, user)
    restarted_store = GraphStore()
    assert restarted_store.retrieve_relevant_memory(tenant, user, "preferred stack")


def test_procedural_memory_is_retrieved(store):
    tenant = f"proc_{uuid.uuid4().hex[:10]}"
    agent = DeterministicChatAgent(store)
    agent.handle(tenant, "alice", f"session_{uuid.uuid4().hex[:10]}", "Our release process is to run tests, build the image, obtain QA approval, deploy and verify health.")
    result = agent.handle(tenant, "alice", f"session_{uuid.uuid4().hex[:10]}", "What is our release process?")
    assert any(item["memory_type"] == "procedural" for item in result.retrieved_memories)


def test_prior_session_turns_are_recalled_without_memory_nodes(store):
    tenant = f"turns_{uuid.uuid4().hex[:10]}"
    user = "alice"
    store.create_session(tenant, "old", user)
    store.save_turn(tenant, "old", "t1", "user", "Hi my name is vaibhav. How are you", "user")
    hits = store.retrieve_relevant_memory(tenant, user, "what is my name")
    assert hits
    assert "vaibhav" in hits[0]["content"].lower()


def test_latest_name_is_preferred_over_older_turns(store):
    tenant = f"latest_{uuid.uuid4().hex[:10]}"
    user = "alice"
    agent = DeterministicChatAgent(store)
    agent.handle(tenant, user, f"session_{uuid.uuid4().hex[:10]}", "Hi my name is vaibhav. How are you")
    agent.handle(tenant, user, f"session_{uuid.uuid4().hex[:10]}", "Hi my name is Sania gupta")
    asked = agent.handle(tenant, user, f"session_{uuid.uuid4().hex[:10]}", "what is my name")
    assert len(asked.retrieved_memories) == 1
    assert "sania" in asked.retrieved_memories[0]["content"].lower()
    assert "vaibhav" not in asked.retrieved_memories[0]["content"].lower()


def test_name_is_recalled_from_older_session_turns(store):
    tenant = f"name_{uuid.uuid4().hex[:10]}"
    user = "alice"
    agent = DeterministicChatAgent(store)
    first = agent.handle(tenant, user, f"session_{uuid.uuid4().hex[:10]}", "Hi my name is vaibhav. How are you")
    assert first.saved_memory
    asked = agent.handle(tenant, user, f"session_{uuid.uuid4().hex[:10]}", "what is my name")
    assert asked.retrieved_memories
    assert "vaibhav" in asked.response.lower()


def test_explain_memory_includes_supersedes_path(store):
    tenant = f"path_{uuid.uuid4().hex[:10]}"
    store.create_memory(tenant, "old_name", "alice", "personal", "semantic", "My name is vaibhav.", 1.0, "name")
    store.supersede_memory(tenant, "old_name", "new_name", "alice", "personal", "semantic", "My name is Sania gupta.", 1.0, "name")
    store.create_session(tenant, "sess_path", "alice")
    store.attach_memory_to_session(tenant, "sess_path", "new_name")
    path = store.explain_memory(tenant, "new_name")
    hops = " ".join(path["hops"])
    assert "SUPERSEDES" in hops
    assert "old_name" in hops
    assert "HAS_MEMORY" in hops


def test_chat_fact_change_supersedes_old_memory(store):
    tenant = f"change_{uuid.uuid4().hex[:10]}"
    agent = DeterministicChatAgent(store)
    agent.handle(tenant, "alice", f"session_{uuid.uuid4().hex[:10]}", "My preferred stack is Python and FastAPI.")
    result = agent.handle(tenant, "alice", f"session_{uuid.uuid4().hex[:10]}", "My preferred stack is Python, FastAPI and FalkorDB.")
    assert result.superseded_memory_id
    old = store.query(tenant, "MATCH (m:Memory {memory_id:$id}) RETURN m.active AS active", {"id": result.superseded_memory_id})
    assert old.result_set == [[False]]
