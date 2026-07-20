# AhinArena

AhinArena is a cloud-native platform where developers upload AI agents to compete in automated board game matches. It provides secure match execution, persistent match history, and a foundation for competitive rankings and AI benchmarking.

This project is being developed incrementally with a focus on modern software engineering practices, including CI, Docker, REST APIs, and cloud-native architecture.

---

## Vision

Build a scalable platform where developers can:

- Upload custom AI bots
- Compete against other bots
- Watch live games and replays
- Track rankings and match history

---

## Planned Architecture

```
Frontend (React)
        │
        ▼
Backend API (FastAPI)
        │
        ├── PostgreSQL
        ├── Job Queue (Postgres match_jobs)
        └── Game Runner
                │
                ▼
        Docker Sandboxes
                │
                ▼
          AI Game Engines
```

---

## Roadmap

- [x] Milestone 0 — Project Setup
- [x] Milestone 1 — Local Game Engine
- [x] Milestone 2 — Backend Service & API
- [x] Milestone 3 — Multi-Game Support
- [x] Milestone 4 — Persistent Match History
- [x] Milestone 5 — Elo Leaderboard
- [x] Milestone 6 — Web Interface
- [x] Milestone 7 — User Accounts
- [x] Milestone 8 — Bot Submission
- [x] Milestone 9 — Docker Sandboxing
- [x] Milestone 10 — Queue & Workers
- [ ] Milestone 11 — Production Deployment

See `docs/roadmap.md` for more details.

---

## Local Matches

The website accepts prebuilt static Linux ARM64 executables. It does not compile
or package player source code; users build their bots with their own toolchain
and upload the resulting executable.

---

## Game Protocol Docs

- `docs/tictactoe-engine-referee.md` documents Tic-Tac-Toe bot/referee communication.
- `docs/connectfour-engine-referee.md` documents Connect Four bot/referee communication.
- `docs/frontend.md` documents the React web interface routes, replay behavior, and API client conventions.
- `docs/bot-submission.md` documents uploaded bot executable storage, validation, and match execution.
- `docs/docker-sandboxing.md` documents the Docker runner image, container restrictions, trust boundaries, runner-host controls, image updates, and incident response.
- `docs/queue-and-workers.md` documents asynchronous match jobs, worker execution, queue recovery, APIs, and local workflow.
- `docs/production-images.md` documents reproducible API and worker images, production run commands, image tags, scanning, and SBOM generation.
- `docs/production-stack.md` documents the production Compose stack, migrations, persistent PostgreSQL, ingress/TLS requirements, deployment, and rollback.
- `docs/production-configuration.md` documents validated runtime configuration, secret-manager injection, and credential rotation.
- `docs/operations.md` documents structured telemetry, dashboards, alerts, log retention, and redaction expectations.
- `docs/postgresql-backup-recovery.md` documents encrypted PostgreSQL backup, restore, recovery objectives, and restore drills.
- `docs/deployment-smoke-test.md` documents the reproducible production-style stack smoke test and manual fallback checklist.
- `docs/staging-production-operations.md` is the complete staging-to-production operator guide: infrastructure, DNS/TLS, deployment, verification, promotion, upgrades, rollback, monitoring, incidents, backup, and recovery.

---

## Web Interface

The React/Vite frontend lives in `frontend/`. It provides:

- a Home page for selecting a game, choosing two registered bots, starting a match, and viewing recent matches;
- Login and Register pages for account creation and cookie-backed sessions;
- a Bot Registration page for authenticated users to upload static Linux ARM64 player executables;
- a Match History page with game filtering and pagination;
- a Leaderboard page with per-game rankings, configurable row count, and pagination;
- a Match Detail page with rating summaries, ordered move history, and replay controls.

Install frontend dependencies once:

```sh
cd frontend
npm install
cd ..
```

Run the FastAPI backend locally on `http://127.0.0.1:8000`, run a worker so
queued matches are executed, then start the web app. Use one terminal for each
long-running process:

```sh
make api
```

```sh
make worker
```

```sh
make frontend
```

Vite serves the frontend, usually at `http://localhost:5173`, and proxies
`/api/*` requests to the local backend. See `docs/frontend.md` for the route map
and implementation details.

The API only enqueues match jobs. The worker claims rows from `match_jobs` and
runs the Docker-sandboxed matches. If the worker is not running, new matches
will stay queued on the home page.

Known gap: replay rendering currently supports Tic-Tac-Toe and Connect Four.
Matches for unsupported game IDs fall back to a summary view without a board
replay.

---

## Auth and Bot API

User accounts use server-side sessions persisted in PostgreSQL and identified by
an `ahin_arena_session` HTTP-only cookie. Login, logout, current-user, bot
creation, and match creation requests rely on that cookie.

Authenticated users can submit a static Linux ARM64 ELF executable for bots they own with
`POST /bots/{bot_id}/submission`. Each accepted submission is versioned and the
latest version becomes the bot's active match code. See
`docs/bot-submission.md` for the milestone 8 details and current security
limitations.

