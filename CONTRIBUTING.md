# Contributing

Thanks for your interest in Open Agent Studio. This is an early prototype; use focused changes and describe what is implemented versus planned.

## Local setup

Follow [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). The current project uses Python/FastAPI and static HTML/CSS/JavaScript. Keep the server loopback-only.

## Changes

- Start with an issue or explain the motivating use case in the change description.
- Preserve the current small architecture unless a concrete need supports a change.
- For behavior changes, add a test first, observe the failure, implement narrowly, and run the full suite.
- Validate user-controlled data on the server. Keep tool capabilities least-privileged and bounded.
- Use safe DOM methods for UI data; do not insert untrusted HTML.
- Update documentation and status reports to match verified behavior.
- Never commit credentials, private data, `.env`, `.venv`, or generated local state.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Production builds, browser E2E, database checks, and security scanners are not yet configured. Do not claim these checks passed unless actually run.

## License

Contributions are accepted under the repository's MIT license.
