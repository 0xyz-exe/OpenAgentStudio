# Database design — current state

No database is implemented or configured. The current workflow validate/execute endpoints are stateless and do not persist definitions, runs, traces, users, or approvals.

## Proposed future entities

- `users`: identity and authentication metadata.
- `workspaces`: owner boundary and workspace settings.
- `workspace_memberships`: user/workspace role, unique per pair.
- `agents`: workspace-owned agent identity, archive state, current config version pointer.
- `agent_versions`: immutable validated configuration versions with creation metadata.
- `workflows`: workspace-owned workflow identity and archive state.
- `workflow_versions`: immutable validated graph JSON and version number.
- `runs`: workspace/workflow version, state, correlation ID, timestamps, cancellation/terminal reason.
- `run_nodes`: run/node version, state, timestamps, attempts and sanitized result/error.
- `approval_requests`: run/step, pending/approved/rejected/expired state, requester/decider and decision timestamp.
- `audit_events`: actor, workspace, action, object reference, timestamp and sanitized metadata.
- `conversation_memory`: explicitly scoped transient/persistent memory with retention metadata and deletion semantics.

## Required invariants before implementation

Every workspace-owned row must be scoped and authorized on every operation; scope should be included in uniqueness/foreign-key strategies where practical. Workflow versions are immutable once executed. State transitions and approval decisions are transactional and one-shot. Idempotency keys protect retryable side effects. Provider calls happen outside long-lived DB transactions. Sensitive prompts, credentials and raw tool payloads are excluded or minimized in durable traces. Migrations must be forward/reversible where feasible and tested against disposable data.

## Storage choice

SQLite is a proposal for simple local development, not yet an implemented portability guarantee. Select ORM/schema/migration tooling only after validating async/concurrency requirements and PostgreSQL compatibility. Redis is out of scope until measured workload requires it.
