# UI/UX brief

## Direction

Developer-first dark operations workspace with restrained graphite surfaces, mint execution accents, compact monospace status labels, clear hierarchy, and a responsive canvas/sidebar layout. System fonts only; the local demo makes no third-party font request.

## Current implementation

The first UI milestone is a single workflow studio page with local workspace indication, a static graph preview, numeric input and multiplier configuration, validation, deterministic execution, node-level outputs, and error/status feedback. The page is served by FastAPI from `app/static`. It has no persistence, editable graph interactions, actual drag/drop, zoom/pan, theme toggle, login, or multi-screen routing. Navigation items marked “Soon” are not functional and must not be represented as shipped features.

## Screen inventory and state

| Screen | Status | Required states/acceptance |
|---|---|---|
| Product landing | Not built | Explain project and setup without claiming missing features |
| Authentication/setup | Not built | Secure session, clear workspace setup |
| Dashboard/agent directory | Not built | Scoped resources, loading/empty/error |
| Agent configuration | Not built | Validated safe defaults, masked credentials |
| Workflow studio | First local demo implemented | Keyboard-operable fields/buttons; validate/run/reset; visible success/failure; responsive graph preview |
| Tool registry/provider config | Not built | Server-side permission/secret controls |
| Memory management | Not built | Inspect/edit/delete with ownership/retention controls |
| Run history/trace | Not built | Persisted sanitized traces, accurate usage metadata |
| Approval inbox | Not built | Authorized review, one-shot decision/expiry feedback |
| Evaluation/usage | Not built | Real measurements only; label estimates/unavailable values |
| Workspace/settings | Not built | Role management and explicit destructive confirmation |

## Accessibility and responsive requirements

Use semantic sections/headings and form labels, visible focus rings, keyboard-capable controls, meaningful accessible button names, non-color-only execution state, reduced motion if motion is added, adequate contrast, and narrow-width layout without horizontal page overflow. Verify at desktop and mobile viewport sizes. The graph preview is not currently an interactive graph editor.

## UX acceptance tracking

The demo's input/factor fields, API validation, run action, result list, reset action, and error text are exercised by API tests only; real browser interaction has not yet been verified because the user's Edge profile was locked and could not be used safely.
