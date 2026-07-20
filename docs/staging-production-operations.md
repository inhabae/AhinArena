# Staging and production operations guide

This is the operator runbook for deploying and operating AhinArena. Follow it
for both environments; replace `staging` with `production` where indicated.
It assumes the checked-in Compose deployment in `deploy/compose.production.yaml`.

## 1. Environment model and prerequisites

Use separate cloud accounts/projects, hosts, PostgreSQL volumes, DNS names,
secret sets, and backup locations for staging and production. A staging host
must never use production credentials or production database data. Do not run
the unmodified stacks together on one host: the Compose file deliberately uses
the fixed `ahinarena-postgres-data` volume name. Use separate hosts, which is
the supported topology.

Recommended names are `staging.arena.example.com` and `arena.example.com`.
The browser application calls `/api` on its own origin, so publish the static
frontend and proxy `/api/` to the API service at the same HTTPS hostname.

Each environment needs:

- A patched Linux Docker Engine host with Compose v2, at least 2 vCPU, 4 GB
  RAM, and 30 GB durable disk for the baseline API, worker, and PostgreSQL
  stack. Increase PostgreSQL disk and backup capacity from observed database
  growth; keep at least 30% free disk space.
- A separate sandbox-runner host/node for the worker whenever possible. The
  supplied Compose file is a baseline and co-locates its worker with the
  application services; do not treat that as a sufficient internet-facing
  isolation boundary. The worker's Docker socket access is effectively
  host-root access, so a hardened production design puts it away from the
  public proxy and PostgreSQL. Give a runner 2 vCPU and 4 GB RAM at minimum,
  then size it from peak concurrent matches and their configured 128 MB/0.5
  CPU sandbox limits.
- A reverse proxy/load balancer on `ahinarena-ingress`, public DNS, and a
  certificate issuer. The proxy alone binds TCP 80 and 443. PostgreSQL, the
  API's port 8000, Docker's socket, and runner administration ports must not
  be publicly reachable.
- A central JSON-log collector, alerting destination, encrypted off-host
  backup storage, and a secret manager. Require MFA for production operator,
  DNS, certificate, secret, registry, and backup-recovery access.

The baseline Compose limits are PostgreSQL 1 CPU/1 GB, API 1 CPU/512 MB, and
worker 1 CPU/512 MB. They are safe starting limits, not a capacity guarantee.
Monitor queue age, database disk/CPU, API p95 latency, and runner utilization;
scale or separate services before any sustained alert condition.

### DNS, TLS, and network policy

1. Create an A/AAAA or load-balancer record for each environment hostname.
   Lower its TTL before a planned DNS cutover, then restore the normal TTL
   after stability is established.
2. Configure the proxy to redirect HTTP to HTTPS, obtain and renew a trusted
   certificate, and serve the frontend. Route `/api/` to `http://api:8000/`
   on `ahinarena-ingress`, preserving `Host`, `X-Forwarded-For`, and
   `X-Forwarded-Proto: https`.
3. Create the ingress network once on each host:

   ```sh
   docker network create ahinarena-ingress
   ```

4. Permit internet ingress only to 80/443 at the proxy. Permit proxy-to-API
   traffic only on the Docker ingress network. Keep the Compose `database`
   network internal. Allow runner-to-database traffic only when runners are
   separated, and deny runner/bot egress except required PostgreSQL, approved
   registry/proxy, DNS/NTP, and management paths. Block cloud metadata
   addresses including `169.254.169.254`.
5. Set `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` to the one exact HTTPS
   hostname for that environment; do not use wildcards, paths, HTTP origins,
   or production origins in staging.

The API runs with proxy-header support. A proxy that does not set
`X-Forwarded-Proto: https` breaks secure-cookie behavior.

## 2. Release inputs and secrets

Before deployment, build and test API, worker, and bot-runner images from one
commit. Scan the exact images, produce SBOMs, and record their immutable
`@sha256:` digests. Never deploy `latest` or another mutable tag. Run the
production-style integration test on a non-production host:

```sh
bash scripts/smoke_production_stack.sh
```

Create `/secure/path/ahinarena.staging.env` and
`/secure/path/ahinarena.production.env` outside the repository, mode 600,
using `deploy/production.env.example` as the field list. Inject its values
from the environment's secret manager; do not put secrets in images, Git,
shell history, tickets, or CI output.

Required values are:

| Purpose | Values |
| --- | --- |
| Images | `API_IMAGE`, `WORKER_IMAGE`, `BOT_SANDBOX_IMAGE`, each pinned by digest |
| Database | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` (host must be `postgres`; URL-encode password characters) |
| Browser and email | `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `RESEND_API_KEY`, `EMAIL_FROM` |
| Worker sandbox | `BOT_SANDBOX_HOST_DIR`, `DOCKER_SOCKET_GID`, optional resource/poll limits and `DOCKER_BINARY` |
| Networking | `INGRESS_NETWORK=ahinarena-ingress` |

