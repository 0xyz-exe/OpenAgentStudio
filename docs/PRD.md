# Product requirements — Open Agent Studio

**Status:** Proposed requirements for a new project; not implemented functionality. Targets below are proposals, not measured baselines.

## Problem and vision

Developers need a inspectable way to define and execute multi-step AI-assisted workflows without surrendering unrestricted tool access or losing track of failures, approvals, and usage. Open Agent Studio aims to provide a local-first developer platform for controlled workflows, tool permissions, human decisions, and traceable execution.

## Personas and needs

- **Individual developer:** quickly prototypes a workflow using deterministic demo tools before configuring a provider.
- **Engineering team operator:** manages workspace-owned agents and tools, controls sensitive actions, and investigates failures.
- **Researcher:** repeats workflow runs and compares outcomes with honest provenance.
- **Contributor:** extends provider/tool adapters without coupling them to core execution logic.

## Product principles

Least privilege; deterministic demo first; transparent execution; provider replaceability; explicit data ownership; safe failure over silent fallback; incremental, test-backed delivery.

## MVP scope and exclusions

**MVP (P0):** secure sign-in and workspace isolation; agent configuration; provider-neutral interface with deterministic provider-free mode; strict-schema safe tools; validated directed acyclic workflows; bounded deterministic execution; persisted state and traces; configurable human approval; basic scoped transient memory; honest usage fields; functional responsive UI and automated critical-path tests.

**Out of scope for initial MVP:** arbitrary shell, unrestricted filesystem or network tools; distributed execution; multi-agent collaboration; plugin marketplace; enterprise SSO; broad public hosting; guaranteed free/always-available external AI; unbounded autonomous execution.

## User journeys

1. **First setup:** launch local services with no paid key; see health/readiness and demo workspace with explicit sample labeling.
2. **Create/edit agent:** enter name, instructions, model selection, tool allowlist, and memory policy; receive validation; save a versioned config.
3. **Register tool:** choose a supported implementation, inspect input/output schema and permissions, enable/disable; no arbitrary code upload in MVP.
4. **Select model:** choose demo or configured provider; credentials stay server-side and masked; provider errors are visible, not silently switched.
5. **Design workflow:** create typed nodes/edges, configure node inputs, validate graph, save; unsupported cycles/branches produce actionable errors.
6. **Execute:** start a run, follow node states, see bounded errors and trace correlation, cancel only where safe.
7. **Approve/reject:** authorized user reviews a pending request with sanitized context; one decision only; expired/duplicate decisions rejected and audited.
8. **Inspect:** find run, inspect statuses/timing/retry counts and sanitized errors; no secret/raw sensitive payload exposure by default.
9. **Evaluate:** run deterministic evaluation examples; distinguish recorded results from proposed metrics and never fabricate scores.
10. **Manage access/keys:** assign workspace roles; provider secrets are server-side, masked, and editable/rotatable without disclosure.

## Requirements and acceptance criteria

### P0

- **Identity and workspace:** protected routes require an authenticated identity; every resource query and mutation is workspace-scoped; cross-workspace access tests deny access.
- **Agents:** create/read/update/archive; validate configuration; edits are versioned; safe default permissions are empty/minimal.
- **Providers:** provider-neutral contract; deterministic demo works without credentials; configured provider errors map to stable sanitized errors; no secret is returned to clients/logs.
- **Tools:** strict input schema validation before invocation, per-agent allowlist, bounded time/output, structured result; no unrestricted execution capability enabled by default.
- **Workflow:** typed nodes/edges persist; invalid references and cycles are rejected; deterministic sequence execution is reproducible.
- **Run engine:** explicit legal state transitions; persisted node timestamps/status/errors; bounded eligible retries; no transaction held during model call; duplicate side effects are prevented or explicitly non-retryable.
- **Approvals:** configured sensitive step pauses; authorized approve/reject transitions exactly once; expiry and audit events enforced.
- **Trace/usage:** correlation ID and step status/duration available; token counts only when provider-reported; cost only with known pricing; unavailable values remain unavailable.
- **UI:** nav and principal flows work; forms validate; async operations have loading/error states; destructive action confirmation; responsive and keyboard accessible.
- **Verification:** automated unit/integration tests cover graph validation, transitions, tool validation, authorization, approval, usage, and provider errors; browser tests cover deterministic flow where available.

### P1

Workflow history/rollback; evaluation datasets and repeatable comparisons; semantic retrieval; scheduling; advanced branching; webhooks; import/export with secure validation; collaboration and audit exports.

### P2

Multi-agent collaboration; plugin marketplace; distributed execution; enterprise SSO; advanced routing/governance.

## Non-functional requirements

Secure-by-default; typed contracts; bounded resource consumption; documented local startup; graceful failure/shutdown; accessibility and responsive operation; observable execution; persistence migrations preserve user data; external provider and database use are optional for local deterministic demo.

## Proposed success metrics

Measure after telemetry is implemented and consent/retention rules are defined: workflow completion rate; tool success rate; median and p95 run latency; provider-reported token counts; estimated cost only when pricing is known; approval rejection/expiry rate; repeatable evaluation metrics; critical test coverage/security regressions. No baseline or target is claimed. Proposed initial engineering goal: every metric must identify its denominator, missing-data policy, and collection window before dashboard display.
