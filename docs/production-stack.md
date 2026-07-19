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
make production-up PRODUCTION_ENV_FILE=/secure/path/ahinarena.production.env
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml ps
```

`make production-migrate` is the explicit, single-run deployment step. It
waits for PostgreSQL, runs the one-shot `migrate` service, and returns that
service's exit status. `make production-up` runs that step before starting or
replacing API/worker containers. Its final application command uses
`--no-deps` intentionally: otherwise Compose restarts an exited migration
dependency and runs it a second time. The API and worker never run Alembic;
the documented target is the only production migration path, so scaling either
service cannot independently migrate the schema. A failed migration prevents
application rollout.

PostgreSQL data lives in the named `ahinarena-postgres-data` volume, which
survives service and host restarts. Never run `docker compose down -v` against
production unless intentionally deleting all database data.

## Schema workflow

For every schema change, use **expand, migrate, contract**:

1. **Expand:** add backward-compatible tables, columns, indexes, or nullable
   fields in one migration; deploy code that can read both old and new shapes.
2. **Migrate:** backfill data in bounded, observable batches. Keep old and new
   code compatible while all API and worker replicas roll forward.
3. **Contract:** only in a later release, after verification and rollback
   windows have elapsed, remove the old reads/writes and then drop old schema.

Create and review revisions locally, and test a clean database upgrade before
release:

```sh
# Local development database only.
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/alembic current
```

On a new production volume, `make production-migrate` applies every revision
to `head`; the one-shot service's successful exit is the clean-database proof
point. Take a verified backup before production migrations. Do not use an API
or worker replica, an application startup hook, or `alembic upgrade` from a
running application container to apply production migrations.

Useful operations:

```sh
# View service logs and migration output.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml logs -f migrate api worker

# Restart a failed long-running service; its restart policy also handles host reboot.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml restart api worker

# Apply a new immutable image release. The migration runs exactly once first.
docker compose --env-file /secure/path/ahinarena.production.env -f deploy/compose.production.yaml pull
make production-up PRODUCTION_ENV_FILE=/secure/path/ahinarena.production.env

# Roll back only a backward-compatible application release.
docker compose --env-file /secure/path/ahinarena.production.previous.env -f deploy/compose.production.yaml up -d --no-deps api worker
```

Only roll back after confirming the schema is backward-compatible. For a
destructive or non-reversible migration, restore the database from a verified
backup before deploying the previous application image. If an upgrade fails,
leave API/worker stopped, capture migration logs, repair or restore the
database, and rerun the explicit migration step; never force an application
rollout past a failed migration.

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
