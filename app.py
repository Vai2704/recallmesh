import html
import uuid

import streamlit as st

from agents.chat_agent import DeterministicChatAgent
from memory.graph_store import GraphStore, validate_tenant_id

st.set_page_config(
    page_title="RecallMesh",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
<style>
.block-container {max-width: 1120px; padding-top: 1.25rem; padding-bottom: 2rem;}
[data-testid="stMetricValue"] {font-size: 1.4rem;}
footer {visibility: hidden;}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stExpandSidebarButton"] {
  visibility: visible !important;
  display: flex !important;
  opacity: 1 !important;
}
.rm-top {display:flex; justify-content:space-between; align-items:flex-end; margin-bottom: 1.25rem; gap: 1rem;}
.rm-brand {font-size: 1.15rem; font-weight: 650; letter-spacing: -.02em;}
.rm-status {color: #7d8b96; font-size: .82rem;}
.rm-dot {color: #3ecf8e;}
</style>
""",
    unsafe_allow_html=True,
)

ORGANIZATIONS = {"Acme": "acme-demo", "Beta": "beta-demo"}
PEOPLE = {"Maya": "maya", "Leo": "leo"}
PAGES = ["Chat", "Memory", "Agents", "Graph", "Operations", "Status"]

with st.sidebar:
    st.markdown("**RecallMesh**")
    st.caption("Workspace")
    org_label = st.selectbox("Organization", list(ORGANIZATIONS), label_visibility="visible")
    user_label = st.selectbox("Signed in as", list(PEOPLE))
    st.divider()
    view = st.radio("Pages", PAGES, label_visibility="collapsed")

tenant = ORGANIZATIONS[org_label]
user = PEOPLE[user_label]

if st.session_state.get("active_tenant") != tenant or st.session_state.get("active_user") != user:
    st.session_state.active_tenant = tenant
    st.session_state.active_user = user
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:12]}"
    st.session_state.messages = []
    st.session_state.pop("last_task_id", None)
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:12]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    validate_tenant_id(tenant)
    store = GraphStore()
    connected, health_message = store.connection_test()
except Exception as exc:
    connected, health_message, store = False, f"Could not reach the database: {exc}", None

if not connected:
    st.error("RecallMesh can’t reach the database right now.")
    st.caption(health_message)
    st.code("docker start recallmesh-db", language="bash")
    st.stop()

store.initialize_schema(tenant)
store.create_session(tenant, st.session_state.session_id, user)

st.markdown(
    f'<div class="rm-top"><div class="rm-brand">RecallMesh</div>'
    f'<div class="rm-status"><span class="rm-dot">●</span> {org_label} · {user_label}</div></div>',
    unsafe_allow_html=True,
)


def session_messages(session_id):
    messages = []
    for item in store.get_turns(tenant, session_id):
        role = item.get("role") if item.get("role") in ("user", "assistant") else "assistant"
        messages.append({"role": role, "content": item.get("content") or ""})
    return messages


def render_chat():
    sessions = store.list_sessions(tenant, user)
    left, right = st.columns([3, 1])
    with left:
        st.subheader("Chat")
    with right:
        if st.button("New chat", use_container_width=True):
            st.session_state.session_id = f"session_{uuid.uuid4().hex[:12]}"
            st.session_state.messages = []
            st.session_state.session_select = st.session_state.session_id
            st.rerun()

    labels = [item["session_id"] for item in sessions]
    if st.session_state.session_id not in labels:
        labels = [st.session_state.session_id] + labels
    if labels:
        if st.session_state.get("session_select") not in labels:
            st.session_state.session_select = st.session_state.session_id
        selected = st.selectbox("Session", labels, key="session_select")
        if selected != st.session_state.session_id:
            st.session_state.session_id = selected
            st.session_state.messages = session_messages(selected)
            st.rerun()
    if not st.session_state.messages:
        st.session_state.messages = session_messages(st.session_state.session_id)

    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    prompt = st.chat_input("Message")
    if prompt:
        result = DeterministicChatAgent(store).handle(tenant, user, st.session_state.session_id, prompt)
        st.session_state.last_task_id = result.coordination["task_id"] if result.coordination else None
        st.session_state.messages.extend(
            [{"role": "user", "content": prompt}, {"role": "assistant", "content": result.response}]
        )
        st.rerun()

    with st.expander("Activity"):
        st.dataframe(store.get_recent_turns(tenant, user, 20), use_container_width=True, hide_index=True)
        if st.session_state.get("last_task_id"):
            st.dataframe(
                store.coordination_timeline(tenant, st.session_state.last_task_id),
                use_container_width=True,
                hide_index=True,
            )


def render_memory():
    st.subheader("Memory")
    c1, c2 = st.columns([3, 1])
    search = c1.text_input("Search", placeholder="Search stored facts")
    kind = c2.selectbox("Type", ["All", "episodic", "semantic", "procedural"])
    records = store.search_memories(tenant, user, search, None if kind == "All" else kind)
    if records:
        st.dataframe(records, use_container_width=True, hide_index=True)
    else:
        st.caption("Nothing stored for this person in this workspace yet.")
    with st.form("memory_form"):
        st.markdown("**Add memory**")
        cols = st.columns(2)
        memory_type = cols[0].selectbox("Type", ["episodic", "semantic", "procedural"])
        scope = cols[1].selectbox("Visibility", ["personal", "shared"])
        confidence = st.slider("Confidence", 0.0, 1.0, 0.9, 0.05)
        content = st.text_area("Content")
        if st.form_submit_button("Save") and content:
            store.create_memory(tenant, f"memory_{uuid.uuid4().hex[:12]}", user, scope, memory_type, content, confidence)
            st.success("Saved.")
            st.rerun()


def render_agents():
    st.subheader("Agents")
    shared = store.get_shared_state(tenant, user)
    if shared:
        st.markdown("**Shared state**")
        st.dataframe(shared, use_container_width=True, hide_index=True)
    records = store.coordination_records(tenant, user)
    if not records:
        st.caption("No handoffs yet. Ask a question in Chat.")
        return
    for record in records:
        title = record["description"] or record["task_id"]
        with st.expander(f"{record['status']} · {title}", expanded=False):
            st.write(f"{record['source_agent'] or '—'} → {record['destination_agent'] or '—'}")
            st.caption(f"{record['handoff_id'] or '—'} · {record['handoff_status'] or '—'}")
            if record["handoff_context"]:
                st.markdown("**Context**")
                st.write(record["handoff_context"])
            result = record["handoff_result"] or record["task_result"]
            if result:
                st.markdown("**Result**")
                st.write(result)
            paths = store.explain_task(tenant, record["task_id"])
            hops = [line for row in paths for line in (row.get("hops") or [])]
            if hops:
                with st.expander("Graph path"):
                    st.code("\n".join(hops), language="text")


def render_graph():
    st.subheader("Graph")
    records, relationships = store.list_graph_records(tenant), store.list_graph_relationships(tenant)
    if not records:
        st.caption("This workspace is empty.")
        return
    node_map = {}
    lines = ["digraph RecallMesh {", "rankdir=LR;", 'node [shape=box style=filled fillcolor="#f4f6f8" fontname=Helvetica fontsize=10];']

    def property_key(properties, index):
        for name in ("memory_id", "task_id", "handoff_id", "session_id", "agent_id", "turn_id", "event_id", "state_id"):
            value = properties.get(name) if properties else None
            if value is not None and str(value):
                return str(value)
        return f"node_{index}"

    for index, record in enumerate(records[:100]):
        props = record["properties"] or {}
        key = property_key(props, index)
        node_id = f"n{index}"
        node_map[key] = node_id
        label = f"{record['labels'][0]}\\n{str(key)[:28]}"
        lines.append(f'{node_id} [label="{html.escape(label).replace(chr(34), chr(92)+chr(34))}"];')
    seen_edges = set()
    for rel in relationships[:200]:
        source = property_key(rel["from_properties"], -1)
        target = property_key(rel["to_properties"], -1)
        edge = (source, target, rel["relationship"])
        if source in node_map and target in node_map and edge not in seen_edges:
            seen_edges.add(edge)
            lines.append(f'{node_map[source]} -> {node_map[target]} [label="{rel["relationship"]}"];')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), use_container_width=True)
    st.caption(f"{len(records)} nodes · {len(relationships)} relationships")


def render_operations():
    st.subheader("Operations")
    st.caption(f"Workspace {org_label} · {user_label}")
    if st.button("Run concurrency check"):
        with st.spinner("Writing and reading records…"):
            result = store.run_concurrent_memory_test(tenant, user, count=20, workers=5)
        cols = st.columns(4)
        cols[0].metric("Writes", f"{result['successful_writes']}/{result['attempted_writes']}")
        cols[1].metric("Reads", f"{result['successful_reads']}/{result['attempted_reads']}")
        cols[2].metric("Failed", len(result["failed_operations"]))
        cols[3].metric("Verified", "Yes" if result["verification_passed"] else "No")
        with st.expander("Raw result"):
            st.json(result)


def render_status():
    st.subheader("Status")
    ok, message = store.connection_test()
    st.success("Database connected") if ok else st.error(message)
    counts = store.record_counts(tenant)
    cols = st.columns(4)
    for index, (label, value) in enumerate(counts.items()):
        cols[index % 4].metric(label, value)


{
    "Chat": render_chat,
    "Memory": render_memory,
    "Agents": render_agents,
    "Graph": render_graph,
    "Operations": render_operations,
    "Status": render_status,
}[view]()