Register a user:

```http
POST /auth/register
```

```json
{
  "email": "player@example.com",
  "username": "player",
  "password": "correct horse battery staple"
}
```

Successful registration returns `201 Created` with the public user shape:

```json
{
  "user": {
    "id": 1,
    "email": "player@example.com",
    "username": "player",
    "description": "",
    "is_email_verified": false,
    "created_at": "2026-07-10T17:00:00Z"
  }
}
```

Duplicate email or username values return `409` responses with
`email_already_registered`, `username_already_taken`, or
`registration_conflict` error codes.

Account fields are validated before storage:

- Email addresses are normalized to lowercase, must be ASCII, and can be up to
  254 characters.
- Usernames are trimmed and must be 3-20 ASCII characters using letters,
  numbers, periods, underscores, or hyphens.
- Passwords must be 8-72 characters when registering.

Log in with an existing account:

```http
POST /auth/login
```

```json
{
  "login": "player",
  "password": "correct horse battery staple"
}
```

The `login` value can be either the account email address or username. The
legacy `email` field is still accepted for clients that already use it.

Successful login returns the same public user shape and sets the
`ahin_arena_session` cookie. Invalid credentials return `401` with
`invalid_credentials`. Unverified accounts return `403` with
`email_not_verified`; use the email verification flow before logging in.

Fetch the authenticated user:

```http
GET /auth/me
```

Missing, invalid, or expired sessions return `401` with `unauthorized`.

Log out and clear the current session:

```http
POST /auth/logout
```

Logout returns `204 No Content`. It is idempotent for missing cookies.

Create a bot for the authenticated user:

```http
POST /bots
```

```text
multipart/form-data
game_id=tictactoe
name=my-bot
executable=@player
```

Successful bot creation returns `201 Created`:

```json
{
  "bot_id": 3,
  "game_id": "tictactoe",
  "name": "my-bot",
  "owner_id": 1,
  "submission_id": 9,
  "version": 1
}
```

Unsupported games return `400` with `unsupported_game`; duplicate bot names
within the same game return `409` with `bot_name_taken`; unauthenticated
requests return `401` with `unauthorized`.

Bot names are trimmed and must be 3-32 ASCII characters using letters,
numbers, spaces, underscores, or hyphens.

Authenticated owners can upload replacement player executables with
`POST /bots/{bot_id}/submission`. New matches run each bot's active submission
inside a locked-down Docker container. See `docs/bot-submission.md` and
`docs/docker-sandboxing.md` for details.

---

## Match API

`POST /matches` enqueues a match job and returns `202 Accepted` with a `job_id`.
The request requires an authenticated session cookie. PostgreSQL is required for
API persistence and queueing.

Tic-Tac-Toe:

```json
{
  "game": "tictactoe",
  "players": [
    {"bot": "randombot1"},
    {"bot": "randombot2"}
  ]
}
```

Connect Four:

```json
{
  "game": "connect-four",
  "players": [
    {"bot": "randombot1"},
    {"bot": "randombot2"}
  ]
}
```

Successful responses include a `Location: /match-jobs/{job_id}` header and a
compact job summary:

```json
{
  "job_id": 17,
  "status": "queued"
}
```

Unsupported games return a `400` response with error code `unsupported_game`.

Check a match job:

```http
GET /match-jobs/17
```

Queued or running jobs return a null `match_id`:

```json
{
  "job_id": 17,
  "status": "running",
  "match_id": null,
  "error_message": null
}
```

Completed jobs include the match ID for the existing match detail endpoint:

```json
{
  "job_id": 17,
  "status": "completed",
  "match_id": 42,
  "error_message": null
}
```

Failed jobs return `status: "failed"` with an `error_message`.

### Ratings and leaderboard

Bots start with an Elo rating of `1200`. Completed matches update both bot
ratings with the standard Elo expected-score formula and a K-factor of `32`:
wins score `1.0`, losses score `0.0`, and draws score `0.5`. The new ratings are
rounded to integers.

The current bot record is stored on `bots`:

- `rating`
- `games_played`
- `wins`
- `losses`
- `draws`

Each persisted match stores the rating snapshot used for that result:

- `bot_one_rating_before`, `bot_two_rating_before`
- `bot_one_rating_after`, `bot_two_rating_after`
- `bot_one_rating_delta`, `bot_two_rating_delta`

Fetch a game's leaderboard:

```http
GET /leaderboard?game_id=tictactoe&limit=50&offset=0
```

`game_id` is required. `limit` defaults to `50` and accepts `1` through `500`.
`offset` defaults to `0`. Results are ordered by `rating` descending, with
`bot_id` ascending as the tie-breaker.

