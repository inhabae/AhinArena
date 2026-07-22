# AhinArena Architecture

## Overview

AhinArena is a deployed platform where developers upload AI agents to compete
in automated board game matches.

The system consists of a web frontend, backend services, persistent storage, and isolated game execution through Docker.

---

## High-Level Architecture

```text
        Frontend (React + Vite)
 Auth / Home / Profiles / History / Leaderboard / Replay
                        │
                        │ /api via frontend/src/api/client.js
                        ▼
              Backend API (FastAPI)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   PostgreSQL    Session Storage   Job Queue
                                  (Postgres match_jobs)
                                        │
                                        ▼
                                  Worker Pool
                                        │
                                        ▼
                                  Game Runner
                                        │
                                        ▼
                               Docker Containers
                                        │
                                        ▼
                                  AI Game Engines
```

---

## Components

- **Frontend** — React/Vite web interface in `frontend/`. It uses React Router
  for auth, Home, Bot Registration, Player Profile, Bot Profile, Match History,
  Leaderboard, queued/live match, and Match Detail/Replay pages.
- **Frontend API client** — `frontend/src/api/client.js` centralizes browser
  calls to the Backend API. It prefixes requests with `/api`, serializes query
  params, parses JSON responses, and raises `ApiError` instances for normalized
  backend errors.
- **Backend API** — FastAPI application logic for health checks, registration,
  email verification, password reset, login/logout, current-user lookup,
  profile updates, bot lookup and creation, bot executable submission, match
  job creation, match history, match detail, and leaderboard data.
- **PostgreSQL** — Persistent data for bots, completed matches, ordered moves,
  ratings, records, users, sessions, bot submissions, active bot submission
  pointers, queued match jobs, and per-match rating snapshots.
- **Session Storage** — Server-side auth sessions stored in the PostgreSQL
  `sessions` table and referenced by the browser's HTTP-only
  `ahin_arena_session` cookie. Expired sessions are removed when encountered.
  Production deploys must set `DEPLOY_ENVIRONMENT=production` so this bearer
  session cookie is issued with `Secure`; `REQUIRE_SECURE_COOKIES=true` makes
  startup fail if that would not happen.
- **Job Queue** — PostgreSQL `match_jobs` rows used to track queued, running,
  completed, and failed asynchronous match requests. Workers claim queued jobs
  with `SELECT ... FOR UPDATE SKIP LOCKED`.
- **Worker Pool** — One or more `python3 -m worker.main` processes that claim
  queued match jobs, run matches, persist results, and update ratings.
- **Game Runner** — Executes matches through the registered game engines.
- **Docker** — Secure execution boundary for submitted bot executables. Each
  active static Linux x86-64 ELF artifact is written to a temporary executable
  file and run in a locked-down container with no network access, dropped
  capabilities, a read-only root
  filesystem, and resource limits.

## Asynchronous Match Execution

`POST /matches` validates the requested game and bots, inserts a `match_jobs`
row, sends `NOTIFY match_jobs_channel`, and returns `202 Accepted` with a
`job_id` and `Location: /match-jobs/{job_id}`. The API no longer runs the match
inside the request cycle.

Worker processes listen for notifications and also poll as a fallback. A worker
claims a queued job with `SELECT ... FOR UPDATE SKIP LOCKED`, marks it running,
then runs the existing match execution path. On success, it persists the
completed match, ordered moves, and Elo updates, stores the resulting
`match_id` on the job, and marks the job completed. Clients poll
`GET /match-jobs/{job_id}` until the job completes or fails.

See `docs/queue-and-workers.md` for the `match_jobs` schema, worker loop,
LISTEN/NOTIFY behavior, stalled-job recovery, API shapes, configuration, and
local development workflow.

## Auth Cookie Deployment Check

`DEPLOY_ENVIRONMENT` is the canonical environment variable controlling whether
the API marks `ahin_arena_session` as `Secure`. Use
`DEPLOY_ENVIRONMENT=development` locally and `DEPLOY_ENVIRONMENT=production` in
production. `ENVIRONMENT`, `APP_ENV`, and `FASTAPI_ENV` are legacy fallbacks
only.

Production should also set `REQUIRE_SECURE_COOKIES=true`, which refuses startup
if the cookie would be issued without `Secure`.

Production deployment assets live under `deploy/`. Verify the real production
environment file or secret manager sets `DEPLOY_ENVIRONMENT=production` and
`REQUIRE_SECURE_COOKIES=true` before starting the API.

After deploy, inspect a real login response from the production URL and confirm
the session cookie attributes:

```sh
curl -i -X POST https://<production-host>/auth/login \
  -H 'content-type: application/json' \
  --data '{"email":"<account-email>","password":"<account-password>"}'
```

The response must contain:

```text
Set-Cookie: ahin_arena_session=...; Secure; HttpOnly; SameSite=Lax
```

## Frontend Flow

The frontend runs as a Vite development server during local development. Vite
proxies browser requests from `/api/*` to the FastAPI backend at
`http://127.0.0.1:8000`, stripping the `/api` prefix before forwarding.

The main routes are:

- `/login` — Login page that posts credentials and receives the session cookie.
- `/register` — Registration page that creates an account before login.
- `/verify-email` — Email verification page for emailed verification tokens.
- `/forgot-password` and `/reset-password` — Password reset request and
  confirmation pages.
- `/` — Home page for selecting a supported game, choosing two registered bots,
  starting a match, and viewing recent matches for the selected game.
- `/bots/new` — Authenticated bot registration page for adding a bot name to a
  supported game and uploading a static Linux x86-64 executable for that bot.
- `/bots/:botId` — Public bot profile with rating, record, submission metadata,
  and owner-editable description.
- `/players/:username` — Public player profile with per-game rankings and
  owner-editable description.
- `/matches` — Match history page with all-game or per-game filtering and
  limit/offset-backed pagination.
- `/leaderboard` — Leaderboard page with per-game rankings, configurable row
  count, and pagination.
- `/matches/:matchId` — Match detail page with result summary, rating deltas,
  move history, and replay controls for supported games.
- `/match-jobs/:jobId` — Live queued/running match view that polls job state
  until the match completes or fails.

Replay state is rebuilt entirely in the browser from the move list returned by
`GET /matches/{match_id}`. Tic-Tac-Toe moves are applied to a 3x3 board and
Connect Four moves are dropped into a 6x7 board from the bottom row upward. Each
intermediate board is stored so the replay can jump, scrub, or auto-play by
move number.

Known frontend gap: replay rendering currently supports `tictactoe` and
`connect-four`. Other persisted game IDs fall back to a match summary with a
message that replay is not supported yet.

Known auth gap: sessions, email verification, password reset, and editable
profile descriptions are implemented, but broader account management and
role-based access are not implemented yet.

## Bot Submission Flow

Users create bot records through multipart `POST /bots`, then upload executables through
`POST /bots/{bot_id}/submission`. The submission endpoint requires the current
session user to own the bot, accepts a validated static Linux x86-64 ELF,
stores a new versioned `bot_submissions` row, and points
`bots.active_submission_id` at the newest accepted version.

Match creation resolves each bot's active submission, writes the artifact to a
private executable file, and starts it through a locked-down `docker run`
command under the shared referee protocol. The command bind-mounts the
executable read-only at `/bot/player`, disables networking, drops Linux
capabilities, runs the container read-only with a small `/tmp` tmpfs, and
applies memory, CPU, and PID limits.

See `docs/docker-sandboxing.md` for the runner image, configurable limits, and
cleanup behavior.
