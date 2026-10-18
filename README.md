# RecallMesh

RecallMesh is a workspace for **agent memory**. People chat with it like a normal assistant, but what they say is stored in a **FalkorDB graph**, not in the browser window.

Close the chat, start a new session, or hand work to another agent — the facts are still there. Each organization gets its own graph. Each person has their own personal memory.

No API key is required. Answers are deterministic and grounded in graph records.

---

## The problem

Typical agents forget. Context lives in the current chat, in RAM, or inside one process.

That fails in three common ways:

1. **A new session starts empty**, even if the same person already shared facts.
2. **A second agent cannot see** what the first one learned.
3. **You cannot explain an answer** — there is no durable trail of which fact was used, or that an older fact was replaced.

---

## How RecallMesh solves it

Everything durable is a node or edge in FalkorDB.

| You do this | What happens |
|---|---|
| Tell it a fact (`My favorite food is Dosa.`) | A **Memory** node is written. The chat turn is linked to a **Session**. |
| Click **New chat** and ask the fact back | The Memory Agent **queries the graph**, not the old screen. Session 12’s messages are not copied into session 5. |
| Change the fact later | A new Memory is created. The old one stays, marked inactive, with a `SUPERSEDES` edge. Only the latest is used. |
| Ask about a process or checklist | The coordinator **routes from graph memory** to the Workflow Specialist. That agent reads the procedural node and returns steps. |
| Open **Sources** or **Agents** | You see which nodes and relationships produced the answer. |

Three kinds of memory:

- **Semantic** — durable facts (“my name is…”, “my preferred stack is…”).
- **Procedural** — how work is done (“our release process requires…”).
- **Episodic** — other statements kept as experience.

Personal memories match the signed-in user. Shared memories are visible to everyone in that organization. Acme and Beta are separate graphs (`recallmesh_acme-demo`, `recallmesh_beta-demo`).

---

## How the graph is used

```text
UI (Chat, Memory, Agents, Graph)
        │
        ▼
Coordinator
   ├── Memory Agent          (recall questions)
   └── Workflow Specialist   (procedures / checklists)
        │
        ▼
GraphStore  →  official FalkorDB client
        │
        ▼
One graph per organization
```

Relationships:

```text
(Session)-[:HAS_TURN]->(Turn)
(Session)-[:HAS_MEMORY]->(Memory)
(Memory)-[:SUPERSEDES]->(Memory)
(Task)-[:ASSIGNED_TO]->(Agent)
(Task)-[:HAS_HANDOFF]->(Handoff)
(Handoff)-[:FROM_AGENT]->(Agent)
(Handoff)-[:TO_AGENT]->(Agent)
(Task)-[:USES_MEMORY]->(Memory)
(Task)-[:USES_STATE]->(SharedState)
(Task)-[:HAS_EVENT]->(CoordinationEvent)
```

Queries live in `memory/graph_store.py`. Examples are in `queries.cypher`. Application state is not kept in SQLite, files, or Python dicts.

---

## What you need

- **Python 3.11+**
- **Docker** (for FalkorDB)
- Git, to clone the repo

---

## Run it locally

### 1. Clone and enter the project

```bash
git clone https://github.com/Vai2704/recallmesh.git
cd recallmesh
```

### 2. Create a virtual environment and install packages

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

### 3. Environment file

**macOS / Linux**

```bash
cp .env.example .env
```

**Windows**

```powershell
copy .env.example .env
```

Defaults talk to FalkorDB on `localhost:6379`. You do not need an LLM key.

### 4. Start FalkorDB

```bash
docker run -d --name recallmesh-db -p 6379:6379 falkordb/falkordb:latest
```

If that container already exists:

```bash
docker start recallmesh-db
```

Or with Compose (database only):

```bash
docker compose up -d falkordb
```

Check it is up:

```bash
docker ps
```

You should see `recallmesh-db` (or `falkordb`) listening on port **6379**.

### 5. Load sample data (optional but useful)

```bash
python scripts/seed_demo.py --reset
```

This only resets the **Acme** graph, then seeds a few demo memories. Run it again without `--reset` if you only want to refresh those fixed IDs. **Beta is not touched.**

### 6. Start the app

```bash
streamlit run app.py
```

