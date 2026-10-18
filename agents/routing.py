"""Decide whether to coordinate and which agent should receive the handoff.

The graph's memory types drive this choice: workflow terms or procedural
nodes go to the specialist; recall questions go to the memory agent.
"""

from memory.graph_store import GraphStore

WORKFLOW_TERMS = (
    "deploy", "release", "workflow", "process", "project", "pipeline",
    "qa", "checklist", "prepare", "procedure",
)


def is_workflow_request(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in WORKFLOW_TERMS)


def should_coordinate(text: str) -> bool:
    """Statements are stored without a handoff; questions and workflows are routed."""
    return GraphStore.is_question(text) or is_workflow_request(text)


def choose_agent(text: str, memories: list[dict]) -> tuple[str, str, str]:
    types = {item.get("memory_type") for item in memories or []}
    if is_workflow_request(text) or "procedural" in types:
        return (
            "workflow_specialist",
            "Workflow Specialist",
            "Graph routing: workflow terms and/or procedural memory → specialist executes the stored procedure.",
        )
    return (
        "memory_agent",
        "Memory Agent",
        "Graph routing: recall question → memory agent answers from active semantic/episodic facts.",
    )
