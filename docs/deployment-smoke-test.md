# Production-style deployment smoke test

Run the disposable smoke test after a production-image change, migration
change, worker/sandbox change, or deployment tooling change. It is designed to
verify the deployable stack, not mocked application components.

```sh
bash scripts/smoke_production_stack.sh
```

The script builds the API, worker, and distroless bot-runner images; starts a
fresh Compose project with a uniquely named PostgreSQL volume; runs the
one-shot Alembic migration service; and starts API and worker. A client
container on the Compose ingress network then verifies readiness, registration,
email-token verification, login, two static bot uploads, queueing, worker
execution, and match completion. It restarts API and worker, checks readiness
again, and confirms the persisted `matches` row remains in PostgreSQL.

The disposable client reaches the API directly over internal HTTP, so the
smoke overlay disables secure cookies only for that stack. The production
Compose file still requires HTTPS and secure cookies behind the reverse proxy.

The script creates no host ports and removes its project, volume, temporary
credentials, ingress network, and bot artifacts on exit. Set
`KEEP_SMOKE_STACK=1` only while investigating a failure; the script prints the
project and temporary environment-file location in that case. Its generated
credentials are smoke-only and must never be reused.

## Prerequisites and expected result

Docker Engine/Desktop must be running and able to build images, run Linux
containers, and allow the disposable worker to access the local Docker socket.
The test needs image-registry access for the pinned bases plus `alpine:3.20`
and `python:3.12-slim`. Run it from the repository root on a non-production
host; its temporary Docker socket use has the same privileged-host risk as a
real worker.

A successful run ends with:

```text
Production-style smoke test passed: project=ahinarena-smoke-... persisted_matches=1
```

On failure, retain the stack with `KEEP_SMOKE_STACK=1`, collect `docker compose
... logs postgres migrate api worker`, and inspect the job status before
destroying it. Record the source commit, image IDs/digests, migration result,
test output, and any remediation in the deployment record.

## Manual checklist

Use this checklist when an automated run is unavailable:

1. Start a new, empty PostgreSQL volume and run `migrate` to successful exit.
2. Start API and worker, then verify `GET /health/ready` returns 200.
3. Register and verify a new test user, then log in with the issued session.
4. Upload two valid static Linux ARM64 bots, enqueue a match, and verify the
   job reaches `completed` with a `match_id`.
5. Restart API and worker; verify readiness, logged-in data/job lookup, and
   the match record still exist.
6. Save service logs, image digests, migration revision, and result; remove
   the disposable environment after review.
