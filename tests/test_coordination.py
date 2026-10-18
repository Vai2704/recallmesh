import uuid

import pytest

from agents.coordinator import CoordinatorAgent
from memory.graph_store import GraphStore


@pytest.fixture(scope="module")
def store():
    repository = GraphStore()
    ok, message = repository.connection_test()
    if not ok:
        pytest.skip(f"real FalkorDB required: {message}")
    return repository


def test_coordinator_persists_task_handoff_assignment_and_completion(store):
    tenant = f"coord_{uuid.uuid4().hex[:10]}"
    memory_id = f"memory_{uuid.uuid4().hex[:10]}"
    store.create_memory(tenant, memory_id, "alice", "personal", "procedural", "Release means test, build, QA, deploy and verify health.")

    result = CoordinatorAgent(store).run(tenant, "alice", "What is our release process?")
    assert result["task_id"] and result["handoff_id"]
    assert memory_id in result["timeline"][0]["memory_ids"]

    task = store.query(tenant, "MATCH (t:Task {task_id:$task_id}) RETURN t.status AS status, t.result AS result", {"task_id": result["task_id"]})
    handoff = store.query(tenant, "MATCH (h:Handoff {handoff_id:$handoff_id}) RETURN h.status AS status, h.memory_ids AS memory_ids, h.result AS result", {"handoff_id": result["handoff_id"]})
    assignment = store.query(tenant, "MATCH (t:Task {task_id:$task_id})-[:ASSIGNED_TO]->(a:Agent) RETURN a.agent_id AS agent_id", {"task_id": result["task_id"]})
    assert task.result_set == [["completed", result["result"]]]
    assert handoff.result_set[0][0] == "completed"
    assert memory_id in handoff.result_set[0][1]
    assert assignment.result_set == [["workflow_specialist"]]
    assert result["routed_to"] == "workflow_specialist"
    assert "Checklist" in result["result"]
    assert "Release means test, build, QA" in result["result"]
    shared = store.get_shared_state(tenant, "alice", "last_specialist_result")
    assert shared and "Checklist" in shared[0]["value"]
    assert store.get_shared_state(tenant, "bob") == []
    assert any(event["event_type"] == "handoff" for event in store.coordination_timeline(tenant, result["task_id"]))
