# Queue and Workers

Milestone 10 moved match execution out of the `POST /matches` request cycle.
The API now validates a match request, stores a PostgreSQL-backed job, and
returns a status URL. One or more worker processes claim those jobs and run the
Docker-sandboxed match execution path in the background.

## Data Model

Match jobs are stored in the `match_jobs` table and mapped by
`api.models.match_job.MatchJob`.

| Column | Purpose |
| --- | --- |
| `id` | Primary key and public `job_id`. |
| `game_id` | Requested game, such as `tictactoe` or `connect-four`. |
| `bot_one_id`, `bot_two_id` | Foreign keys to the two `bots` rows selected for the match. |
| `status` | Job state. The allowed values are `queued`, `running`, `completed`, and `failed`. |
| `match_id` | Nullable foreign key to the persisted `matches` row after successful execution. |
| `attempts` | Number of times a worker has claimed the job. Used by stalled-job recovery. |
| `error_message` | Failure text for failed jobs, or `NULL` for queued/running/completed jobs. |
| `created_at` | Server timestamp for enqueue time. |
| `started_at` | Timestamp set when a worker claims the job. |
| `completed_at` | Timestamp set when a job completes or fails. |

The table has a status check constraint:

```sql
status in ('queued', 'running', 'completed', 'failed')
```

## Job Lifecycle

1. A client calls `POST /matches` with two bot names and a supported game.
2. The API validates the game, resolves both bots, requires each bot to have an
   active submission, rejects self-play with the same bot row, and inserts a
   `match_jobs` row with `status = 'queued'`.
3. On PostgreSQL, the API sends `NOTIFY match_jobs_channel` after the job is
   committed.
4. The API returns `202 Accepted`, a `job_id`, and a `Location` header pointing
   to `/match-jobs/{job_id}`.
5. A worker claims the oldest queued job, marks it `running`, increments
   `attempts`, sets `started_at`, and clears any previous error.
6. The worker runs the shared match executor. That executor starts each bot's
   active submission in the Docker sandbox, records ordered moves, persists the
   match result, and applies Elo updates.
7. On success, the worker stores the new `match_id`, marks the job
   `completed`, sets `completed_at`, and clears `error_message`.
8. On an execution error, the worker marks the job `failed`, sets
   `completed_at`, and stores the exception text in `error_message`.

## Worker Process

Workers run through the module entry point:

```sh
PYTHONPATH=. .venv/bin/python -m worker.main
```

The Makefile wraps this as:

```sh
make worker
```

Each worker loops forever:

1. Run stalled-job recovery when the poll interval has elapsed.
2. Try to claim one queued job.
3. If a job was claimed, execute it immediately.
4. If no job was available, wait for a PostgreSQL notification or the polling
   timeout before trying again.

On PostgreSQL, claims use row-level locking so multiple workers can run safely:

```sql
SELECT id
FROM match_jobs
WHERE status = 'queued'
ORDER BY created_at, id
LIMIT 1
FOR UPDATE SKIP LOCKED
```

`SKIP LOCKED` lets concurrent workers skip rows already being claimed by another
worker. Jobs are ordered by `created_at, id`, so workers generally process the
oldest queued request first.

The worker falls back to a simpler query path for non-PostgreSQL test databases,
but production queueing is designed around PostgreSQL.

## LISTEN/NOTIFY and Polling

The notification channel is `match_jobs_channel`.

When the API creates a job and the active SQLAlchemy dialect is PostgreSQL, it
runs:

```sql
NOTIFY match_jobs_channel
```

Workers try to open a separate psycopg connection and run:

```sql
LISTEN match_jobs_channel
```

When a notification arrives, a sleeping worker wakes up and tries to claim work.
Notifications are only a wakeup optimization; they are not the durable queue.
The durable state is the `match_jobs` table.

Workers also poll on a fixed interval. Polling covers missed notifications,
worker restarts, local test databases, and any failure to create a PostgreSQL
listener. If `LISTEN` setup fails, the worker automatically uses polling only.

## Stalled-Job Recovery

A worker can stop after marking a job `running` but before completing it. The
reaper handles that case by scanning for old running jobs:

```sql
SELECT id
FROM match_jobs
WHERE status = 'running'
  AND started_at IS NOT NULL
  AND started_at < :cutoff
ORDER BY started_at, id
FOR UPDATE SKIP LOCKED
```

The cutoff is `now - MATCH_JOB_STALL_TIMEOUT_SECONDS`.

For each stalled job:

- If `attempts < MATCH_JOB_MAX_ATTEMPTS`, the job is returned to `queued`,
  `started_at` is cleared, and a worker can retry it.
- If `attempts >= MATCH_JOB_MAX_ATTEMPTS`, the job is marked `failed`,
  `completed_at` is set, and `error_message` becomes
  `Match job stalled after maximum attempts.`

The reaper runs inside the worker loop, so every active worker can help recover
stalled jobs. Row locks and `SKIP LOCKED` prevent workers from reaping the same
job at the same time.

