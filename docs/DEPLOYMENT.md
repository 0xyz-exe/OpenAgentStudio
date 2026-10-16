# Deployment status and guidance

**No production deployment is supported.** The current API has no authentication, authorization, persistence, operational limits, observability redaction, or deployment packaging. It is intended only for loopback local development.

## Safe local mode

Run Uvicorn with `--host 127.0.0.1`. Do not bind to `0.0.0.0`, configure reverse proxies/tunnels, or expose `/docs` to untrusted users. The application uses no provider secrets and makes no outbound calls.

## Not yet provided

Docker/Compose, container hardening, TLS/reverse proxy setup, health/readiness distinction, secrets management, migrations, backup/restore, production worker model, CI/CD, scaling, rate/quota controls, monitoring, incident response, or verified cloud deployment.

Before proposing a deployment, implement and test authentication/workspace authorization, request and execution limits, data retention and backup policy, secure secret storage, logging redaction, dependency review, health/readiness and graceful shutdown. Re-run the threat model and deployment-specific security review then.
