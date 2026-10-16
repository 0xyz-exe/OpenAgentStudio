import math
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import hash_password, hash_secret, new_secret, verify_password
from app.store import BootstrapClosed, WorkflowStore
from app.workflows import WorkflowError, run_workflow, validate_workflow


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowNode(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=40)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def config_must_be_finite_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        def check(item: Any, depth: int = 0) -> None:
            if depth > 32:
                raise ValueError("node configuration is nested too deeply")
            if item is None or isinstance(item, (str, bool)):
                return
            if isinstance(item, int):
                if abs(item) > 10**308:
                    raise ValueError("integer is outside the supported range")
                return
            if isinstance(item, float):
                if not math.isfinite(item):
                    raise ValueError("numbers must be finite")
                return
            if isinstance(item, list):
                for child in item:
                    check(child, depth + 1)
                return
            if isinstance(item, dict):
                for child in item.values():
                    check(child, depth + 1)
                return
            raise ValueError("configuration must contain JSON-compatible values")

        check(value)
        return value


class WorkflowEdge(StrictModel):
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)


class WorkflowRequest(StrictModel):
    nodes: list[WorkflowNode] = Field(min_length=1, max_length=100)
    edges: list[WorkflowEdge] = Field(max_length=200)


class WorkflowCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    definition: WorkflowRequest

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("workflow name cannot be blank")
        return value


