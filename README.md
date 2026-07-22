# AhinArena

AhinArena is a deployed AI competition platform where developers upload static
Linux x86-64 bot executables, run them in automated board-game matches, and
track match history, replays, and Elo rankings.

The current application includes:

- React/Vite frontend for auth, bot registration, profiles, match creation,
  live job tracking, replays, match history, and leaderboards.
- FastAPI backend with PostgreSQL persistence, cookie-backed sessions, email
  verification, password reset, bot submission, match APIs, and rating updates.
- PostgreSQL-backed match queue processed by worker processes.
- Docker-sandboxed bot execution for submitted executables.
- Production Compose deployment assets, Caddy ingress config, smoke tests, and
  operations runbooks.

## Architecture

```text
React/Vite frontend
        |
        | /api
        v
FastAPI backend
        |
        +-- PostgreSQL: users, sessions, bots, submissions, matches, ratings
        |
        +-- match_jobs queue
                 |
                 v
              workers
                 |
                 v
        Docker sandboxed bot executables
```

Supported games are Tic-Tac-Toe and Connect Four. Replay rendering is available
for both games.

## Local Development

Create a virtual environment, install dependencies, and configure local
environment values:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Install frontend dependencies:

```sh
cd frontend
npm install
cd ..
```

Run database migrations:

```sh
make migrate
```

Start the backend, worker, and frontend in separate terminals:

```sh
make api
make worker
make frontend
```

The frontend usually runs at `http://localhost:5173` and proxies `/api/*` to
the backend at `http://127.0.0.1:8000`.

## Bot Submissions

Bots are uploaded as prebuilt static Linux x86-64 ELF executables. The site does
not compile user source code. Authenticated users create a bot for a supported
game and upload one executable as the active submission. New matches run each
bot's active submission inside the Docker sandbox.

Local helper targets can build sample executables from `players/builtin_player.c`:

```sh
make builtin-players
make sleepy-players
```

Generated executables are written under `build/` and are ignored by Git.

## Tests

Run the backend and engine test suite:

```sh
make test
```

Run frontend checks:

```sh
cd frontend
npm run lint
npm run build
```

Run the disposable production-style smoke test after deployment, image, worker,
sandbox, or migration changes:

```sh
bash scripts/smoke_production_stack.sh
```

The smoke test requires Docker and creates disposable local containers only.

## Documentation

- [Architecture](docs/architecture.md) - component map and major flows.
- [Frontend](docs/frontend.md) - route map, page behavior, and API client rules.
- [Bot submissions](docs/bot-submission.md) - executable requirements and
  upload flow.
- [Tic-Tac-Toe protocol](docs/tictactoe-engine-referee.md) and
  [Connect Four protocol](docs/connectfour-engine-referee.md) - bot/referee
  communication.
- [Docker sandboxing](docs/docker-sandboxing.md) - runner image, container
  limits, trust boundaries, and incident handling.
- [Queue and workers](docs/queue-and-workers.md) - match job lifecycle and
  worker operation.
- [Production stack](docs/production-stack.md) - Compose deployment,
  migrations, ingress, and rollback.
- [Production configuration](docs/production-configuration.md) - required
  environment variables and secret handling.
- [Production images](docs/production-images.md) - reproducible image builds,
  tags, scanning, and SBOMs.
- [Deployment smoke test](docs/deployment-smoke-test.md) - automated and manual
  verification steps.
- [Operations](docs/operations.md) - telemetry, dashboards, alerts, logs, and
  retention.
- [PostgreSQL backup and recovery](docs/postgresql-backup-recovery.md) -
  backup, restore, and recovery drills.
- [Staging and production operations](docs/staging-production-operations.md) -
  full operator runbook.

## Repository Layout

```text
api/        FastAPI app, models, auth, ratings, match execution
engine/     Game engines, protocols, and local runners
worker/     Asynchronous match worker
frontend/   React/Vite web application
deploy/     Production Compose, Caddy, and smoke-test overlays
docker/     API, worker, and bot-runner Dockerfiles
scripts/    Local and production smoke utilities
tests/      Backend, worker, referee, and game tests
docs/       Focused architecture, development, and operations docs
players/    Sample bot source used by local helper targets
```

## License

MIT. See [LICENSE](LICENSE).