The API/worker images set `DEPLOY_ENVIRONMENT=production` and
`REQUIRE_SECURE_COOKIES=true`. Do not override them. Create the sandbox directory
once per environment, using the worker image's UID/GID 10001:

```sh
install -d -o 10001 -g 10001 -m 700 /var/lib/ahinarena/bot-sandbox
DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
```

Give the API only database/email configuration. Give the worker only its
database configuration and sandbox-related access; use a dedicated,
least-privilege database role for a remote runner where the architecture
allows it. Never mount the Docker socket into API, migration, or PostgreSQL.

Rotate a secret by adding the replacement in the secret manager, making the
dependent service accept it, deploying/restarting every affected service, and
verifying health plus a real email delivery or database reconnection. Revoke
the old secret only after that evidence is recorded. For a database password,
change/create the database role first, update `POSTGRES_PASSWORD` and
`DATABASE_URL` together, then restart services.

## 3. Initial deployment sequence

Perform these steps first in staging, then promote the *same recorded image
digests* to production after the checklist in section 5.

1. Confirm host, network, DNS/TLS, proxy, secret file, sandbox directory, and
   backup schedule are ready. Validate interpolation without printing secrets:

   ```sh
   ENV_FILE=/secure/path/ahinarena.staging.env
   docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml config --quiet
   ```

2. On production, create and verify an encrypted backup before the first
   migration or any schema-changing release. Configure the daily backup job
   described in section 8 before accepting user data.
3. Pull the recorded images and run the one supported migration/deployment
   path. It starts PostgreSQL, waits for health, runs Alembic once, then starts
   API and worker only if migration succeeds:

   ```sh
   docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml pull
   make production-up PRODUCTION_ENV_FILE="$ENV_FILE"
   docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml ps
   ```

   Do not run Alembic from API/worker replicas or application startup. Do not
   use `docker compose down -v`; it deletes the named database volume.
4. Deploy the reviewed static frontend build to the proxy's document root or
   approved static host. Confirm its origin equals `FRONTEND_URL` and its
   `/api` proxy uses the same origin.
5. Execute the verification procedure below before announcing the environment.

If migration fails, API and worker must remain stopped. Capture migration logs,
repair with a reviewed forward migration or restore a verified backup, then
rerun the explicit migration step. Never force the application rollout past a
failed migration.

## 4. Reproducible deployment verification

Run from a trusted operator machine after every deployment. Replace the base
URL and keep the release record with the output, image digests, source commit,
timestamp, migration result, and operator.

```sh
BASE_URL=https://staging.arena.example.com
curl --fail --show-error "$BASE_URL/api/health/live"
curl --fail --show-error "$BASE_URL/api/health/ready"
curl --fail --show-error -I "$BASE_URL/"
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml logs --tail=200 migrate api worker
```

Confirm the certificate covers the hostname, HTTP redirects to HTTPS, no API
or database port is externally reachable, `ps` shows API healthy, and the
migration exited successfully. Then use dedicated disposable test accounts to:

1. Register, verify email, log in, and confirm the session cookie is `Secure`,
   `HttpOnly`, and sent only over HTTPS.
2. Upload two known-good static Linux ARM64 bot executables and request a
   match.
3. Verify the job moves from queued to completed, a match ID and replay are
   visible, and no unexpected sandbox errors occur.
4. Restart API and worker, then repeat readiness and confirm the match,
   account, and job data persist.

For a release-candidate proof, use the automated equivalent in
`docs/deployment-smoke-test.md` before staging. It validates migrations,
authentication, bot upload, worker execution, and persistence against a fresh
disposable stack.

## 5. Staging-to-production promotion checklist

All boxes must be true; record the evidence in the release record.

- [ ] Source commit is reviewed; API, worker, and runner image digests are
  immutable, scanned, and accompanied by SBOMs.
- [ ] `bash scripts/smoke_production_stack.sh` passed for the candidate.
- [ ] Candidate ran in staging with the exact production-bound digests.
- [ ] Staging migration completed and all section 4 checks passed, including a
  real queued match, persistence after restart, TLS, and email verification.
- [ ] Production secrets, CORS/frontend origin, DNS/TLS, proxy, firewall, and
  runner isolation were reviewed; staging secrets/data are not reused.
- [ ] A current encrypted production backup has verified checksum and the last
  restore drill is within the quarter; rollback compatibility is documented.
- [ ] The release's migrations follow expand-migrate-contract and are backward
  compatible with the previous application version, or an approved restore
  plan and maintenance window exist.
- [ ] Monitoring dashboards/alerts are live, on-call ownership is named, and
  a change window/stakeholder communication plan is recorded.
- [ ] The operator has recorded prior API/worker/runner image digests and the
  exact production environment-file revision/reference for rollback.

Promote by changing only the production secret/config image-digest references,
then perform section 3 and section 4 against `https://arena.example.com`.
Do not rebuild the images between staging approval and production.

## 6. Upgrades, migrations, and rollback

