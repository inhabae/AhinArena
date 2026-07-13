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
- Login through `POST /auth/login` with server-side session storage
- Logout through `POST /auth/logout` with session deletion and cookie clearing
- Current-user lookup through `GET /auth/me`
- HTTP-only `ahin_arena_session` cookie support with credentialed CORS
- PostgreSQL-backed users and sessions schema with Alembic migrations
- Authenticated match creation for `POST /matches`
- Authenticated bot creation through `POST /bots`
- Bot ownership stored on bot records
- Frontend Login and Register pages at `/login` and `/register`
- Auth-aware Home and Bot Registration flows
- Auth flow documentation in `README.md`, `docs/architecture.md`, and `docs/frontend.md`

---

## Milestone 8 — Bot Submission

**Goal**

Allow developers to upload custom AI agents.

**Deliverables**

- Persistent `bot_submissions` table with per-bot versioning
- `bots.active_submission_id` pointer for the source used in new matches
- Authenticated `POST /bots/{bot_id}/submission` endpoint
- Bot ownership enforcement for source uploads
- Python-only submission validation for non-empty source, 100 KB maximum size,
  and parseable syntax
- Submitted source execution through Docker sandbox commands under the existing
  referee subprocess protocol
- Match creation rejection for bots without an active submission
- Default random bot submissions seeded for supported games
- Frontend source-code submission flow on `/bots/new`
- Bot submission documentation in `docs/bot-submission.md`

---

## Milestone 9 — Docker Sandboxing

**Goal**

Execute uploaded AI agents securely inside isolated Docker containers.

---

## Milestone 10 — Queue & Workers

**Goal**

Support asynchronous match execution using Redis.

---

## Milestone 11 — Real-Time Games

**Goal**

Allow users to spectate matches live through WebSockets.

---

## Milestone 12 — Production Deployment

**Goal**

Deploy AhinArena as a scalable cloud-native application.
