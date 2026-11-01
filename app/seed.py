import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from app.auth import hash_password, new_secret, hash_secret
from app.store import WorkflowStore

db_path = ".data/studio.sqlite3"
store = WorkflowStore(db_path)

print("Seeding OpenAgentStudio database...")

# Clear existing tables
with store._connection() as conn:
    conn.execute("DELETE FROM runs")
    conn.execute("DELETE FROM workflows")
    conn.execute("DELETE FROM agent_versions")
    conn.execute("DELETE FROM agents")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM memberships")
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM workspaces")

# 1. Workspace & User Bootstrap
email = "owner@openagent.local"
password = "Password123!"
workspace_name = "Local Studio Workspace"
password_hash = hash_password(password)

user = store.bootstrap_owner(email, password_hash, workspace_name)
user_id = user["id"]
workspace_id = user["workspace_id"]
print(f"Bootstrapped user {email} (id: {user_id}) in workspace {workspace_name} (id: {workspace_id})")

# 2. Pre-create active session for browser
raw_token = new_secret()
token_hash = hash_secret(raw_token)
csrf_token = new_secret()
expires_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()
store.create_session(token_hash, csrf_token, user_id, expires_at)

# Write session credentials to file for Playwright
with open(".data/session.json", "w") as f:
    json.dump({
        "raw_token": raw_token,
        "csrf_token": csrf_token,
        "email": email,
        "password": password
    }, f)

# 3. Workflows
wf1_def = {
    "nodes": [
        {"id": "start", "type": "input", "config": {"value": 7}},
        {"id": "scale", "type": "multiply", "config": {"factor": 3}},
        {"id": "finish", "type": "output", "config": {}}
    ],
    "edges": [
        {"source": "start", "target": "scale"},
        {"source": "scale", "target": "finish"}
    ]
}
wf1 = store.create_workflow("Number Transformer Demo", wf1_def, workspace_id)

wf2_def = {
    "nodes": [
        {"id": "start", "type": "input", "config": {"value": 25}},
        {"id": "scale", "type": "multiply", "config": {"factor": 4}},
        {"id": "finish", "type": "output", "config": {}}
    ],
    "edges": [
        {"source": "start", "target": "scale"},
        {"source": "scale", "target": "finish"}
    ]
}
wf2 = store.create_workflow("Batch Scaling Pipeline", wf2_def, workspace_id)

# 4. Runs
run1_result = {
    "status": "succeeded",
    "output": 21,
    "nodes": {
        "start": {"status": "succeeded", "output": 7},
        "scale": {"status": "succeeded", "output": 21},
        "finish": {"status": "succeeded", "output": 21}
    }
}
run1 = store.create_run(wf1["id"], run1_result, workspace_id)

run2_result = {
    "status": "succeeded",
    "output": 100,
    "nodes": {
        "start": {"status": "succeeded", "output": 25},
        "scale": {"status": "succeeded", "output": 100},
        "finish": {"status": "succeeded", "output": 100}
    }
}
run2 = store.create_run(wf2["id"], run2_result, workspace_id)

# 5. Agents
agent1 = store.create_agent({
    "name": "Document Analysis Agent",
    "instructions": "Extract key contractual obligations, statutory delivery deadlines, indemnification caps, and compliance breach penalties from enterprise PDF documentation.",
    "provider": "demo",
    "model": "deterministic",
    "tool_allowlist": [],
    "memory_policy": "disabled"
}, workspace_id)
# Upgrade agent1 to v2
store.update_agent(agent1["id"], {
    "name": "Document Analysis Agent",
    "instructions": "Extract key contractual obligations, statutory delivery deadlines, indemnification caps, and compliance breach penalties with structured JSON schema citations.",
    "provider": "demo",
    "model": "deterministic",
    "tool_allowlist": [],
    "memory_policy": "disabled"
}, workspace_id)

agent2 = store.create_agent({
    "name": "Code Synthesis Agent",
    "instructions": "Synthesize bounded, self-contained Python microservices adhering strictly to specified pytest unit test suites and interface contracts.",
    "provider": "demo",
    "model": "deterministic",
    "tool_allowlist": [],
    "memory_policy": "disabled"
}, workspace_id)
store.update_agent(agent2["id"], {
    "name": "Code Synthesis Agent",
    "instructions": "Synthesize bounded, self-contained Python microservices adhering strictly to specified pytest unit test suites, typing protocols, and zero external network calls.",
    "provider": "demo",
    "model": "deterministic",
    "tool_allowlist": [],
    "memory_policy": "disabled"
}, workspace_id)

agent3 = store.create_agent({
    "name": "Security Triage Agent",
    "instructions": "Parse static analysis SARIF artifacts and map identified code flaws to CWE classifications and CVSS v3.1 impact scores.",
    "provider": "demo",
    "model": "deterministic",
    "tool_allowlist": [],
    "memory_policy": "disabled"
}, workspace_id)

print("Seeding complete: 1 user, 1 workspace, 2 workflows, 2 runs, 3 agents with versions.")