For every schema change use **expand, migrate, contract**: first add a
backward-compatible shape; backfill in bounded observable batches while both
versions work; remove old reads/writes only in a later release after the
rollback window. Test upgrade from a clean database and from a representative
recent backup before production.

For an ordinary release, update the three image digest values in the
environment's secret/config reference, take a production backup if the release
has migrations, then run:

```sh
ENV_FILE=/secure/path/ahinarena.production.env
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml pull
make production-up PRODUCTION_ENV_FILE="$ENV_FILE"
```

Verify as in section 4 and observe the API, queue, and worker for the defined
change window. The worker has no HTTP health endpoint: use its heartbeat,
restart count, logs, queue depth, and age of the oldest queued job.

To roll back an application-only, backward-compatible release, restore the
previous known-good environment file (or its image-digest values) and run:

```sh
PREVIOUS_ENV_FILE=/secure/path/ahinarena.production.previous.env
docker compose --env-file "$PREVIOUS_ENV_FILE" -f deploy/compose.production.yaml \
  up -d --no-deps api worker
```

Do not downgrade Alembic casually. If the schema is destructive or incompatible,
put the proxy in maintenance mode, stop writers, and restore the database to a
verified backup compatible with the previous application before rolling it
back. Prefer a clean replacement environment and DNS/proxy cutover to an
in-place restore.

## 7. Monitoring and incident response

Ship JSON stdout from API and worker to centralized logging. Preserve
`X-Request-ID` for API correlation and `job_id` for match correlation. Redact
cookies, authorization headers, tokens, API keys, database URLs, bot source,
executables, commands, email addresses, and query strings before indexing.

Dashboard at least: API requests/4xx/5xx and p50/p95/p99 duration; queue depth
and oldest queued-job age; job claims/completions/retries/failures; match
duration/failure reasons; worker restarts and time since heartbeat; PostgreSQL
availability, disk, connections, CPU, and backup freshness. Retain raw
high-volume logs 30 days and aggregate metrics at least 13 months.

Alert on API 5xx above 2% for 10 minutes, API p95 over objective for 15
minutes, API readiness failure/unhealthy state for 2 minutes, no worker
heartbeat for two intervals plus five minutes, queue age above five minutes
for 10 minutes, stalled-max-attempt jobs, sustained match failures above 5%,
failed backups, and low database/backup storage.

For an incident: acknowledge and appoint an incident commander; record start
time, scope, request/job IDs, release digest, and changes; mitigate (maintenance
mode, rollback, scale, or isolate) before deep diagnosis; preserve relevant
logs/evidence; communicate status; validate recovery with section 4; then
document root cause and corrective actions.

Treat a possible bot escape, Docker daemon access, unexpected runner egress,
or runner security alert as a host compromise. Stop assigning jobs to that
runner, isolate it at the firewall, preserve daemon/system/audit/worker logs
and artifact hashes, rotate every reachable credential, rebuild it from a
known-good OS/image, validate firewall/metadata blocking/daemon policy, and
review jobs in the exposure window. Do not execute suspect bot artifacts on an
analyst workstation.

## 8. Backup, restore, and recovery

Baseline targets are RPO 24 hours and RTO 4 hours. Run a monitored daily 02:30
UTC job from a hardened operations host, not an application or worker
container. It must create a PostgreSQL custom-format dump, encrypt it before
it reaches disk/storage, upload it plus a SHA-256 checksum to a separate
account and region, and alert when no successful backup exists within 26 hours.
Keep 35 daily, 12 weekly, and 12 monthly backups with immutable/object-lock
protection for at least 35 days where available.

The detailed commands and access controls are in
`docs/postgresql-backup-recovery.md`; use them exactly for backup and restore.
Before any restore, declare the recovery, identify the backup/image versions,
verify checksum, decrypt only through the approved recovery path, and inspect
the archive with `pg_restore --list`. Do not start API or worker against a
partially restored database.

For a disaster or suspected host compromise, build a clean isolated replacement
environment, restore the verified archive, run reviewed forward-compatible
migrations, validate readiness/data/login/read-only lookup/a controlled match,
rotate credentials, and only then cut proxy/DNS traffic. For an approved
in-place restore, enable maintenance mode, stop API and worker writers, take a
final forensic backup, restore with `--clean --if-exists`, redeploy through
`make production-up`, and complete section 4 before lifting maintenance.

Run and record a full isolated restore drill on the first Wednesday of January,
April, July, and October, and after material changes to PostgreSQL, backup
tooling/keys, Compose topology, or migration strategy. Measure actual RPO/RTO,
record checksum and validation evidence, and remediate gaps.

## 9. Useful operational commands

```sh
# Status and live logs
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml ps
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml logs -f migrate api worker

# Restart long-running application components after diagnosing a transient issue
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml restart api worker

# Stop writers for an approved maintenance/recovery operation
docker compose --env-file "$ENV_FILE" -f deploy/compose.production.yaml stop api worker
```

Never use these commands as routine operations: `docker compose down -v`, an
unreviewed `alembic downgrade`, a direct public API port mapping, a public
Docker daemon, or a mutable image tag.
