import uuid

from agents.chat_agent import DeterministicChatAgent
from memory.graph_store import GraphStore


def test_final_demo_sequence_uses_two_memory_types_and_session_links():
    store = GraphStore()
    ok, message = store.connection_test()
    assert ok, message
    tenant = f"demo_{uuid.uuid4().hex[:10]}"
    agent = DeterministicChatAgent(store)
    first_session = f"session_{uuid.uuid4().hex[:10]}"
    first = agent.handle(tenant, "maya", first_session, "Remember that my preferred stack is Python, FastAPI and FalkorDB. Our release process requires tests, QA approval and health verification.")
    assert {item["memory_type"] for item in first.saved_memory} == {"semantic", "procedural"}
    second_session = f"session_{uuid.uuid4().hex[:10]}"
    recalled = agent.handle(tenant, "maya", second_session, "What is my preferred stack, and which checks are required before release?")
    assert {"semantic", "procedural"} <= {item["memory_type"] for item in recalled.retrieved_memories}
    linked = store.query(tenant, "MATCH (s:Session {session_id:$session_id})-[:HAS_MEMORY]->(m:Memory) RETURN count(m) AS count", {"session_id": second_session})
    assert linked.result_set == [[2]]
    coordinated = agent.handle(tenant, "maya", second_session, "Prepare a release checklist using our saved procedure.")
    task_id = coordinated.coordination["task_id"]
    task_links = store.query(tenant, "MATCH (t:Task {task_id:$task_id})-[:USES_MEMORY]->(m:Memory) RETURN count(m) AS count", {"task_id": task_id})
    assert task_links.result_set[0][0] >= 1
