import uuid
from dataclasses import dataclass, field

from memory.graph_store import GraphStore

from .coordinator import CoordinatorAgent
from .memory_agent import MemoryAgent
from .routing import should_coordinate


@dataclass
class ChatResult:
    response: str
    retrieved_memories: list[dict]
    history: list[dict]
    saved_memory: dict | None
    superseded_memory_id: str | None = None
    coordination: dict | None = None
    provenance: list[dict] = field(default_factory=list)


class DeterministicChatAgent:
    """Deterministic agent loop: persist → retrieve → route → explain from the graph."""

    def __init__(self, store):
        self.store = store
        self.memory_agent = MemoryAgent(store)

    @staticmethod
    def classify(text: str) -> list[tuple[str, str, str]]:
        return MemoryAgent.classify(text)

    def _graph_memories(self, items: list[dict]) -> list[dict]:
        return [item for item in items if item.get("source") != "turn" and item.get("memory_id")]

    def handle(self, tenant_id, user_id, session_id, text, scope="personal", confidence=0.9) -> ChatResult:
        self.store.create_session(tenant_id, session_id, user_id)
        retrieved = self.memory_agent.retrieve(tenant_id, user_id, text, exclude_contents=[text])
        self.store.save_turn(tenant_id, session_id, f"turn_{uuid.uuid4().hex[:12]}", "user", text, "user")
        history = self.store.get_recent_turns(tenant_id, user_id)
        saved, superseded = self.memory_agent.persist(tenant_id, user_id, text, scope, confidence)
        for item in saved:
            self.store.attach_memory_to_session(tenant_id, session_id, item["memory_id"])
        coordination = None
        if should_coordinate(text):
            coordination = CoordinatorAgent(self.store).run(tenant_id, user_id, text, session_id)
        for item in self._graph_memories(retrieved):
            self.store.attach_memory_to_session(tenant_id, session_id, item["memory_id"])
        for item in self._graph_memories(coordination.get("memories", []) if coordination else []):
            self.store.attach_memory_to_session(tenant_id, session_id, item["memory_id"])
        provenance = [
            self.store.explain_memory(tenant_id, item["memory_id"])
            for item in self._graph_memories(retrieved)[:3]
        ]
        response = self._compose(text, retrieved, saved, coordination)
        self.store.save_turn(tenant_id, session_id, f"turn_{uuid.uuid4().hex[:12]}", "assistant", response, "coordinator")
        return ChatResult(response, retrieved, history, saved or None, superseded, coordination, provenance)

    @staticmethod
    def _compose(text, retrieved, saved, coordination) -> str:
        if coordination and coordination.get("result"):
            return coordination["result"]
        if not GraphStore.is_question(text):
            return "Saved."
        if retrieved:
            return MemoryAgent.format_recall(text, retrieved)
        if "preferred stack" in text.lower():
            return "I do not have a persisted preferred stack for you yet."
        if "release" in text.lower() or "process" in text.lower():
            return "I do not have a persisted release process for this tenant and user yet."
        return "Recorded. I will use persisted graph memory when it is relevant."
