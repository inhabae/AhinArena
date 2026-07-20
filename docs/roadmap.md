# AhinArena Roadmap

This roadmap outlines the planned development milestones for AhinArena. Each milestone delivers a working feature that builds toward a complete AI competition platform.

---

## Milestone 0 — Project Setup

**Goal**

Establish the repository, documentation, development workflow, and CI pipeline.

**Deliverables**

- Repository structure
- GitHub Project & Issues
- GitHub Actions CI
- Initial documentation

---

## Milestone 1 — Local Game Engine

**Goal**

Develop the core game engine capable of running local bot-vs-bot matches.

**Deliverables**

- Board representation
- Legal move validation
- Game loop
- Winner detection
- Bot interface

---

## Milestone 2 — Backend Service & API

**Goal**

Expose the game engine through a REST API.

**Deliverables**

- FastAPI backend
- Match execution endpoint
- API testing

---

## Milestone 3 — Multi-Game Support

**Goal**

Expand the platform beyond Tic-Tac-Toe by introducing reusable game abstractions and support for multiple game engines.

**Deliverables**

- Game registry
- Shared game interface
- Multi-game match request support
- Connect Four engine support
- Connect Four local runner
- Multi-game API routing for Tic-Tac-Toe and Connect Four
- API validation for unsupported games

---

## Milestone 4 — Persistent Match History

**Goal**

Store completed matches in PostgreSQL.

**Deliverables**

- PostgreSQL-backed database schema
- Alembic migrations for matches and moves
- Match persistence from `POST /matches`
- Match history listing through `GET /matches`
- Match detail lookup with ordered move history through `GET /matches/{match_id}`
- Persisted match IDs returned from match creation

---

## Milestone 5 — Elo Leaderboard

**Goal**

Introduce competitive rankings.

**Deliverables**

- Elo rating system with `1200` default ratings and K-factor `32`
- Bot rating and record persistence
- Match rating snapshots for before/after ratings and deltas
- Leaderboard API through `GET /leaderboard`
- Leaderboard filtering by game with limit/offset pagination
- Rating and leaderboard documentation in the README

---

## Milestone 6 — Web Interface

**Goal**

Provide a web application for starting matches, browsing persisted results,
tracking rankings, and replaying supported games.

**Deliverables**

- React/Vite frontend under `frontend/`
- Shared application layout and route map for `/`, `/matches`, `/leaderboard`, and `/matches/:matchId`
- Home page with game selection, bot selection, match creation, recent matches, and API error handling
- Match history page with all-game/per-game filtering, 20-row pagination, rating deltas, and match-detail navigation
- Leaderboard page with per-game rankings, configurable page sizes, and offset pagination
- Match detail page with result summary, rating snapshots, ordered move history, and replay controls
- Browser replay reconstruction for Tic-Tac-Toe and Connect Four from persisted move history
- Unsupported-game replay fallback that shows the matchup/result and reports that replay is not supported yet
- Frontend API client conventions documented in `docs/frontend.md`

---

## Milestone 7 — User Accounts

**Goal**

Allow users to create accounts and manage their bots.

**Deliverables**

- User registration through `POST /auth/register`
- Email verification through `POST /auth/verify-email` and
  `POST /auth/verify-email/resend`
- Password reset through request, validate, and confirm endpoints
- Login through `POST /auth/login` with server-side session storage
- Logout through `POST /auth/logout` with session deletion and cookie clearing
- Current-user lookup through `GET /auth/me`
- Current-user description updates through `PATCH /auth/me`
- Public player profiles through `GET /users/{username}`
- HTTP-only `ahin_arena_session` cookie support with credentialed CORS
- PostgreSQL-backed users, sessions, auth tokens, and auth rate-limit event
  schemas with Alembic migrations
- Authenticated match creation for `POST /matches`
- Authenticated bot creation through `POST /bots`
- Bot ownership stored on bot records
- Frontend Login, Register, Verify Email, Forgot Password, Reset Password, and
  Player Profile pages
- Auth-aware Home and Bot Registration flows
- Auth flow documentation in `README.md`, `docs/architecture.md`, and `docs/frontend.md`

---

## Milestone 8 — Bot Submission

**Goal**

Allow developers to upload custom AI agents.

**Deliverables**

- Persistent `bot_submissions` table with per-bot versioning
- `bots.active_submission_id` pointer for the executable used in new matches
- Authenticated `POST /bots/{bot_id}/submission` endpoint
- Bot ownership enforcement for executable uploads
- Static Linux x86-64 ELF validation, including upload size, architecture, and
  dynamic-linking rejection
- Submitted executable execution through Docker sandbox commands under the
  existing referee subprocess protocol
- Match creation rejection for bots without an active submission
- Deployment-provided executable artifacts seeded for supported games
- Frontend executable submission flow on `/bots/new`
- Bot submission documentation in `docs/bot-submission.md`

---

## Milestone 9 — Docker Sandboxing

**Goal**

Execute uploaded AI agents securely inside isolated Docker containers.

**Deliverables**

- Dedicated bot runner image in `docker/bot_runner/Dockerfile`
- Non-root sandbox user inside the runner image
- Submitted executable mounted read-only at `/bot/player`
- Per-bot temporary executable files created from active submissions
- Per-bot named containers for match execution
- Container networking disabled with `--network none`
- Linux capabilities dropped and `no-new-privileges` enabled
- Read-only container root filesystem with constrained `/tmp` tmpfs
- Memory, CPU, and PID limits configurable through environment variables
- Sandbox cleanup that force-removes containers and deletes temporary executable
  directories after match execution
- Docker sandboxing documentation in `docs/docker-sandboxing.md`

---

## Milestone 10 — Queue & Workers

**Status: Done**

**Goal**

Support asynchronous match execution through a PostgreSQL-backed job queue and
separate worker processes.

**Deliverables**

- PostgreSQL-backed `match_jobs` table for queued match requests
- `POST /matches` enqueue flow returning `202 Accepted`, `job_id`, and a
  `Location: /match-jobs/{job_id}` header
- Job status lookup through `GET /match-jobs/{job_id}`
- Worker process entry point through `python3 -m worker.main`
- Worker job claiming with `SELECT ... FOR UPDATE SKIP LOCKED`
- Existing referee, Docker sandboxing, match persistence, move persistence, and
  Elo rating updates executed from workers
- PostgreSQL `LISTEN`/`NOTIFY` wakeups with polling fallback
- Stalled `running` job recovery with attempt limits
- Frontend match creation polling until completion or failure

---

## Milestone 11 — Production Deployment

**Goal**

Deploy AhinArena as a scalable cloud-native application.
