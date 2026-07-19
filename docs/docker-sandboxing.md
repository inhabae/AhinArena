# Executable Sandbox

Workers materialize the active database artifact into a private `player` file,
set mode `0555`, and mount it read-only at `/bot/player`. The only launch
command is `/bot/player`; filenames and other upload metadata never influence
execution.

The runner image is `gcr.io/distroless/static-debian12:nonroot`, with no shell,
Python, Node.js, compiler, package manager, or application code. Uploaded
players therefore must be statically linked.

Each player is launched with `--rm -i --init`, `--network none`, all
capabilities dropped, `no-new-privileges`, a read-only root filesystem, and a
non-root UID. `/tmp` is a bounded `noexec,nosuid,nodev` tmpfs. Memory, CPU, PID,
startup, and move limits retain their existing environment-variable controls.
Containers have unique names and cleanup force-removes the container and its
private host temporary directory in a `finally` path.

The sandbox reduces risk but does not replace host hardening, current container
runtimes, or worker isolation. Bot stderr included in failures is restricted to
2 KiB and control characters are sanitized.

## Trust boundary and deployment model

Treat every uploaded bot and the worker process that starts it as untrusted
workload. The Docker socket is **effectively host-root access**: a process that
can use it can generally start a privileged container, mount the host
filesystem, or access other containers. Dropping capabilities inside the bot
container does not reduce the authority of a compromised worker that controls
the Docker daemon.

The API, migration process, and PostgreSQL host must never receive a Docker
socket mount. The production Compose file mounts `/var/run/docker.sock` only
into the worker service; this is a minimum boundary, not a reason to colocate
that worker with the API or database in a higher-risk deployment.

For internet-facing production, use one of these designs in preference order:

1. Run a dedicated sandbox-execution service or runner pool on separate nodes.
   It accepts a narrowly defined job payload and returns a result; it has no
   API ingress, no application secret store, and no access to the API/database
   host filesystem.
2. Run workers on dedicated runner hosts/nodes with no API, reverse proxy, or
   PostgreSQL data volumes. Permit their database connection only to the
   PostgreSQL endpoint and use a dedicated, least-privilege database role.
3. If a shared host is unavoidable, use a narrowly scoped Docker API proxy
   instead of the raw socket, and allow only the create/start/inspect/remove
   operations and runner-image policy the worker needs.

Do not expose the Docker daemon over TCP. Do not grant the worker Docker group
membership on the API or database host. The worker image contains a Docker CLI
only to call the runner host's approved daemon/API; it is not a general-purpose
administration container.

## Runner host and network controls

Apply the following controls to every sandbox runner host or node:

- Keep the host dedicated to sandbox work. Use a minimal, patched OS and
  container runtime, enforce automatic security updates, and restrict SSH and
  management-plane access to operators.
- Keep bot containers on `--network none` (the current default). At the host
  firewall and cloud-network layer, deny runner workload egress except the
  specific PostgreSQL/queue endpoint, DNS/NTP if required, and the approved
  image registry or proxy. Do not rely on a container's lack of a network
  interface as the sole egress control.
- Explicitly block cloud instance-metadata endpoints, including
  `169.254.169.254`, and equivalent provider-local metadata addresses, from
  the worker and bot-container network paths. Do not attach instance profiles,
  cloud credentials, deployment tokens, or registry write credentials to a
  runner host.
- Give the worker only the database credentials and service configuration
  needed to claim/complete jobs. Store them in the host's secret mechanism,
  not images or environment files checked into source control; rotate them
  independently from API credentials.
- Do not mount host paths into bot containers other than the per-match,
  read-only player file. The worker's `BOT_SANDBOX_HOST_DIR` is a dedicated
  host directory bind-mounted at the same absolute path into the worker so the
  Docker daemon can mount each generated player file; it is not mounted into a
  bot except for that single read-only file. Never mount the Docker socket, `/proc`, `/sys`, the
  host root, application source, logs, SSH material, or cloud credential paths.
  Keep temporary bot files on a dedicated filesystem with restrictive
  permissions and remove them after each match.
- Enforce the existing read-only filesystem, non-root user, capability drop,
  `no-new-privileges`, PID/memory/CPU limits, timeouts, and bounded tmpfs. Use
  an additional VM, microVM, or hardened runtime boundary for higher-risk or
  multi-tenant workloads.

## Sandbox-image updates

The runner image is an executable security boundary and must be updated like a
production dependency:

1. Build from the reviewed `docker/bot_runner/Dockerfile` in CI, generate an
   SBOM, scan it, and record its immutable digest.
2. Test the candidate digest with representative valid, invalid, timeout, and
   resource-exhaustion bots on a non-production runner.
3. Update `BOT_SANDBOX_IMAGE` to that digest in the deployment secret/config;
   never use a mutable tag for production execution.
4. Roll out one runner/node first, watch `match_job_failed`, duration, and
   resource-limit events, then roll out the remaining runner pool.
5. Keep the prior approved digest available for rollback. Revoke/replace a
   digest immediately when a runtime, base-image, or supply-chain issue is
   announced, and record the affected runner and job time window.

## Suspected bot-container compromise

Treat a suspected escape, unexpected network attempt, daemon API use, or
security-alerted runner as a host incident:

1. Stop assigning new jobs to the affected runner; disable or drain its worker
   and preserve the job IDs, image digest, container IDs, and relevant logs.
2. Isolate the runner from the network at the firewall/security-group layer.
   Do not restart or destroy it before collecting volatile evidence unless
   continued harm requires immediate shutdown.
3. From a trusted administration path, identify and stop sandbox containers;
   preserve Docker daemon, system, audit, and worker logs plus the submitted
   artifact hashes. Do not execute or download the bot artifact on an analyst
   workstation.
4. Rotate every credential reachable from that runner, including database,
   registry, cloud, and deployment credentials. Assume raw Docker-socket
   access may have exposed all host-visible secrets.
5. Rebuild the runner from a known-good image/OS rather than attempting an
   in-place cleanup. Validate host firewall, metadata blocking, daemon policy,
   image digest, and least-privilege database access before returning it to the
   pool.
6. Review jobs run on that node during the exposure window, notify affected
   owners according to the incident policy, and document root cause and the
   corrective controls before resuming normal scheduling.
