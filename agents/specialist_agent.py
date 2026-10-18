import re


class SpecialistAgent:
    name = "workflow_specialist"
    role = "Workflow Specialist"

    def __init__(self, store):
        self.store = store

    @staticmethod
    def procedure_steps(content: str) -> list[str]:
        body = str(content or "").strip().rstrip(".")
        for prefix in (
            "Our release process requires ",
            "Our release process is to ",
            "Our release process is ",
            "Release means ",
        ):
            if body.lower().startswith(prefix.lower()):
                body = body[len(prefix):]
                break
        parts = [part.strip() for part in re.split(r"\s*,\s*|\s+then\s+", body, flags=re.I) if part.strip()]
        cleaned = []
        for part in parts:
            part = re.sub(r"^(and|to)\s+", "", part, flags=re.I).strip()
            if part:
                cleaned.append(part)
        return cleaned or [body]

    def execute(self, tenant_id, task_id, handoff_id, request, user_id=None):
        self.store.update_handoff(tenant_id, handoff_id, "in_progress")
        memories = [item for item in self.store.get_task_memories(tenant_id, task_id) if item.get("memory_id")]
        procedural = [item for item in memories if item.get("memory_type") == "procedural"]
        other = [item for item in memories if item.get("memory_type") != "procedural"]
        if procedural:
            source = procedural[0]
            steps = self.procedure_steps(source["content"])
            lines = [
                "Workflow Specialist executed a procedure stored in FalkorDB.",
                f"Source: `{source['memory_id']}` ({source.get('scope')} procedural) — {source['content']}",
                "Checklist:",
            ]
            lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
            if other:
                lines.append("Related graph memory: " + "; ".join(item["content"] for item in other[:2]))
            result = "\n".join(lines)
        elif memories:
            result = "Workflow Specialist received graph memory but no procedural node. Facts: " + "; ".join(
                item["content"] for item in memories[:3]
            )
        else:
            result = f"Workflow Specialist found no procedural memory in the graph for: {request}"
        if user_id:
            self.store.upsert_shared_state(
                tenant_id, user_id, "last_specialist_result", result, self.name, task_id
            )
        self.store.update_handoff(tenant_id, handoff_id, "completed", result=result)
        self.store.set_task_result(tenant_id, task_id, "completed", result=result)
        return result
