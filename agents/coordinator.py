import uuid

from .memory_agent import MemoryAgent
from .routing import choose_agent
from .specialist_agent import SpecialistAgent


class CoordinatorAgent:
    name = "coordinator"
    role = "Coordinator Agent"

    def __init__(self, store):
        self.store = store
        self.memory_agent = MemoryAgent(store)
        self.specialist = SpecialistAgent(store)

    def run(self, tenant_id, user_id, request, session_id=None):
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        handoff_id = f"handoff_{uuid.uuid4().hex[:12]}"
        timeline = []
        try:
            memories = [item for item in self.memory_agent.retrieve(tenant_id, user_id, request) if item.get("source") != "turn"]
            agent_id, agent_name, route_reason = choose_agent(request, memories)
            timeline.append({"stage": "memory_retrieved", "memory_ids": [item["memory_id"] for item in memories], "route": agent_id})
            self.store.create_task(tenant_id, task_id, request, "pending", user_id=user_id)
            self.store.record_coordination_event(tenant_id, task_id, "task_created", "pending", request)
            self.store.update_task(tenant_id, task_id, "in_progress")
            self.store.record_coordination_event(tenant_id, task_id, "routed", "in_progress", route_reason)
            timeline.append({"stage": "task_created", "task_id": task_id, "status": "in_progress", "route": agent_id})
            memory_ids = [item["memory_id"] for item in memories]
            summary = " | ".join(f"{item['memory_type']}:{item['content']}" for item in memories[:5]) or "none"
            payload = f"{route_reason}\nTask: {request}\nShared memory: {summary}"
            self.store.upsert_shared_state(tenant_id, user_id, "working_context", payload, self.name, task_id)
            self.store.create_handoff(tenant_id, handoff_id, task_id, self.name, agent_id, payload, memory_ids)
            destination = self.memory_agent if agent_id == self.memory_agent.name else self.specialist
            self.store.assign_task(tenant_id, task_id, agent_id, agent_name, destination.role)
            for memory_id in memory_ids:
                self.store.attach_memory_to_task(tenant_id, task_id, memory_id)
            self.store.record_coordination_event(tenant_id, task_id, "handoff_assigned", "pending", payload)
            timeline.append({"stage": "handoff_assigned", "handoff_id": handoff_id, "agent": agent_name, "memory_ids": memory_ids})
            result = destination.execute(tenant_id, task_id, handoff_id, request, user_id)
            self.store.record_coordination_event(tenant_id, task_id, "specialist_completed", "completed", result, result)
            timeline.append({"stage": "specialist_completed", "status": "completed", "result": result, "agent": agent_id})
            return {
                "task_id": task_id,
                "handoff_id": handoff_id,
                "result": result,
                "memories": memories,
                "timeline": timeline,
                "routed_to": agent_id,
                "route_reason": route_reason,
            }
        except Exception as exc:
            error = str(exc)
            try:
                self.store.set_task_result(tenant_id, task_id, "failed", error=error)
                self.store.update_handoff(tenant_id, handoff_id, "failed", error=error)
                self.store.record_coordination_event(tenant_id, task_id, "failed", "failed", error, error)
            except Exception:
                pass
            timeline.append({"stage": "failed", "status": "failed", "error": error})
            return {"task_id": task_id, "handoff_id": handoff_id, "result": "The coordination task failed.", "memories": [], "timeline": timeline, "error": error}
