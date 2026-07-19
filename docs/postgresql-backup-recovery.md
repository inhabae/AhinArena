# PostgreSQL backup, restore, and disaster recovery

This runbook covers the PostgreSQL service in
`deploy/compose.production.yaml`. It protects application data in the named
`ahinarena-postgres-data` volume; it does not replace the immutable image,
configuration, and secret-management records needed to recreate an entire
environment.

## Objectives, ownership, and assumptions

The baseline objective for the self-managed Compose deployment is **RPO 24
hours** and **RTO 4 hours**: a verified encrypted logical backup is created at
least daily, and a working replacement environment can be restored within four
hours. If the product requires less than 24 hours of data loss, use managed
PostgreSQL backups or configure continuous WAL archiving to a separate account
and test point-in-time recovery; a daily `pg_dump` alone cannot meet that RPO.

The on-call incident commander owns declaring a recovery and stakeholder
updates. The database/platform owner owns backup jobs, encryption keys, and
the restore execution. The application owner validates migrations, API
readiness, and critical user flows after restore. Security owns evidence
preservation, access review, and credential rotation when compromise is
suspected. Record the current names and contact paths in the production
operations system, not this repository.

## Automated backup policy

Run the following backup job every day at 02:30 UTC (or an equivalent
low-traffic, monitored schedule) from a hardened operations host or CI runner
that has access to the Compose host and the backup storage account. Do not run
it from the API or sandbox-worker container.

1. Create a PostgreSQL custom-format logical dump with `pg_dump`.
2. Encrypt it before it leaves the operations host.
3. Upload the encrypted object and its checksum to a separate account/project
   and region from the production host.
4. Alert if no successful backup is recorded by 26 hours, if upload/checksum
   verification fails, or if free backup-storage capacity is low.

Recommended retention is 35 daily backups, 12 weekly backups, and 12 monthly
backups. Apply object-lock/immutability for at least 35 days where policy and
storage support it. Retention must be implemented with lifecycle rules in the
backup store, not by trusting a best-effort cleanup job on the production host.
Keep a separate, access-controlled copy of the deployment environment file,
image digests, and encryption-key recovery material; a database dump alone
cannot recreate the service.

### Create an encrypted backup

Set these values in the scheduled job's protected environment. The recipient
is the public key or key-management identity allowed to encrypt; the private
decrypt key belongs only in the approved recovery secret store.

```sh
PRODUCTION_ENV_FILE=/secure/path/ahinarena.production.env
BACKUP_DIR=/secure/backup-staging
BACKUP_TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_FILE="$BACKUP_DIR/ahinarena-postgres-$BACKUP_TIMESTAMP.dump.age"
AGE_RECIPIENT=age1replace-with-the-approved-backup-recipient
mkdir -p "$BACKUP_DIR"

docker compose --env-file "$PRODUCTION_ENV_FILE" -f deploy/compose.production.yaml \
  exec -T postgres pg_dump -U "$(grep '^POSTGRES_USER=' "$PRODUCTION_ENV_FILE" | cut -d= -f2-)" \
  -d "$(grep '^POSTGRES_DB=' "$PRODUCTION_ENV_FILE" | cut -d= -f2-)" \
  --format=custom --no-owner --no-acl \
  | age --recipient "$AGE_RECIPIENT" --output "$BACKUP_FILE"

sha256sum "$BACKUP_FILE" > "$BACKUP_FILE.sha256"
```

The command deliberately streams a custom archive through encryption and never
writes a plaintext dump to disk. A production automation should source
`POSTGRES_USER` and `POSTGRES_DB` from the secret manager rather than parse an
environment file; the extraction above is only a portable Compose example.
Upload both the encrypted archive and checksum through the storage provider's
authenticated CLI or backup agent, then verify the remote object's checksum
and version/immutability status. Restrict the staging directory to the backup
operator and remove it according to the host's approved secure-data policy.

Use an encryption scheme with envelope encryption/KMS or an equivalent
reviewed tool such as `age`. Encryption keys must be separate from the backup
account, require MFA and least-privilege recovery access, and be regularly
tested for recovery. Deny public access to backup buckets, enable audit logs,
and allow the automated writer only `put`/list operations while granting
restore operators time-bound read/decrypt access.

## Pre-restore validation

Before changing any target environment:

1. Declare the recovery and identify the backup timestamp, source image
   digests, target environment, and recovery owner.
2. Download the encrypted archive through the approved recovery path and
   verify it against the stored SHA-256 checksum.
