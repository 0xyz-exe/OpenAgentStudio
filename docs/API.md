# API contract — current local prototype

**Current scope (2026-10-16):** Public health/static routes; local owner setup/sign-in/logout; protected workspace-scoped agent profile CRUD/archive/version-history routes; workflow validate/save/update/read/execute/run-history routes. Cookie session and CSRF/origin controls apply. Agent provider is limited to deterministic demo; tool allowlists are enforced empty and memory is disabled. Workflows execute only the bounded deterministic linear nodes. The app remains loopback-only and is not the complete PRD MVP.

> Historical endpoint notes below describe the pre-auth prototype and are superseded by this current scope summary.

## Current routes

| Method and path | Auth | Behavior |
|---|---|---|
| `GET /health`, `GET /` | No | Liveness and local studio page |
| `GET /api/auth/status`, `GET /api/auth/me` | No / session | Setup status; current session (401 when signed out) |
| `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout` | No / session+CSRF | One-time local owner bootstrap, sign-in, session revocation |
| `GET/POST /api/agents` | Session / session+CSRF | Workspace-scoped agent list/create |
| `GET/PUT/DELETE /api/agents/{id}` | Session / session+CSRF | Read, versioned update, archive |
| `GET /api/agents/{id}/versions` | Session | Immutable config history |
| `GET/POST /api/workflows` | Session / session+CSRF | List/save validated workflows |
| `GET/PUT /api/workflows/{id}` | Session / session+CSRF | Read/update workflow |
| `POST /api/workflows/{id}/execute`, `GET /api/workflows/{id}/runs` | Session+CSRF / session | Run persisted workflow and inspect saved results |
| `POST /api/workflows/validate`, `POST /api/workflows/execute` | Session+CSRF | Validate or run submitted deterministic workflow |

Cookie-authenticated state-changing routes require `X-CSRF-Token`; browser mutations reject cross-origin origins. Agent configuration currently permits only `provider=demo`, `model=deterministic`, empty `tool_allowlist`, and `memory_policy=disabled`.

## Endpoints

### `GET /health`
Returns `{"status":"ok","service":"open-agent-studio-api"}` when the process responds. This is a liveness indicator, not a dependency readiness check.

### `GET /`
Serves the local workflow studio HTML.

### `POST /api/workflows/validate`
Accepts a workflow document and returns `{"valid":true,"order":[...]}`. Structural validation errors return HTTP 422 with a `detail` message.

### `POST /api/workflows/execute`
Accepts the same workflow document and returns node results and terminal status. Execution is synchronous, in-memory, deterministic and supports only a single linear path through `input`, `multiply`, and `output` nodes. Invalid structure returns HTTP 422; invalid runtime node data returns an execution with `status: failed` and a sanitized validation message in that node's result. No execution record is persisted.

## Request shape

```json
{
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
```

Node count is capped at 100; edge count at 200; request bodies are capped at 64 KiB, including chunked requests. Unknown top-level/node/edge fields are rejected by the API models. Supported numeric magnitude is capped to absolute `10**308` at input, factor and result. Branching, joins, cycles, unknown nodes, repeated edges, multiple input/output nodes, and disconnected structures are rejected. The engine has no arbitrary code, shell, network, or filesystem operations.

## Error semantics

Malformed request schema and invalid workflow structure return 422. A supported graph whose runtime operation cannot consume its input returns a result with `status: failed`; this distinction is intentional. Unexpected server errors are not currently assigned a stable public contract. Do not expose this development API to untrusted clients.
