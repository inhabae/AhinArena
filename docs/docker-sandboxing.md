# Docker Sandboxing

Milestone 9 runs submitted Python bots inside isolated Docker containers instead
of executing uploaded source directly on the API host.

## Scope

Docker sandboxing covers:

- building a dedicated bot runner image from `docker/bot_runner/Dockerfile`;
- writing each active bot submission to a private temporary source file;
- mounting submitted source read-only at `/bot/source.py`;
- running each bot as a separate named container;
- disabling container networking;
- dropping Linux capabilities and blocking privilege escalation;
- applying read-only filesystem, memory, CPU, PID, and `/tmp` limits;
- cleaning up containers and temporary source files after match execution.

The sandbox is an execution boundary for untrusted bot code. It does not add
asynchronous scheduling, live match streaming, multi-language runtimes, or a
submission history UI.

## Runner Image

Build the default runner image from the repository root:

```sh
docker build -t ahinarena-bot-runner:latest -f docker/bot_runner/Dockerfile .
```

The image is based on `python:3.12-slim`. It copies the shared `engine/` package
into `/app/engine`, sets `PYTHONPATH=/app`, and runs submitted source through:

```text
python /bot/source.py
```

The container process runs as the non-root `sandbox` user with UID/GID `10001`.
The `/app` and `/bot` directories are owned by root and made non-writable before
switching users.

## Match Execution Flow

`POST /matches` resolves the two requested bots and requires both to have an
active submission. Missing active source is rejected with `bot_has_no_submission`.

For each bot, `api.bot_sandbox.build_bot_sandbox`:

1. creates a private temporary directory;
2. writes the active submission source to `source.py`;
3. changes the source file mode to read-only;
4. creates a unique container name in the form `ahinarena-bot-{id}-{token}`;
5. returns the `docker run` command used by the existing referee protocol.

The game runner still communicates with bots as persistent subprocesses. It
sends line-delimited JSON states on `stdin` and expects line-delimited JSON
moves on `stdout`. Timeouts, crashes, invalid JSON, and illegal moves are still
handled by the referee as bot failures.

## Container Restrictions

The generated command uses these default restrictions:

```text
docker run --rm -i --init \
  --network none \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --memory 128m \
  --cpus 0.5 \
  --pids-limit 64 \
  --name ahinarena-bot-{id}-{token} \
  --mount type=bind,src={temp_source},dst=/bot/source.py,readonly \
  ahinarena-bot-runner:latest
```

These flags provide the current sandbox boundary:

- `--network none` prevents network access from bot code.
- `--cap-drop ALL` removes Linux capabilities from the container.
- `--security-opt no-new-privileges` prevents gaining extra privileges.
- `--read-only` makes the container root filesystem immutable.
- `--tmpfs /tmp:...` provides a small writable temporary filesystem with
  execution and device files disabled.
- `--memory`, `--cpus`, and `--pids-limit` constrain resource usage.
- The submitted source is bind-mounted read-only and is not copied into the
  image.

## Configuration

The sandbox command can be adjusted with environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCKER_BINARY` | `docker` | Container CLI executable. Tests also cover alternate values such as `podman`. |
| `BOT_SANDBOX_IMAGE` | `ahinarena-bot-runner:latest` | Runner image used for submitted bots. |
| `BOT_SANDBOX_MEMORY_LIMIT` | `128m` | Docker memory limit. |
| `BOT_SANDBOX_CPU_LIMIT` | `0.5` | Docker CPU quota. |
| `BOT_SANDBOX_PIDS_LIMIT` | `64` | Maximum process count inside the container. |
| `BOT_SANDBOX_TMPFS_SIZE` | `16m` | Size of the writable `/tmp` tmpfs. |
| `BOT_MOVE_TIMEOUT_SECONDS` | `2.0` | Per-move response timeout after a bot has started. |
| `BOT_STARTUP_TIMEOUT_SECONDS` | `10.0` | First-response timeout that includes container startup and Python imports. |

Empty environment variable values are ignored and fall back to the defaults.

## Cleanup

After match execution, the API calls `BotSandbox.cleanup()` for each started
sandbox. Cleanup force-removes the named container with:

```sh
docker rm --force <container_name>
```

It then deletes the temporary source directory. Cleanup is attempted in a
`finally` block so it runs even when the match fails, and Docker removal errors
are ignored so temporary files can still be removed.

## Limitations

- Only Python submissions are supported.
- Docker or a compatible `DOCKER_BINARY` must be available where the API runs.
- The sandbox limits reduce risk but are not a complete defense for every
  container escape or host misconfiguration scenario.
- Matches still run synchronously inside the API request cycle. Queue-backed
  workers are planned for Milestone 10.