## API

### `POST /matches`

Creates a queued match job. The request requires an authenticated
`ahin_arena_session` cookie.

```http
POST /matches
```

```json
{
  "game": "connect-four",
  "players": [
    {"bot": "bot-one"},
    {"bot": "bot-two"}
  ]
}
```

Successful responses return `202 Accepted`:

```http
Location: /match-jobs/17
```

```json
{
  "job_id": 17,
  "status": "queued"
}
```

Common validation failures include:

- `400 unsupported_game` when `game` is not supported.
- `400 invalid_player_count` when the request does not contain exactly two
  players.
- `400 duplicate_bot_match` when both players resolve to the same bot row.
- Bot lookup or active-submission errors when a named bot cannot be used for
  the requested game.

### `GET /match-jobs/{job_id}`

Returns compact status for one job.

```http
GET /match-jobs/17
```

Queued or running jobs have no `match_id` yet:

```json
{
  "job_id": 17,
  "status": "running",
  "match_id": null,
  "error_message": null
}
```

Completed jobs include the persisted match ID:

```json
{
  "job_id": 17,
  "status": "completed",
  "match_id": 42,
  "error_message": null
}
```

Failed jobs include an error message:

```json
{
  "job_id": 17,
  "status": "failed",
  "match_id": null,
  "error_message": "Match job stalled after maximum attempts."
}
```

Unknown jobs return `404 match_job_not_found`.

### `GET /match-jobs`

The frontend also uses the list endpoint to show recent queue activity:

```http
GET /match-jobs?game_id=connect-four&status=queued&limit=20&offset=0
```

Filters are optional. `limit` accepts `1` through `100`, `offset` starts at `0`,
and `status` can be any job state.

## Configuration

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | Required | API, worker, migrations | SQLAlchemy database URL. Local development uses `postgresql+psycopg://...`. |
| `CORS_ALLOWED_ORIGINS` | Localhost Vite and port 3000 origins | API | Comma-separated explicit browser origins allowed to send credentialed API requests. |
| `TRUSTED_PROXY_CIDRS` | Empty | API | Comma-separated proxy IPs or CIDRs trusted to supply `X-Forwarded-For` for auth rate limiting. Leave empty unless the deployment proxy is known and configured. |
| `WORKER_POLL_INTERVAL_SECONDS` | `5.0` in code, `1` through `make worker` | Worker | Sleep interval for polling, notification wait timeout, and reaper cadence. |
| `MATCH_JOB_STALL_TIMEOUT_SECONDS` | `30.0` | Worker | Age after which a `running` job is considered stalled. |
| `MATCH_JOB_MAX_ATTEMPTS` | `3` | Worker | Maximum claim attempts before a stalled job is failed instead of requeued. |
| `BOT_MOVE_TIMEOUT_SECONDS` | `2.0` | Worker match execution | Per-move timeout after bot startup. |
| `BOT_STARTUP_TIMEOUT_SECONDS` | `10.0` | Worker match execution | First-response timeout, including container startup and Python imports. |
| `DOCKER_BINARY` | `docker` | Worker match execution | Container CLI used by the bot sandbox. |
| `BOT_SANDBOX_IMAGE` | `ahinarena-bot-runner:latest` | Worker match execution | Docker image used to run submitted bots. |
| `BOT_SANDBOX_MEMORY_LIMIT` | `128m` | Worker match execution | Container memory limit. |
| `BOT_SANDBOX_CPU_LIMIT` | `0.5` | Worker match execution | Container CPU limit. |
| `BOT_SANDBOX_PIDS_LIMIT` | `64` | Worker match execution | Container process limit. |
| `BOT_SANDBOX_TMPFS_SIZE` | `16m` | Worker match execution | Writable `/tmp` tmpfs size inside the container. |

See `docs/docker-sandboxing.md` for the full sandbox command and security
settings.

## Local Development

Create and edit the environment file:

```sh
cp .env.example .env
```

Install dependencies and run migrations:

```sh
.venv/bin/pip install -r requirements.txt
make migrate
```

Build the bot runner image before executing submitted bots:

```sh
docker build -t ahinarena-bot-runner:latest -f docker/bot_runner/Dockerfile .
```

Run the API, worker, and frontend in three terminals:

```sh
make api
```

```sh
make worker
```

```sh
make frontend
```

The API listens on `http://127.0.0.1:8000`. Vite usually serves the frontend on
`http://localhost:5173` and proxies `/api/*` requests to the API.

The local match flow requires all of these pieces:

- PostgreSQL is running and `DATABASE_URL` points at a migrated database.
- The API is running so users can create bots, submit code, and enqueue jobs.
- At least one worker is running so queued jobs become completed matches.
- Docker is available to the worker for sandboxed bot execution.
- The frontend is running if testing through the browser.

If the API is running but no worker is running, `POST /matches` still succeeds,
but jobs remain in `queued` status until a worker starts.
