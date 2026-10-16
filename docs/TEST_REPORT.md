# Test report — current local verification

**Current checkpoint (2026-10-16):** The results below supersede historical run notes further down. Windows 11, `C:/Users/wondr/OpenAgentStudio`, Python 3.14.7.

## Executed commands and results

| Command | Actual result |
|---|---|
| `.venv/Scripts/python -m pytest -q` | **32 passed in 14.98s** (provider keys unset) |
| `.venv/Scripts/python -m ruff check app tests` | **All checks passed** |
| `.venv/Scripts/python -m ruff format --check app tests` | **8 files already formatted** |
| `.venv/Scripts/python -m mypy app` | **Success: no issues found in 5 source files** |
| `.venv/Scripts/python -m compileall -q app tests` | Exit 0, included in final combined command below |
| `node --check app/static/studio.js` | Exit 0, included in final combined command below |
| `git diff --check` | Exit 0, included in final combined command below |
| `.venv/Scripts/python -m pip wheel . --no-deps --wheel-dir C:/Users/wondr/AppData/Local/hermes/cache/scratch/oas-wheel-final3` | Built `open_agent_studio-0.1.0-py3-none-any.whl` successfully; SHA-256 `0770931f8a8b4ab1f8df14c5af17523fe84d51d4a4e97163aa459baf1077c4ae` |
| Wheel inspection Python snippet | Found 6 packaged static assets including `agents.css`; assertion passed |
| `.venv/Scripts/python -m pytest -q` (with `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` unset) | **40 passed in 20.87s**; deterministic demo/API tests run without paid provider credentials |
| `curl --fail --silent --show-error http://127.0.0.1:8020/health` | Returned `{"status":"ok","service":"open-agent-studio-api"}` |
| Custom credential-pattern scan | `matches: []`; heuristic only, excludes `.venv`, `.git`, build, browser artifacts and caches |
| `git check-ignore -v` on sample `.data/`, `.playwright-cli/`, and `build/` paths | All ignored as configured |

Combined final check command, exit 0:

```text
unset OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY; .venv/Scripts/python -m ruff check app tests && .venv/Scripts/python -m ruff format --check app tests && .venv/Scripts/python -m mypy app && .venv/Scripts/python -m pytest -q && .venv/Scripts/python -m compileall -q app tests && node --check app/static/studio.js && git diff --check
```

It exited 0; pytest reported **40 passed in 20.87s**.

## Browser smoke test

Playwright CLI Chromium previously exercised initial account creation, workflow save/execute, persisted run retrieval after reload, and logout against loopback `http://127.0.0.1:8020`. Request log showed registration 201, save 201, execute 200, workflow/run reads 200, and logout 200. This was exploratory browser interaction, **not** a committed test suite with assertions. The current agents markup, JavaScript, and stylesheet were fetched successfully from a fresh loopback Uvicorn instance; owner sign-in and agent interactions were not completed in that browser session (no test password was entered). There is no maintained Playwright E2E test file.

## Failed check corrected

An earlier Ruff run failed with eight E501 line-length findings. Formatting and targeted code edits resolved these. Final lint and formatter checks listed above passed.

## Not run / limitations

- No automated Playwright E2E spec; no hosted CI run.
- No real AI-provider call, tool integration, approval/retry/cancellation flow, deployment, load/fuzz test, dependency advisory scan, or penetration test.
- Pytest includes ASGI API integration tests; there is no separate configured integration-test command.
- Wheel built and contents inspected; isolated installation and launch from wheel not tested.
- The demo is deterministic and needs no paid AI credential; no real provider exists to verify.

**Release status:** Local prototype tests/lint/type-check/syntax/package checks passed at this checkpoint, but PRD MVP acceptance criteria are not met. See current review summary at the top of `IMPLEMENTATION_REPORT.md` and `SECURITY_AUDIT.md`.

> Historical test notes below are superseded by the current checkpoint above.

**Run:** local prototype verification, Windows 11, Python 3.14.7.

## Executed

- `python -m pip install -e '.[dev]'` using the repository `.venv` — completed successfully; editable wheel built and installed.
- `.venv/Scripts/python -m pytest -q` — **14 passed**.
- `node --check app/static/studio.js` — passed (exit code 0).
- `git diff --check` — passed for tracked changes (exit code 0).
- Live Uvicorn smoke test bound to `127.0.0.1:8000`; `GET /health` returned HTTP 200 with `{"status":"ok","service":"open-agent-studio-api"}`; `GET /` returned HTTP 200 and studio HTML; POST workflow returned `status: succeeded`, final output `21`, node values `7`, `21`, `21`.
- API tests cover workflow graph acceptance, cycle and unknown type rejection, deterministic results, non-finite and oversized numeric inputs, health/static routes, API validation/execution, unsupported node rejection, and 64 KiB body cap for declared-length and chunked requests.

## Not run / blocked

- Browser E2E and visual inspection: browser tool refused because the user's Edge profile was locked. The user's browser was not closed to preserve unsaved tabs.
- GitHub Actions workflow: added, not executed remotely.
- Node/Next.js build: Next.js scaffold installation returned npm `EALLOWSCRIPTS` under the host's configured `allow-scripts` policy. The policy was not bypassed; the partial scaffold was removed.
- Database migrations, production build/deployment, live AI provider calls, security scanner/advisory audit, fuzzing, load tests, penetration tests: not applicable or not configured.

## Caveats

Tests verify backend behavior and that static content is served, but they do not execute the browser JavaScript or prove responsive rendering. The app remains an unauthenticated local prototype; tests are not a production security assessment.
