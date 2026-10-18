from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    falkordb_host: str = os.getenv("FALKORDB_HOST", "localhost")
    falkordb_port: int = int(os.getenv("FALKORDB_PORT", "6379"))
    falkordb_password: str | None = os.getenv("FALKORDB_PASSWORD") or None
    falkordb_username: str | None = os.getenv("FALKORDB_USERNAME") or None
    graph_prefix: str = os.getenv("FALKORDB_GRAPH_PREFIX", "recallmesh")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None

def schema_queries() -> tuple[str, ...]:
    return tuple(f"CREATE INDEX FOR (n:{label}) ON (n.{property_name})" for label, property_name in (
        ("Session", "session_id"), ("Turn", "turn_id"), ("Memory", "memory_id"),
        ("Agent", "agent_id"), ("Task", "task_id"), ("Handoff", "handoff_id"),
        ("SharedState", "state_id"), ("SharedState", "user_id"),
    ))

MEMORY_TYPES = {"episodic", "semantic", "procedural"}
MEMORY_SCOPES = {"personal", "shared"}
