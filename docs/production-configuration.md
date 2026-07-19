# Production configuration and secrets

Start with `.env.production.example`, but do not copy real secrets into the
repository, a container image, Compose file, or CI log. The API and worker
fail at startup with clear errors when `DEPLOY_ENVIRONMENT=production` and
required configuration is absent or unsafe.

## Variables

Required API values are `DATABASE_URL` (PostgreSQL scheme),
`CORS_ALLOWED_ORIGINS` (one or more explicit HTTPS origins), `FRONTEND_URL`
(HTTPS origin), `REQUIRE_SECURE_COOKIES=true`, `RESEND_API_KEY`, and
`EMAIL_FROM`. Email is required because account verification and password
recovery are production features.

Workers additionally require `BOT_SANDBOX_IMAGE` pinned with `@sha256:`,
`DOCKER_BINARY`, and sandbox memory, CPU, PID, and tmpfs limits. Optional
tuning values and their defaults are listed in the template. `API_IMAGE`,
`WORKER_IMAGE`, PostgreSQL credentials, `DOCKER_SOCKET_GID`, and
`INGRESS_NETWORK` are Compose inputs; see `docs/production-stack.md`.

Wildcards or paths in CORS origins, insecure frontend URLs, non-PostgreSQL
database URLs, disabled secure cookies, and mutable sandbox tags are rejected
in production.

## Secret manager and rotation

Use your platform's secret manager (for example cloud Secret Manager, Vault,
or Docker Swarm secrets) to inject `DATABASE_URL`, `POSTGRES_PASSWORD`, and
`RESEND_API_KEY` at runtime. Give each service only the secrets it needs;
restrict secret reads to the deployment identity, audit access, and never log
environment variables.

Rotate by creating the new value in the secret manager, updating the database
or email provider to accept it, deploying services with the new secret, and
verifying health and email delivery. Revoke the old value only after every
service has restarted successfully. For database passwords, alter/create the
database role first, update `DATABASE_URL` and `POSTGRES_PASSWORD` together,
roll services, then verify a fresh connection. Keep a tested backup and
rollback plan before destructive database changes.
