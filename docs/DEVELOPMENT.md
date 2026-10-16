# Development guide

## Supported setup

Python 3.11+; current development was exercised with Python 3.14.7 on Windows 11. Use a project-local virtual environment. The prototype has no database or external API dependency.

## Install and run

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Do not alter a host package-manager script policy to install the abandoned frontend scaffold. Static assets are under `app/static/`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use `httpx.ASGITransport` for API integration and unittest assertions for engine validation. No test uses a production database or a live model.

## Current engine contract

Only a single linear graph containing exactly one `input`, exactly one `output`, and zero or more `multiply` nodes is supported. `validate_workflow` rejects cycles, branching, joining, disconnected graphs, duplicate edges/IDs, invalid directions, and unknown types. `run_workflow` returns deterministic node outputs and failures without side effects. Add features as small vertical test-first changes and keep the tool surface allowlisted.

## Engineering guardrails

- Preserve loopback-only development; do not configure public exposure before auth and authorization exist.
- Never put provider credentials into the browser or repository.
- Use safe DOM insertion (`textContent`/element APIs), not untrusted HTML.
- Document what is not implemented; don't label design-only requirements as capabilities.
- Add regression tests before fixing bugs and execute the focused then full suite.
- Do not commit `.venv`, secrets, test data, or machine-generated artifacts.
