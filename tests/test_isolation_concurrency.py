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


def test_tenant_and_personal_memory_isolation(store):
    tenant_a = f"acme_{uuid.uuid4().hex[:10]}"
    tenant_b = f"beta_{uuid.uuid4().hex[:10]}"
    store.create_memory(tenant_a, "maya_private", "maya", "personal", "semantic", "Acme private architecture")
    store.create_memory(tenant_a, "acme_shared", "maya", "shared", "semantic", "Acme shared policy")
    assert store.retrieve_relevant_memory(tenant_a, "maya", "architecture")
    assert store.retrieve_relevant_memory(tenant_a, "leo", "architecture") == []
    assert store.retrieve_relevant_memory(tenant_a, "leo", "policy")
    assert store.retrieve_relevant_memory(tenant_b, "maya", "architecture") == []
    assert store.list_sessions(tenant_b, "maya") == []


def test_shared_state_is_isolated_by_user_and_tenant(store):
    tenant_a = f"state_{uuid.uuid4().hex[:10]}"
    tenant_b = f"state_{uuid.uuid4().hex[:10]}"
    store.upsert_shared_state(tenant_a, "maya", "working_context", "maya context", "coordinator")
    assert store.get_shared_state(tenant_a, "maya")
    assert store.get_shared_state(tenant_a, "leo") == []
    assert store.get_shared_state(tenant_b, "maya") == []


def test_concurrent_writes_and_reads_are_verified(store):
    tenant = f"concurrent_{uuid.uuid4().hex[:10]}"
    result = store.run_concurrent_memory_test(tenant, "maya", count=20, workers=5)
    assert result["attempted_writes"] == 20
    assert result["successful_writes"] == 20
    assert result["attempted_reads"] == 20
    assert result["successful_reads"] == 20
    assert result["verification_passed"] is True
    assert result["failed_operations"] == []