```json
[
  {
    "bot_id": 1,
    "name": "random",
    "rating": 1216,
    "games_played": 4,
    "wins": 2,
    "losses": 1,
    "draws": 1
  },
  {
    "bot_id": 2,
    "name": "baseline",
    "rating": 1184,
    "games_played": 4,
    "wins": 1,
    "losses": 2,
    "draws": 1
  }
]
```

Rating snapshots also appear in match history responses so contributors can
audit how a match changed each bot's rating.

List persisted matches:

```http
GET /matches?limit=20&offset=0
```

```json
{
  "items": [
    {
      "match_id": 42,
      "game": "connect-four",
      "bot_one_id": 1,
      "bot_two_id": 2,
      "bot_one_rating_before": 1200,
      "bot_two_rating_before": 1200,
      "bot_one_rating_after": 1216,
      "bot_two_rating_after": 1184,
      "bot_one_rating_delta": 16,
      "bot_two_rating_delta": -16,
      "winner_bot_id": 1,
      "result_reason": "win",
      "created_at": "2026-07-09T17:00:00Z",
      "completed_at": "2026-07-09T17:00:02Z"
    }
  ],
  "limit": 20,
  "offset": 0,
  "total": 1
}
```

Look up one persisted match with ordered move history:

```http
GET /matches/42
```

```json
{
  "match_id": 42,
  "game": "connect-four",
  "bot_one_id": 1,
  "bot_two_id": 2,
  "bot_one_rating_before": 1200,
  "bot_two_rating_before": 1200,
  "bot_one_rating_after": 1216,
  "bot_two_rating_after": 1184,
  "bot_one_rating_delta": 16,
  "bot_two_rating_delta": -16,
  "winner_bot_id": 1,
  "result_reason": "win",
  "created_at": "2026-07-09T17:00:00Z",
  "completed_at": "2026-07-09T17:00:02Z",
  "moves": [
    {"move_number": 1, "bot_id": 1, "move": 0},
    {"move_number": 2, "bot_id": 2, "move": 1},
    {"move_number": 3, "bot_id": 1, "move": 0}
  ]
}
```

Unknown match IDs return a `404` response with error code `match_not_found`.

---

## Local PostgreSQL Setup

Persistent match history requires PostgreSQL. Install and start PostgreSQL
locally, then create an application user and database:

```sh
createuser ahin_arena --pwprompt
createdb ahin_arena --owner ahin_arena
```

The API reads its database connection from the `DATABASE_URL` environment
variable. Copy the example environment file and edit the database user/password
if needed:

```sh
cp .env.example .env
```

The local `Makefile` loads `.env` automatically for `make api`, `make worker`,
and `make migrate`.

Real email delivery for verification and password reset uses Resend when both
`RESEND_API_KEY` and `EMAIL_FROM` are set:

```sh
RESEND_API_KEY=...
EMAIL_FROM="AhinArena <noreply@mail.example.com>"
FRONTEND_URL="https://arena.example.com"
```

When email delivery is configured, registration and password-reset endpoints
send links by email. They never return raw auth tokens. `FRONTEND_URL` controls
the link host and defaults to `http://localhost:5173`.

The API also reads allowed browser origins for CORS from
`CORS_ALLOWED_ORIGINS`. Use a comma-separated list when the frontend runs on a
different origin or port:

```sh
export CORS_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

If unset, the local-development default allows `http://localhost:5173`,
`http://127.0.0.1:5173`, `http://localhost:3000`, and
`http://127.0.0.1:3000`.

The API enables credentialed CORS so browser requests can include the auth
cookie. Because credentials are allowed, `CORS_ALLOWED_ORIGINS` must list
explicit origins and cannot be `*`.

Auth session cookies are controlled by `DEPLOY_ENVIRONMENT`. Local development
uses `DEPLOY_ENVIRONMENT=development`, which issues the HTTP-only
`ahin_arena_session` cookie without `Secure` so localhost HTTP works.
Production deploys must set:

```sh
DEPLOY_ENVIRONMENT=production
REQUIRE_SECURE_COOKIES=true
```

With `DEPLOY_ENVIRONMENT=production`, login responses must include:

```text
Set-Cookie: ahin_arena_session=...; Secure; HttpOnly; SameSite=Lax
```

`REQUIRE_SECURE_COOKIES=true` makes the API refuse startup if the session cookie
would be issued without `Secure`. `ENVIRONMENT`, `APP_ENV`, and `FASTAPI_ENV`
are still recognized as legacy fallbacks, but new deploys should use
`DEPLOY_ENVIRONMENT`.

Run database migrations with Alembic:

```sh
make migrate
```

Tests override the API database dependency and do not require a local
PostgreSQL instance.

---

## Repository Structure

```
AhinArena/
├── api/
├── frontend/
├── engine/
│   ├── connectfour/
│   └── tictactoe/
├── scripts/
├── tests/
│   ├── api/
│   ├── connectfour/
│   └── tictactoe/
├── docs/
└── requirements.txt
```

---

## License

This project is licensed under the MIT License.
