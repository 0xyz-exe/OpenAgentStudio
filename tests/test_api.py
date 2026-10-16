import asyncio
import json

import httpx
import pytest

from app.main import app, get_store
from app.store import WorkflowStore

_TEST_AUTH_HEADERS: dict[str, str] = {}


def request(method, path, *, auth=True, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = dict(_TEST_AUTH_HEADERS) if auth else {}
            headers.update(kwargs.pop("headers", {}))
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(send())


@pytest.fixture(autouse=True)
def authenticated_local_store(tmp_path):
    global _TEST_AUTH_HEADERS
    store = WorkflowStore(tmp_path / "test.sqlite3")
    app.dependency_overrides[get_store] = lambda: store
    _TEST_AUTH_HEADERS = {}
    response = request(
        "POST",
        "/api/auth/register",
        auth=False,
        json={
            "email": "owner@example.test",
            "password": "correct horse battery",
            "workspace_name": "Test workspace",
        },
    )
    assert response.status_code == 201
    _TEST_AUTH_HEADERS = {
        "Cookie": f"oas_session={response.cookies.get('oas_session')}",
        "X-CSRF-Token": response.json()["csrf_token"],
    }
    yield store
    _TEST_AUTH_HEADERS = {}
    app.dependency_overrides.pop(get_store, None)


@pytest.fixture
def isolated_store(authenticated_local_store):
    return authenticated_local_store


def workflow_payload():
    return {
        "nodes": [
            {"id": "start", "type": "input", "config": {"value": 7}},
            {"id": "scale", "type": "multiply", "config": {"factor": 3}},
            {"id": "finish", "type": "output", "config": {}},
        ],
        "edges": [
            {"source": "start", "target": "scale"},
            {"source": "scale", "target": "finish"},
        ],
    }


def test_health_endpoint_reports_service():
    response = request("GET", "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "open-agent-studio-api"}


def test_root_serves_workflow_studio():
    response = request("GET", "/")
    assert response.status_code == 200
    assert "Open Agent Studio" in response.text
    assert "Run workflow" in response.text


def test_validate_endpoint_returns_topological_order():
    response = request("POST", "/api/workflows/validate", json=workflow_payload())
    assert response.status_code == 200
    assert response.json() == {"valid": True, "order": ["start", "scale", "finish"]}


def test_execute_endpoint_runs_only_validated_deterministic_nodes():
    response = request("POST", "/api/workflows/execute", json=workflow_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output"] == 21
    assert body["nodes"]["scale"]["output"] == 21


def test_execute_endpoint_rejects_oversized_request_body():
    response = request(
        "POST",
        "/api/workflows/execute",
        content=b" " * (64 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request body exceeds 64 KiB limit"


def test_execute_endpoint_rejects_chunked_oversized_body():
    async def send():
        async def chunks():
            yield b" " * (32 * 1024)
            yield b" " * (32 * 1024 + 1)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/workflows/execute",
                content=chunks(),
                headers={"Content-Type": "application/json"},
            )

    response = asyncio.run(send())
    assert response.status_code == 413, response.text


def test_static_assets_are_served_from_local_app():
    response = request("GET", "/static/studio.js")
    assert response.status_code == 200
    assert "Run workflow" in response.text


def test_authenticated_workflow_routes_require_session(isolated_store):
    response = request("GET", "/api/workflows", auth=False)
    assert response.status_code == 401
    response = request("POST", "/api/workflows/validate", auth=False, json=workflow_payload())
    assert response.status_code == 401


def test_mutating_workflow_routes_require_csrf_token(isolated_store):
    response = request(
        "POST",
        "/api/workflows/validate",
        headers={"X-CSRF-Token": "incorrect-token"},
        json=workflow_payload(),
    )
    assert response.status_code == 403


def test_cross_origin_mutations_are_rejected(isolated_store):
    response = request(
        "POST",
        "/api/workflows/validate",
        headers={"Origin": "https://attacker.invalid"},
        json=workflow_payload(),
    )
    assert response.status_code == 403


def test_authentication_routes_use_non_disclosing_responses(isolated_store):
    response = request(
        "POST",
        "/api/auth/login",
        auth=False,
        json={"email": "owner@example.test", "password": "wrong password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"


def test_login_sets_httponly_session_cookie_without_exposing_hash(isolated_store):
    response = request(
        "POST",
        "/api/auth/login",
        auth=False,
        json={"email": "owner@example.test", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert "pbkdf2_sha256" not in response.text
    assert response.json()["user"]["role"] == "owner"


def test_logout_revokes_persisted_session(isolated_store):
    login_response = request(
        "POST",
        "/api/auth/login",
        auth=False,
        json={"email": "owner@example.test", "password": "correct horse battery"},
    )
    token = login_response.cookies.get("oas_session")
    headers = {
        "Cookie": f"oas_session={token}",
        "X-CSRF-Token": login_response.json()["csrf_token"],
    }
    logout_response = request("POST", "/api/auth/logout", auth=False, headers=headers)
    assert logout_response.status_code == 200
    me_response = request(
        "GET", "/api/auth/me", auth=False, headers={"Cookie": f"oas_session={token}"}
    )
    assert me_response.status_code == 401


def test_create_agent_defaults_to_deterministic_provider_and_no_tools(isolated_store):
    response = request(
        "POST",
        "/api/agents",
        json={"name": "Local assistant", "instructions": "Transform numbers safely."},
    )
    assert response.status_code == 201
    agent = response.json()
    assert agent["name"] == "Local assistant"
    assert agent["config"]["provider"] == "demo"
    assert agent["config"]["model"] == "deterministic"
    assert agent["config"]["tool_allowlist"] == []
    assert agent["version"] == 1


def test_agent_updates_create_immutable_config_versions(isolated_store):
    created = request("POST", "/api/agents", json={"name": "Assistant", "instructions": "Initial."})
    agent_id = created.json()["id"]
    updated = request(
        "PUT",
        f"/api/agents/{agent_id}",
        json={"name": "Assistant v2", "instructions": "Updated."},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    history = request("GET", f"/api/agents/{agent_id}/versions")
    assert [item["version"] for item in history.json()["versions"]] == [2, 1]
    assert history.json()["versions"][1]["config"]["instructions"] == "Initial."


def test_agent_api_requires_authentication_and_hides_foreign_workspace(isolated_store):
    assert request("GET", "/api/agents", auth=False).status_code == 401
    agent = request(
        "POST", "/api/agents", json={"name": "Private agent", "instructions": "Local."}
    ).json()
    assert isolated_store.list_agents("unrelated-workspace") == []
    assert isolated_store.get_agent(agent["id"], "unrelated-workspace") is None


def test_agent_config_rejects_unregistered_tools_and_unknown_fields(isolated_store):
    payload = {"name": "Unsafe", "instructions": "Do work.", "tool_allowlist": ["shell"]}
    assert request("POST", "/api/agents", json=payload).status_code == 422
    payload = {"name": "Extra", "instructions": "Do work.", "admin": True}
    assert request("POST", "/api/agents", json=payload).status_code == 422
    payload = {"name": "Memory", "instructions": "Do work.", "memory_policy": "transient"}
    assert request("POST", "/api/agents", json=payload).status_code == 422


def test_agent_archive_hides_agent_and_versions(isolated_store):
    created = request(
        "POST", "/api/agents", json={"name": "To archive", "instructions": "Keep history."}
    )
    agent_id = created.json()["id"]
    archived = request("DELETE", f"/api/agents/{agent_id}")
    assert archived.status_code == 204
    assert request("GET", f"/api/agents/{agent_id}").status_code == 404
    assert request("GET", "/api/agents").json()["agents"] == []
    assert request("GET", f"/api/agents/{agent_id}/versions").json()["versions"][0]["version"] == 1


def test_workspace_queries_do_not_return_foreign_data(isolated_store):

    with isolated_store._connection() as connection:
        connection.executemany(
            "INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
            [
                ("workspace-a", "Primary", "2026-01-01T00:00:00+00:00"),
                ("workspace-b", "Other workspace", "2026-01-01T00:00:00+00:00"),
            ],
        )
    workflow = isolated_store.create_workflow("Private", workflow_payload(), "workspace-a")
    assert isolated_store.get_workflow(workflow["id"], "workspace-b") is None
    assert isolated_store.list_workflows("workspace-b") == []
    with pytest.raises(LookupError):
        isolated_store.create_run(workflow["id"], {"status": "succeeded"}, "workspace-b")


def test_save_list_and_execute_workflow_persists_run(isolated_store):
    response = request(
        "POST",
        "/api/workflows",
        json={"name": "Saved multiplier", "definition": workflow_payload()},
    )
    assert response.status_code == 201
    workflow = response.json()
    assert workflow["name"] == "Saved multiplier"
    assert workflow["definition"]["nodes"][1]["type"] == "multiply"

    listed = request("GET", "/api/workflows")
    assert [item["id"] for item in listed.json()["workflows"]] == [workflow["id"]]

    executed = request("POST", f"/api/workflows/{workflow['id']}/execute")
    assert executed.status_code == 200
    assert executed.json()["status"] == "succeeded"
    assert executed.json()["output"] == 21
    assert executed.json()["run_id"]

    runs = request("GET", f"/api/workflows/{workflow['id']}/runs")
    assert len(runs.json()["runs"]) == 1
    assert runs.json()["runs"][0]["result"]["output"] == 21

    reopened = WorkflowStore(isolated_store.path)
    assert len(reopened.list_runs(workflow["id"], workflow["workspace_id"])) == 1


def test_save_endpoint_rejects_invalid_graph(isolated_store):
    payload = {"name": "Invalid", "definition": workflow_payload()}
    payload["definition"]["nodes"][1]["type"] = "shell"
    response = request("POST", "/api/workflows", json=payload)
    assert response.status_code == 422


def test_save_endpoint_rejects_non_finite_json_numbers(isolated_store):
    payload = {"name": "Invalid number", "definition": workflow_payload()}
    payload["definition"]["nodes"][0]["config"]["value"] = float("nan")
    response = request(
        "POST",
        "/api/workflows",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_execute_endpoint_rejects_unsupported_node_types():
    payload = workflow_payload()
    payload["nodes"][1]["type"] = "shell"
    response = request("POST", "/api/workflows/execute", json=payload)
    assert response.status_code == 422
