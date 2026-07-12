# AhinArena Architecture

## Overview

AhinArena is a cloud-native platform where developers upload AI agents to compete in automated board game matches.

The system consists of a web frontend, backend services, persistent storage, and isolated game execution through Docker.

---

## High-Level Architecture

```text
        Frontend (React + Vite)
 Auth / Home / History / Leaderboard / Replay
                        │
                        │ /api via frontend/src/api/client.js
                        ▼
              Backend API (FastAPI)
                        │
        ┌───────────────┼───────────────┬───────────────┐
        │               │               │               │
        ▼               ▼               ▼               ▼
   PostgreSQL    Session Storage      Redis        Matchmaker
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
  for the Login, Register, Home, Bot Registration, Match History, Leaderboard,
  and Match Detail/Replay pages.
- **Frontend API client** — `frontend/src/api/client.js` centralizes browser
  calls to the Backend API. It prefixes requests with `/api`, serializes query
  params, parses JSON responses, and raises `ApiError` instances for normalized
  backend errors.
- **Backend API** — FastAPI application logic for health checks, registration,
  login/logout, current-user lookup, bot lookup and creation, match creation,
  bot source submission, match history, match detail, and leaderboard data.
- **PostgreSQL** — Persistent data for bots, completed matches, ordered moves,
  ratings, records, users, sessions, bot submissions, active bot submission
  pointers, and per-match rating snapshots.
- **Session Storage** — Server-side auth sessions stored in the PostgreSQL
  `sessions` table and referenced by the browser's HTTP-only
  `ahin_arena_session` cookie. Expired sessions are removed when encountered.
- **Redis** — Planned cache and queue layer.
- **Matchmaker** — Planned opponent selection service.
- **Game Runner** — Executes matches through the registered game engines.
- **Docker** — Planned secure AI execution boundary.

## Frontend Flow

The frontend runs as a Vite development server during local development. Vite
proxies browser requests from `/api/*` to the FastAPI backend at
`http://127.0.0.1:8000`, stripping the `/api` prefix before forwarding.

The main routes are:

- `/login` — Login page that posts credentials and receives the session cookie.
- `/register` — Registration page that creates an account before login.
- `/` — Home page for selecting a supported game, choosing two registered bots,
  starting a match, and viewing recent matches for the selected game.
- `/bots/new` — Authenticated bot registration page for adding a bot name to a
  supported game and submitting Python source code for that bot.
- `/matches` — Match history page with all-game or per-game filtering and
  limit/offset-backed pagination.
- `/leaderboard` — Leaderboard page with per-game rankings, configurable row
  count, and pagination.
- `/matches/:matchId` — Match detail page with result summary, rating deltas,
  move history, and replay controls for supported games.

Replay state is rebuilt entirely in the browser from the move list returned by
`GET /matches/{match_id}`. Tic-Tac-Toe moves are applied to a 3x3 board and
Connect Four moves are dropped into a 6x7 board from the bottom row upward. Each
intermediate board is stored so the replay can jump, scrub, or auto-play by
move number.

Known frontend gap: replay rendering currently supports `tictactoe` and
`connect-four`. Other persisted game IDs fall back to a match summary with a
message that replay is not supported yet.

Known auth gap: sessions are durable and cookie-backed, but account management
is intentionally minimal. Password reset, email verification, and role-based
access are not implemented yet.

## Bot Submission Flow

Users create bot records through `POST /bots`, then upload source code through
`POST /bots/{bot_id}/submission`. The submission endpoint requires the current
session user to own the bot, accepts only Python, stores a new versioned
`bot_submissions` row, and points `bots.active_submission_id` at the newest
accepted version.

Match creation resolves each bot's active submission and starts that source as a
temporary Python subprocess under the shared referee protocol. This is the
milestone 8 execution path only; Docker sandboxing remains a planned milestone,
so submitted code is not isolated from the host process environment yet.
