import re
import uuid

from memory.graph_store import GraphStore

_FACT_VALUE = r"(.+?)(?=(?:,\s*(?:and\s+)?my\s+)|\s+and\s+my\s+|\.|$)"


class MemoryAgent:
    """Reads and writes episodic, semantic, and procedural memory in FalkorDB."""

    name = "memory_agent"
    role = "Memory Agent"

    def __init__(self, store):
        self.store = store

    def retrieve(self, tenant_id, user_id, text, exclude_contents=None):
        return self.store.retrieve_relevant_memory(tenant_id, user_id, text, exclude_contents=exclude_contents)

    def propose(self, tenant_id, user_id, text):
        return {"memory_ids": [item["memory_id"] for item in self.retrieve(tenant_id, user_id, text)]}

    @staticmethod
    def classify(text: str) -> list[tuple[str, str, str]]:
        memories = []
        name = re.search(rf"my\s+name\s+is\s+{_FACT_VALUE}", text, re.I)
        if name:
            memories.append(("semantic", "name", f"My name is {name.group(1).strip()}."))
        match = re.search(rf"my\s+preferred\s+([a-z ]+?)\s+is\s+{_FACT_VALUE}", text, re.I)
        if match:
            key = f"preferred_{re.sub(r'[^a-z0-9]+', '_', match.group(1).strip().lower()).strip('_')}"
            memories.append(("semantic", key, f"My preferred {match.group(1).strip()} is {match.group(2).strip()}."))
        for generic in re.finditer(r"my\s+([a-z][a-z ]{1,30})\s+is\s+" + _FACT_VALUE, text, re.I):
            subject_raw = generic.group(1).strip().lower()
            if subject_raw == "name" or subject_raw.startswith("preferred"):
                continue
            subject = re.sub(r"[^a-z0-9]+", "_", subject_raw).strip("_")
            memories.append(("semantic", f"personal_{subject}", f"My {generic.group(1).strip()} is {generic.group(2).strip()}."))
        process = re.search(r"(?:our\s+)?release\s+process\s+(?:requires|is|includes)\s+(.+?)(?:\.|$)", text, re.I)
        if process:
            memories.append(("procedural", "release_process", f"Our release process requires {process.group(1).strip()}."))
        return memories

    def persist(self, tenant_id, user_id, text, scope="personal", confidence=0.9):
        extracted = self.classify(text)
        saved = []
        superseded = None
        for memory_type, fact_key, content in extracted:
            old = self.store.find_active_memory(tenant_id, user_id, fact_key)
            memory_id = f"memory_{uuid.uuid4().hex[:12]}"
            if old and old[0]["content"] != content:
                superseded = old[0]["memory_id"]
                saved.extend(self.store.supersede_memory(
                    tenant_id, superseded, memory_id, user_id, scope, memory_type, content, confidence, fact_key
                ))
            elif not old:
                saved.extend(self.store.create_memory(
                    tenant_id, memory_id, user_id, scope, memory_type, content, confidence, fact_key
                ))
        if not extracted and not self.store.is_question(text):
            saved.extend(self.store.create_memory(
                tenant_id,
                f"memory_{uuid.uuid4().hex[:12]}",
                user_id,
                scope,
                "episodic",
                text.strip(),
                confidence,
                f"episode_{uuid.uuid4().hex[:12]}",
            ))
        return saved, superseded

    @staticmethod
    def format_recall(request: str, memories: list[dict]) -> str:
        """Answer with the requested fact only, without memory ids or extra details."""
        subjects = GraphStore.asked_subjects(request)
        lines = []
        seen = set()
        for item in memories:
            for clause in GraphStore.matching_clauses(item.get("content") or "", subjects):
                key = clause.strip().lower()
                if key not in seen:
                    seen.add(key)
                    lines.append(clause)
        if lines:
            return "\n".join(lines)
        return "I don't have that saved yet."

    def execute(self, tenant_id, task_id, handoff_id, request, user_id=None):
        """Complete a recall handoff using memories already linked to the task."""
        self.store.update_handoff(tenant_id, handoff_id, "in_progress")
        memories = [item for item in self.store.get_task_memories(tenant_id, task_id) if item.get("memory_id")]
        result = self.format_recall(request, memories) if memories else "I don't have that saved yet."
        if user_id:
            self.store.upsert_shared_state(tenant_id, user_id, "last_agent_result", result, self.name, task_id)
        self.store.update_handoff(tenant_id, handoff_id, "completed", result=result)
        self.store.set_task_result(tenant_id, task_id, "completed", result=result)
        return result