class AgentConfigRequest(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    instructions: str = Field(default="", max_length=4000)
    provider: Literal["demo"] = "demo"
    model: Literal["deterministic"] = "deterministic"
    tool_allowlist: list[str] = Field(default_factory=list, max_length=20)
    memory_policy: Literal["disabled"] = "disabled"

    @field_validator("name")
    @classmethod
    def agent_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("agent name cannot be blank")
        return value

    @field_validator("tool_allowlist")
    @classmethod
    def no_unregistered_tools(cls, value: list[str]) -> list[str]:
        if value:
            raise ValueError("no executable tools are registered yet")
        return value


class RegisterRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    workspace_name: str = Field(default="My workspace", min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain or any(char.isspace() for char in value):
            raise ValueError("enter a valid email address")
        return value

    @field_validator("workspace_name")
    @classmethod
    def valid_workspace_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("workspace name cannot be blank")
        return value


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


_SESSION_COOKIE = "oas_session"
_SESSION_TTL = timedelta(hours=12)
_MAX_BODY_BYTES = 64 * 1024


class RequestBodyLimitMiddleware:
    """Reject oversized request bodies, including chunked bodies without a length."""

    def __init__(self, app, max_bytes: int = _MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {
            "POST",
            "PUT",
            "PATCH",
        }:
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        content_length = request_headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                response = JSONResponse(
                    status_code=400, content={"detail": "invalid Content-Length"}
                )
                await response(scope, receive, send)
                return
            if declared_length > self.max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "request body exceeds 64 KiB limit"},
                )
                await response(scope, receive, send)
                return

        chunks = []
        received = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                response = JSONResponse(
                    status_code=400,
                    content={"detail": "client disconnected during request"},
                )
                await response(scope, receive, send)
                return
            if message["type"] == "http.request":
                chunks.append(message)
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": "request body exceeds 64 KiB limit"},
                    )
                    await response(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break

        replay = iter(chunks)

        async def replay_receive():
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        await self.app(scope, replay_receive, send)


class SameOriginMutationMiddleware:
    """Reject browser cross-origin state changes while keeping CLI clients usable."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            headers = dict(scope.get("headers", []))
            origin = headers.get(b"origin")
            if origin:
                parsed = urlsplit(origin.decode("latin-1"))
                host = headers.get(b"host", b"").decode("latin-1")
                if (
                    not parsed.netloc
                    or parsed.netloc.casefold() != host.casefold()
                    or parsed.scheme != scope.get("scheme")
                ):
                    response = JSONResponse(
                        status_code=403,
                        content={"detail": "cross-origin mutation denied"},
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Set conservative browser policy headers on UI and API responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (
                            b"content-security-policy",
                            (
                                b"default-src 'self'; script-src 'self'; style-src 'self'; "
                                b"img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                                b"base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
                            ),
                        ),
                    ]
                )
                if scope.get("path", "").startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = FastAPI(
    title="Open Agent Studio API",
    version="0.1.0",
    description=(
        "Local-first deterministic workflow demo with SQLite persistence and local-owner "
        "authentication."
    ),
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return safe validation details without reflecting attacker-controlled inputs."""
    details = [
        {
            "loc": error.get("loc", []),
            "msg": error.get("msg", "Invalid request"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(SameOriginMutationMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

_store: WorkflowStore | None = None


def get_store() -> WorkflowStore:
    global _store
    if _store is None:
        default_db = Path(__file__).resolve().parents[1] / ".data" / "studio.sqlite3"
        _store = WorkflowStore(os.environ.get("OPEN_AGENT_STUDIO_DB", default_db))
    return _store


def current_session(request: Request, store: WorkflowStore = Depends(get_store)) -> dict[str, str]:
    token = request.cookies.get(_SESSION_COOKIE)
    session = (
        store.get_session(hash_secret(token))
        if token and len(token) <= 128 and token.isascii()
        else None
    )
    if session is None:
        raise HTTPException(status_code=401, detail="authentication required")
    return session


def authenticated_mutation(
    request: Request, session: dict[str, str] = Depends(current_session)
) -> dict[str, str]:
    csrf = request.headers.get("x-csrf-token", "")
    if not secrets.compare_digest(csrf.encode("utf-8"), session["csrf_token"].encode("utf-8")):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    return session


def _new_authenticated_response(
    store: WorkflowStore, user: dict[str, str], *, status_code: int = 200
) -> JSONResponse:
    token = new_secret()
    csrf_token = new_secret()
    expires_at = datetime.now(UTC) + _SESSION_TTL
    store.create_session(hash_secret(token), csrf_token, user["id"], expires_at.isoformat())
    response = JSONResponse(
        content={
            "user": {
                key: user[key] for key in ("id", "email", "workspace_id", "workspace_name", "role")
            },
            "csrf_token": csrf_token,
        },
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        max_age=int(_SESSION_TTL.total_seconds()),
        httponly=True,
        secure=False,
        samesite="strict",
        path="/",
    )
    return response


@app.get("/api/auth/status")
def auth_status(store: WorkflowStore = Depends(get_store)) -> dict[str, bool]:
    return {"setup_required": store.user_count() == 0}


@app.post("/api/auth/register", status_code=201)
def register(request: RegisterRequest, store: WorkflowStore = Depends(get_store)) -> JSONResponse:
    if store.user_count() != 0:
        raise HTTPException(status_code=409, detail="initial account already exists")
    try:
        user = store.bootstrap_owner(
            request.email, hash_password(request.password), request.workspace_name
        )
    except BootstrapClosed as exc:
        raise HTTPException(status_code=409, detail="initial account already exists") from exc
    return _new_authenticated_response(store, user, status_code=201)


@app.post("/api/auth/login")
def login(request: LoginRequest, store: WorkflowStore = Depends(get_store)) -> JSONResponse:
    user = store.get_user(request.email.strip().lower())
    password_hash = user["password_hash"] if user else None
    if not verify_password(request.password, password_hash) or user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return _new_authenticated_response(store, user)


@app.get("/api/auth/me")
def who_am_i(session: dict[str, str] = Depends(current_session)) -> dict[str, Any]:
    return {
        "user": {
            key: session[key] for key in ("id", "email", "workspace_id", "workspace_name", "role")
        },
        "csrf_token": session["csrf_token"],
    }


@app.post("/api/auth/logout")
def logout(
    request: Request,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> JSONResponse:
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        store.revoke_session(hash_secret(token))
    response = JSONResponse(content={"status": "signed_out"}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        _SESSION_COOKIE, httponly=True, secure=False, samesite="strict", path="/"
    )
    return response


@app.get("/", include_in_schema=False)
def studio() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "open-agent-studio-api"}


@app.post("/api/agents", status_code=201)
def create_agent(
    request: AgentConfigRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    return store.create_agent(request.model_dump(), session["workspace_id"])


@app.get("/api/agents")
def list_agents(
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    return {"agents": store.list_agents(session["workspace_id"])}


@app.get("/api/agents/{agent_id}")
def get_agent(
    agent_id: str,
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    agent = store.get_agent(agent_id, session["workspace_id"])
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@app.put("/api/agents/{agent_id}")
def update_agent(
    agent_id: str,
    request: AgentConfigRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    agent = store.update_agent(agent_id, request.model_dump(), session["workspace_id"])
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@app.get("/api/agents/{agent_id}/versions")
def list_agent_versions(
    agent_id: str,
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    versions = store.list_agent_versions(agent_id, session["workspace_id"])
    if versions is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return {"versions": versions}


@app.delete("/api/agents/{agent_id}", status_code=204)
def archive_agent(
    agent_id: str,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> None:
    if not store.archive_agent(agent_id, session["workspace_id"]):
        raise HTTPException(status_code=404, detail="agent not found")


@app.post("/api/workflows", status_code=201)
def create_workflow(
    request: WorkflowCreateRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    definition = request.definition.model_dump()
    try:
        validate_workflow(definition)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return store.create_workflow(request.name.strip(), definition, session["workspace_id"])


@app.put("/api/workflows/{workflow_id}")
def update_workflow(
    workflow_id: str,
    request: WorkflowCreateRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    definition = request.definition.model_dump()
    try:
        validate_workflow(definition)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    workflow = store.update_workflow(workflow_id, request.name, definition, session["workspace_id"])
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@app.get("/api/workflows")
def list_workflows(
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    return {"workflows": store.list_workflows(session["workspace_id"])}


@app.get("/api/workflows/{workflow_id}")
def get_workflow(
    workflow_id: str,
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    workflow = store.get_workflow(workflow_id, session["workspace_id"])
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return workflow


@app.post("/api/workflows/{workflow_id}/execute")
def execute_saved_workflow(
    workflow_id: str,
    session: dict[str, str] = Depends(authenticated_mutation),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    workflow = store.get_workflow(workflow_id, session["workspace_id"])
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    result = run_workflow(workflow["definition"])
    run = store.create_run(workflow_id, result, session["workspace_id"])
    return {**result, "run_id": run["id"], "created_at": run["created_at"]}


@app.get("/api/workflows/{workflow_id}/runs")
def list_workflow_runs(
    workflow_id: str,
    session: dict[str, str] = Depends(current_session),
    store: WorkflowStore = Depends(get_store),
) -> dict[str, Any]:
    if store.get_workflow(workflow_id, session["workspace_id"]) is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return {"runs": store.list_runs(workflow_id, session["workspace_id"])}


@app.post("/api/workflows/validate")
def validate(
    request: WorkflowRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
) -> dict[str, Any]:
    workflow = request.model_dump()
    try:
        return {"valid": True, "order": validate_workflow(workflow)}
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/workflows/execute")
def execute(
    request: WorkflowRequest,
    session: dict[str, str] = Depends(authenticated_mutation),
) -> dict[str, Any]:
    workflow = request.model_dump()
    try:
        return run_workflow(workflow)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
