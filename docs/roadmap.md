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

- Elo rating system
- Leaderboard API

---

## Milestone 6 — Web Interface

**Goal**

Provide a basic web application for interacting with the platform.

**Deliverables**

- Home page
- Match history
- Leaderboard
- Replay viewer

---

## Milestone 7 — User Accounts

**Goal**

Allow users to create accounts and manage their bots.

---

## Milestone 8 — Bot Submission

**Goal**

Allow developers to upload custom AI agents.

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
