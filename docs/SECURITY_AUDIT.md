# Security audit — local prototype, not production approved

**Current review (2026-10-16):** This top section is authoritative; historical notes below predate authentication and persistence and are superseded. This is a bounded code review, not penetration testing or security certification.

## Findings by priority

### Critical
- No critical exploitable issue was demonstrated in the limited tests. This is not evidence the application is vulnerability-free.

### High
- **Shared deployment unsafe:** cookie `Secure=False` for plain local HTTP; no login rate limiting, account recovery, or hardened deployment. Bind to `127.0.0.1` only; never expose to LAN/internet.
- **MVP security features absent:** no provider, tool registry/allowlist, approval flow, or bounded retry/run-state system. Do not add powerful tool execution without server-side authorization, strict schemas, time/output limits, approvals as applicable, and regression tests.
- **Single-owner only:** initial owner bootstrap and one workspace; no complete multi-user role/tenant management. Queries for workflow/run records are scoped by workspace and tests exercise cross-workspace denials, but PRD identity requirements remain incomplete.

### Medium
- No login throttling, password reset, MFA, session-management UI, or complete role administration.
- SQLite migration/backup/restore and concurrent multi-worker operation are not production-validated; preserve existing user databases.
- Request cap (64 KiB) and workflow bounds exist, but no request-read deadline, run concurrency quota, or abuse controls.
- Persisted demo runs lack node-level durable traces/timing, approval audit, and retention controls.
- No dependency advisory audit, fuzzing, load test, penetration test, or deployment review.

### Low
- Unauthenticated `GET /api/auth/me` intentionally returns 401 and appears as a browser console error during initial sign-in bootstrap.
- Browser security headers exist but are not comprehensively covered by automated assertions.

## Controls observed

PBKDF2-SHA256 password hashes use 600,000 rounds and per-user salts. Session secrets are random, only hashed tokens persist, cookies are HttpOnly/SameSite=Strict with finite lifetime, and authenticated writes require CSRF token plus same-origin checks. Workflow/run storage queries scope by workspace. Only strict deterministic `input`, `multiply`, and `output` nodes execute; there is no shell, arbitrary Python, filesystem, network, or uploaded-code tool. Validation responses avoid reflecting inputs; UI uses safe DOM text APIs. `.data/`, `build/`, and `.playwright-cli/` are ignored.

## Verification evidence

- `.venv/Scripts/python -m pytest -q`: 40 passed (20.87s) in the final all-checks run with `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GOOGLE_API_KEY` unset; includes auth, agent CRUD/version/archive, CSRF, origin, workspace scoping, numeric limits, body caps, deterministic execution and persistence, and tool registry schema/bounds/catalog/rejection tests.
- Heuristic scan for credential assignments and common `sk-` tokens: `matches: []` (excluded environments and generated browser/build/data artifacts; not a full secret scanner).
- `git check-ignore -v` confirmed local DB, build, and Playwright artifacts are ignored.
- Loopback Chromium smoke flow exercised setup, save/execute, history reload, and logout; this is not a maintained assertion-based E2E suite. Expected unauthenticated 401 appeared in browser console.
- No dependency scanner, penetration test, or hosted deployment assessment was run.

**Release gate:** Not release-ready for shared use. Keep loopback-only until role-aware authorization, provider/tool boundaries, approval state machine, bounded execution/tracing, login abuse controls, and missing security/browser tests are implemented and verified.

> Historical audit text below is superseded by this review.

**Scope:** source code present at initial demo milestone. No authentication, database, provider credentials, model calls, or arbitrary tools exist. This is a preliminary review, not a production security certification.

| Area | Finding/status | Action/limitation |
|---|---|---|
| Authentication/access control | Not implemented | Bind to `127.0.0.1`; never expose to untrusted clients. Add auth/workspace scoping before adding user data or shared deployment. |
| Cross-workspace isolation | Not applicable yet; no workspace persistence | Add isolation tests with workspace-bound data layer. |
| SQL injection | No database/query layer | Reassess with persistence. |
| XSS | UI inserts runtime messages/results through DOM `textContent` and element creation; no `innerHTML` remains | Keep using safe DOM APIs for all user/model/tool content; browser security verification still pending. |
| CSRF/session | No session/auth or cross-origin mutation configuration | Must design secure sessions and CSRF protections before auth. |
| SSRF/path traversal/command injection | No URL/path/shell tool or file import/export | Do not add unrestricted tools. Review each future external capability separately. |
| Prompt injection/tool misuse | No LLM/provider or powerful tools yet | Model output must not authorize tools; enforce server-side allowlists/schema/approval. |
| Resource exhaustion | 64 KiB request-body cap including chunked requests; node/edge limits and safe numeric range; no rate limit, concurrency quota, or request-read timeout | Add runtime quotas/timeouts before shared exposure; test limits under real ASGI server/proxy |
| Secret exposure | No secrets are read or returned; demo requires no key | Optional future credentials must be server-side, masked and redacted. |
| Logging/retention | No execution logs or persistent traces | Define minimization/retention before adding storage. |
| Retry/idempotency/approval race | No retries, side effects, approvals, or durable states | Required when those features are implemented. |
| Dependency vulnerabilities | No advisory audit run | Run dependency audit before release and maintain update process. |
| Workflow schema | Strict API model rejects unknown shape keys; graph bounds and supported node types validated; only linear calculator workflow executes | No imports; add request size cap and property/security regression tests. |

## Verification performed

- Unit/API tests cover linear workflow execution, cycle/type rejection, malformed numeric boundaries, endpoint success/errors, 64 KiB request limits (declared and chunked), and serving static assets.
- Numeric boundary regression tests cover non-finite floats and oversized integer inputs.
- No dedicated security scanner, dependency advisory audit, browser XSS test, fuzzing, penetration test, or deployment review has been performed.

## Remediation gate

Do not expose or deploy this current build for multiple users. Prior to any shared deployment, implement authentication, workspace isolation, request/resource limits, persistence safety, secure sessions, observability redaction and the regression tests listed in `THREAT_MODEL.md`.