Open the URL Streamlit prints, usually [http://localhost:8501](http://localhost:8501).

Leave this terminal running. Use another terminal (with the venv activated) for tests or seed commands.

---

## How to use

After `streamlit run app.py`, open [http://localhost:8501](http://localhost:8501).

**Sidebar**

- **Organization** — Acme or Beta (each is its own graph).
- **Signed in as** — Maya or Leo (personal memory is per person).
- **Pages** — Chat, Memory, Agents, Graph, Operations, Status.

Use **Acme** and **Maya** unless a step says otherwise.

### Pages

| Page | What it is for |
|---|---|
| **Chat** | Talk to the agents. New chat starts a new session; older sessions stay in the **Session** list. |
| **Memory** | Search stored facts, or add a memory by type (episodic / semantic / procedural) and visibility (personal / shared). |
| **Agents** | Tasks, handoffs, shared state, who answered, and the result. |
| **Graph** | Live picture of nodes and relationships. |
| **Operations** | Concurrent write/read check against the database. |
| **Status** | Connection check and record counts. |

Statements are stored. Questions are looked up in the graph and routed to an agent. After an answer, **Sources** shows the memory that was used; **How this was found** shows the graph path. **Activity** is recent turns (collapsed so Chat stays clean).

### Manual usage / test flow

Copy these into Chat. They are the main product checks.

**1. Remember across sessions**

1. Send: `My favorite food is Dosa.`
2. Click **New chat** (this is a new session, like “session 5” after “session 12”).
3. Ask: `What is my favorite food?`

Expected: Dosa appears under **Sources**. This session’s transcript is only the new question and answer — the previous chat is not copied in. Switch **Session** in the dropdown to open the older chat if you want to see it.

**2. Procedural memory**

1. Send: `Our release process requires tests, QA approval and health verification.`
2. **New chat**.
3. Ask: `Which checks are required before release?`

Expected: a procedural memory is used; the reply lists those checks.

**3. Agent handoff**

Ask: `Prepare a release checklist using our saved procedure.`

Then open **Agents**. Expected:

- Coordinator took the request
- Procedural memory was retrieved
- A task and a handoff exist
- Destination is `workflow_specialist`
- Status is completed and a result is stored

**4. Isolation**

Switch **Signed in as** to **Leo**, or **Organization** to **Beta**. Ask the food or stack question again.

Expected: Maya’s personal facts are not returned.

**5. Concurrency**

Open **Operations** → **Run concurrency check**.

Expected: 20 writes, 20 reads, 0 failures.

**6. Graph**

Open **Graph** after the steps above. You should see sessions, turns, memories, tasks, handoffs, and agents, all loaded from FalkorDB.

**7. Database down**

```bash
docker stop recallmesh-db
```

Refresh the app. Expected: an error, and no “saved successfully” message. Then:

```bash
docker start recallmesh-db
```

Refresh again; Chat should work.

### Automated tests

These hit the real database. Keep FalkorDB running and the venv activated.

**macOS / Linux**

```bash
source .venv/bin/activate
python -m pytest -q
```

**Windows**

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

All tests should pass (currently **22**). If the database is stopped, most tests fail on connection — that is expected.

Optional extra check:

```bash
python -m compileall -q app.py memory agents tests scripts
```

---

## Project layout

```text
app.py                 UI
agents/                Coordinator, Memory Agent, Workflow Specialist, routing
memory/graph_store.py  All FalkorDB reads and writes
scripts/seed_demo.py   Sample Acme data
tests/                 pytest (needs FalkorDB running)
queries.cypher         Example Cypher
.env.example           Database settings
```

---

## Troubleshooting

| Symptom | What to do |
|---|---|
| App says it cannot reach the database | `docker ps`. Start with `docker start recallmesh-db` or the `docker run` command above. Confirm port **6379**. |
| `docker run` says the name is taken | `docker start recallmesh-db` |
| Empty Acme workspace | `python scripts/seed_demo.py --reset` then refresh the browser |
| Another user cannot see a fact | Personal memory is per user. Use **shared** visibility for org-wide facts |
| Tests fail | Start FalkorDB, activate `.venv`, run `python -m pytest -q` again |
| `streamlit` not found | The venv is not active, or `pip install -r requirements.txt` was skipped |

To stop the database:

```bash
docker stop recallmesh-db
```

The app should show a connection error and must not claim it saved anything. Start it again with `docker start recallmesh-db`.

---

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `FALKORDB_HOST` | `localhost` | Database host |
| `FALKORDB_PORT` | `6379` | Database port |
| `FALKORDB_USERNAME` | empty | Optional |
| `FALKORDB_PASSWORD` | empty | Optional |
| `FALKORDB_GRAPH_PREFIX` | `recallmesh` | Graph names become `prefix_organization` |

---

## Limits

- The person picker is a demo switch, not real login.
- Extraction is pattern-based (for example `my … is …`, release process). Free-form chat still stores as episodic when it is a statement.
- Concurrency check is a correctness demo, not a load benchmark.
- Graph view caps how many nodes it draws; every item still comes from FalkorDB.

---

## License / origin

Built as an open project on FalkorDB. AI coding tools were used while writing and checking the code. Behavior described here matches the repository as it stands.
