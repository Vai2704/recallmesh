// Representative parameterized Cypher used by memory/graph_store.py.

// Tenant graph is selected by the validated tenant ID before query execution.
MATCH (m:Memory) WHERE m.active=true AND (m.scope='shared' OR m.user_id=$user_id)
RETURN m.memory_id AS memory_id, m.memory_type AS memory_type, m.content AS content;

CREATE (m:Memory {memory_id:$memory_id, user_id:$user_id, scope:$scope,
  memory_type:$memory_type, content:$content, confidence:$confidence,
  active:true, version:1, fact_key:$fact_key, created_at:$now, updated_at:$now});

MATCH (old:Memory {memory_id:$old_id}), (new:Memory {memory_id:$new_id})
SET old.active=false, new.version=old.version+1
CREATE (new)-[:SUPERSEDES]->(old);

CREATE (s:Session {session_id:$session_id, user_id:$user_id, created_at:$now});
MATCH (s:Session {session_id:$session_id})
CREATE (t:Turn {turn_id:$turn_id, role:$role, content:$content, timestamp:$now})
CREATE (s)-[:HAS_TURN]->(t);

CREATE (t:Task {task_id:$task_id, description:$description, status:$status,
  user_id:$user_id, created_at:$now, updated_at:$now});
MATCH (t:Task {task_id:$task_id})
MERGE (a:Agent {agent_id:$agent_id})
CREATE (t)-[:ASSIGNED_TO]->(a);

MATCH (t:Task {task_id:$task_id})
CREATE (h:Handoff {handoff_id:$handoff_id, task_id:$task_id,
  source_agent_id:$source, destination_agent_id:$destination,
  memory_ids:$memory_ids, payload:$payload, status:$status,
  created_at:$now, status_updated_at:$now})
CREATE (t)-[:HAS_HANDOFF]->(h);

MATCH (t:Task {task_id:$task_id})
CREATE (e:CoordinationEvent {event_id:$event_id, stage:$stage,
  status:$status, detail:$detail, at:$now})
CREATE (t)-[:HAS_EVENT]->(e);

MERGE (s:SharedState {state_id:$state_id})
SET s.user_id=$user_id, s.key=$key, s.value=$value, s.updated_by=$agent_id;
MATCH (t:Task {task_id:$task_id})-[:USES_MEMORY]->(m:Memory)
WHERE m.active=true
RETURN m.memory_type AS memory_type, m.content AS content;

MATCH (m:Memory {memory_id:$memory_id})
OPTIONAL MATCH (m)-[:SUPERSEDES]->(old:Memory)
OPTIONAL MATCH (s:Session)-[:HAS_MEMORY]->(m)
OPTIONAL MATCH (t:Task)-[:USES_MEMORY]->(m)
RETURN m.memory_id AS memory_id, collect(DISTINCT old.memory_id) AS superseded_ids,
  collect(DISTINCT s.session_id) AS session_ids, collect(DISTINCT t.task_id) AS task_ids;

// Synthetic demo-only reset, never used for arbitrary tenant input.
MATCH (n) DETACH DELETE n;
