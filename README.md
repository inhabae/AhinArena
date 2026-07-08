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
        ├── Redis
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
- [ ] Milestone 4 — Persistent Match History
- [ ] Milestone 5 — Elo Leaderboard
- [ ] Milestone 6 — Web Interface
- [ ] Milestone 7 — User Accounts
- [ ] Milestone 8 — Bot Submission
- [ ] Milestone 9 — Docker Sandboxing
- [ ] Milestone 10 — Queue & Workers
- [ ] Milestone 11 — Real-Time Games
- [ ] Milestone 12 — Production Deployment

See `docs/roadmap.md` for more details.

---

## Local Matches

Run a local Tic-Tac-Toe match between the built-in random bots:

```sh
python3 scripts/run_local_tictactoe.py --timeout 1.0
```

Run a local Connect Four match between the built-in random bots:

```sh
python3 scripts/run_local_connect_four.py --timeout 1.0
```

Both local runners print each move, the board after that move, and the final match result.

---

## Game Protocol Docs

- `docs/tictactoe-engine-referee.md` documents Tic-Tac-Toe bot/referee communication.
- `docs/connectfour-engine-referee.md` documents Connect Four bot/referee communication.

---

## Match API

`POST /matches` supports multiple games through the `game` field.

Tic-Tac-Toe:

```json
{
  "game": "tictactoe",
  "players": [
    {"id": "player-x", "bot": "random"},
    {"id": "player-o", "bot": "random"}
  ]
}
```

Connect Four:

```json
{
  "game": "connect-four",
  "players": [
    {"id": "player-x", "bot": "random"},
    {"id": "player-o", "bot": "random"}
  ]
}
```

Responses use a consistent shape:

```json
{
  "game": "connect-four",
  "players": [
    {"id": "player-x", "bot": "random"},
    {"id": "player-o", "bot": "random"}
  ],
  "result": {
    "winner": "X",
    "reason": "win",
    "moves": [["X", 0]],
    "final_board": []
  }
}
```

Unsupported games return a `400` response with error code `unsupported_game`.

---

## Local PostgreSQL Setup

The API reads its database connection from the `DATABASE_URL` environment
variable. For local development, create a PostgreSQL database and export a URL
using the psycopg SQLAlchemy driver:

```sh
export DATABASE_URL="postgresql+psycopg://ahin_arena:ahin_arena@localhost:5432/ahin_arena"
```

Run database migrations with Alembic:

```sh
alembic upgrade head
```

Tests override the API database dependency and do not require a local
PostgreSQL instance.

---

## Repository Structure

```
AhinArena/
├── api/
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
