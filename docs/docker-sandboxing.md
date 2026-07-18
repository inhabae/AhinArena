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
