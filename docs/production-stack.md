# Production Compose stack

`deploy/compose.production.yaml` runs PostgreSQL, a one-shot Alembic migration,
the API, and the match worker. PostgreSQL and the worker are isolated on the
internal `database` network. Only the API joins `ahinarena-ingress`, so attach
the reverse proxy to that network; the Compose file deliberately publishes no
application or database ports to the host.

## Prerequisites

Use Docker Engine with Compose v2 on a Linux host. The worker needs access to
the Docker socket to create the separately restricted bot containers; this is
equivalent to host-root access. Prefer a dedicated worker host or a narrowly
scoped Docker API proxy.

Create the proxy network once, then create a secret environment file outside
the repository from `deploy/production.env.example`:

```sh
docker network create ahinarena-ingress
install -m 600 /dev/null /secure/path/ahinarena.production.env
# Copy values from deploy/production.env.example into that file.
DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
```

Use immutable image digests in `API_IMAGE`, `WORKER_IMAGE`, and
`BOT_SANDBOX_IMAGE`. `DATABASE_URL` must use `postgres` as its host and must
URL-encode the password if needed.

## Deploy and operate

Validate interpolation and configuration before starting:

```sh
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml config --quiet
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml up -d
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml ps
```

The migration service exits successfully after applying migrations. API and
worker start only after it succeeds; an unsuccessful migration leaves them
stopped. PostgreSQL data lives in the named `ahinarena-postgres-data` volume,
which survives service and host restarts. Never run `docker compose down -v`
against production unless intentionally deleting all database data.

Useful operations:

```sh
# View service logs and migration output.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml logs -f migrate api worker

# Restart a failed long-running service; its restart policy also handles host reboot.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml restart api worker

# Apply a new immutable image release. Migration reruns first.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml pull
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml up -d

# Roll back application images after restoring the previous environment file values.
docker compose --env-file /secure/path/ahinarena.production.previous.env -f deploy/compose.production.yaml up -d
```

Only roll back after confirming the migration is backward-compatible. For a
destructive or non-reversible migration, restore the database from a verified
backup before deploying the previous application image.

## Reverse proxy, TLS, and domains

Terminate TLS in a reverse proxy on `ahinarena-ingress`, and route the public
domain (for example `arena.example.com`) to `http://api:8000`. The proxy is the
only component that should bind public ports `80` and `443`; redirect HTTP to
HTTPS, obtain/renew certificates, and preserve the `Host`, `X-Forwarded-For`,
and `X-Forwarded-Proto` headers. Set `CORS_ALLOWED_ORIGINS` to exact HTTPS
origins (no wildcard), including every intentional browser domain.

The API is started with Uvicorn `--proxy-headers`. Keep it reachable only from
a trusted proxy network; do not publish the API port directly. Ensure the
proxy sends `X-Forwarded-Proto: https`, otherwise secure-cookie and HTTPS URL
behavior can be incorrect. Restrict proxy access to the API's Compose network
and restrict firewall ingress to ports 80/443 only.

## Capacity and health

Each service has Compose CPU/memory limits, and the long-running services use
`unless-stopped`. PostgreSQL health checks gate migration; API health checks
call `GET /health`. The worker has no HTTP listener, so monitor its logs,
container restart count, and queued/running `match_jobs` age rather than using
a synthetic health check that cannot prove job processing is healthy.