3. Inspect the archive without restoring it:

   ```sh
   age --decrypt --identity /secure/recovery/backup-key.txt "$BACKUP_FILE" \
     | pg_restore --list >/tmp/ahinarena-restore-list.txt
   ```

4. Confirm the archive contains the expected schema and application tables,
   and choose the application image version compatible with that backup. Do
   not start API or worker replicas against a partially restored database.

Only approved recovery operators may access the decrypt key. Do not paste
keys, database URLs, or dump contents into tickets, chat, CI logs, or shell
history.

## Restore to a new environment

Use a separate host/account or a clearly isolated replacement environment.
Create its secret environment file from `deploy/production.env.example`, use
new database and application credentials, and record the immutable API,
worker, and sandbox image digests to be deployed. Do not reuse the compromised
host or its Docker volume after a suspected host compromise.

1. Create the trusted ingress network and start PostgreSQL only. On a new host
   the Compose volume is empty and PostgreSQL creates the target database from
   `POSTGRES_DB` and `POSTGRES_USER`.

   ```sh
   docker network create ahinarena-ingress
   docker compose --env-file /secure/path/ahinarena.recovery.env \
     -f deploy/compose.production.yaml up -d --wait postgres
   ```

2. Restore the verified archive into that empty database. Replace the archive
   and decrypt-key paths with the approved recovery material.

   ```sh
   age --decrypt --identity /secure/recovery/backup-key.txt "$BACKUP_FILE" \
     | docker compose --env-file /secure/path/ahinarena.recovery.env \
       -f deploy/compose.production.yaml exec -T postgres \
       pg_restore -U "$(grep '^POSTGRES_USER=' /secure/path/ahinarena.recovery.env | cut -d= -f2-)" \
       -d "$(grep '^POSTGRES_DB=' /secure/path/ahinarena.recovery.env | cut -d= -f2-)" \
       --clean --if-exists --no-owner --no-acl
   ```

3. Apply any reviewed, forward-compatible schema migrations and start
   application services with the documented target. `production-up` runs the
   one-shot migration exactly once before starting API and worker.

   ```sh
   make production-up PRODUCTION_ENV_FILE=/secure/path/ahinarena.recovery.env
   ```

4. Verify `docker compose ... ps`, `GET /health/ready`, the Alembic revision,
   expected row counts, user login, a read-only match lookup, and one controlled
   match job. Keep public DNS/routing pointed at the old environment until
   these checks pass; then perform the documented cutover.

## Restore an existing environment

An in-place restore is destructive. Prefer the new-environment path and cut
over once validated. Use this path only when the recovery lead explicitly
approves overwriting the existing database.

1. Put the service in maintenance mode at the reverse proxy, stop API and
   worker writers, and take a final encrypted backup of the current state for
   forensics/rollback.

   ```sh
   docker compose --env-file "$PRODUCTION_ENV_FILE" -f deploy/compose.production.yaml \
     stop api worker
   ```

2. Verify the selected archive as described above. Restore it into the
   PostgreSQL service with `--clean --if-exists`; these options remove objects
   not present in the archive, so re-check the target file and database name
   before running the command.

   ```sh
   age --decrypt --identity /secure/recovery/backup-key.txt "$BACKUP_FILE" \
     | docker compose --env-file "$PRODUCTION_ENV_FILE" \
       -f deploy/compose.production.yaml exec -T postgres \
       pg_restore -U "$(grep '^POSTGRES_USER=' "$PRODUCTION_ENV_FILE" | cut -d= -f2-)" \
       -d "$(grep '^POSTGRES_DB=' "$PRODUCTION_ENV_FILE" | cut -d= -f2-)" \
       --clean --if-exists --no-owner --no-acl
   ```

3. Run `make production-up` using the same production environment file; it
   performs the documented one-shot migration before starting API and worker.
   Validate readiness, migration revision, data sanity, and a controlled match
   before lifting maintenance mode.

If the database host, Docker daemon, or credentials may be compromised, do not
perform an in-place restore. Build a clean replacement environment, rotate all
credentials, and follow the sandbox incident procedure.

## Restore drills and review

Schedule a full restore drill for the first Wednesday of January, April, July,
and October, with the database/platform owner as accountable owner and the
application owner as validator. Also run one after any material change to
PostgreSQL version, backup tooling, encryption keys, Compose topology, or
schema migration strategy. Restore a recent encrypted backup into an isolated
environment, run the validation checks above, measure actual RTO/RPO, and
destroy the drill environment afterward. The database/platform owner records
the backup timestamp, checksum result, restore duration, validation evidence,
gaps, and remediation owner. Review backup-job success, retention lifecycle,
key access, and the last drill monthly in the operational review.
