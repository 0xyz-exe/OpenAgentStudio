# Threat model (initial, design-stage)

**Status:** preliminary. This local prototype now contains a static UI and deterministic calculator workflow API. It still has no authentication, persistence, model provider, or privileged tool. This is not a completed security review.

## Assets

Workspace data; agent instructions; workflow definitions; provider credentials; execution outputs and traces; approval records; user sessions; resource capacity and model/tool spend.

## Trust boundaries

Browser to API; authenticated user to workspace-owned objects; workflow definition to executor; agent/model instructions to tool invocation; external provider and retrieved/tool output to application; application to database and host resources.

## Threat actors and abuse cases

A malicious or compromised workspace member; malicious workflow/prompt/document content; compromised external provider/tool output; unauthenticated internet client; accidental operator misconfiguration.

| Threat | Initial controls required | Verification required |
|---|---|---|
| Cross-workspace IDOR/data leakage | Derive scope from authenticated membership; scoped repository queries; deny by default | Cross-tenant integration tests for reads/writes/approval |
| Credential leakage | Server-side secret storage; masked write-only fields; redaction in structured logs/errors | Secret canary tests across API/log paths |
| Prompt injection/tool misuse | Model output never grants permissions; server-side tool allowlist and schemas; sensitive tool approval | Adversarial tests proving unauthorized tool calls are denied |
| SSRF/path traversal/command injection | No arbitrary URL/path/shell tool by default; strict allowlists if introduced | Negative tests and code review of each capability |
| Resource exhaustion | Request/body/output limits, timeouts, concurrency and quota bounds | Load/timeout tests with bounded resource assertions |
| Duplicate effects/races | Idempotency, transactional state transitions, unique approval decisions | Concurrent retry/approval regression tests |
| XSS/unsafe import | Escape untrusted text; schema-validate imports; size limits | Browser tests with hostile strings and malformed imports |
| CSRF/session abuse | Framework-appropriate secure cookie/session controls and origin protections | Auth/session and CSRF regression tests |
| Sensitive trace retention | Minimize prompt/tool payload retention; sanitize errors; define retention controls | Verify logs/traces do not contain secrets or unnecessary payloads |

## Security requirements

Least privilege; authenticated workspace membership for every protected action; no provider secret to browser; explicit tool permissions; strict schema validation; bounded execution; auditable approval; no silent provider fallback; dependency and configuration review; secure shutdown and migrations.

## Residual risk and next review

All controls are requirements only and remain unimplemented/unverified. Before any deployment, review actual authentication/session design, database isolation, secret handling, tool network/filesystem boundaries, quotas, dependency advisories, import/export, and operational retention. Do not describe this threat model as a passed security audit.
