import uuid

import pytest

from agents.coordinator import CoordinatorAgent
from agents.routing import choose_agent, should_coordinate
from memory.graph_store import GraphStore


def test_statements_are_not_coordinated():
    assert should_coordinate("Hi my name is maya.") is False
    assert should_coordinate("What is my name?") is True
    assert should_coordinate("Prepare a release checklist") is True


def test_graph_memory_types_choose_destination_agent():
    recall_id, recall_name, _ = choose_agent("What is my name?", [{"memory_type": "semantic"}])
    assert recall_id == "memory_agent"
    assert "Memory" in recall_name
    workflow_id, workflow_name, _ = choose_agent(
        "What is our release process?", [{"memory_type": "procedural"}]
    )
    assert workflow_id == "workflow_specialist"
    assert "Specialist" in workflow_name


@pytest.fixture(scope="module")
def store():
    repository = GraphStore()
    ok, message = repository.connection_test()
    if not ok:
        pytest.skip(f"real FalkorDB required: {message}")
    return repository


def test_coordinator_hands_recall_to_memory_agent(store):
    tenant = f"route_{uuid.uuid4().hex[:10]}"
    store.create_memory(tenant, "m_name", "alice", "personal", "semantic", "My name is alice.", fact_key="name")
    result = CoordinatorAgent(store).run(tenant, "alice", "What is my name?")
    assert result["routed_to"] == "memory_agent"
    assert "alice" in result["result"].lower()
    assignment = store.query(
        tenant,
        "MATCH (t:Task {task_id:$task_id})-[:ASSIGNED_TO]->(a:Agent) RETURN a.agent_id AS agent_id",
        {"task_id": result["task_id"]},
    )
    assert assignment.result_set == [["memory_agent"]]
