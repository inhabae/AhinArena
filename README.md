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
- [x] Milestone 4 — Persistent Match History
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

`POST /matches` runs a match, persists the completed match and move history to
PostgreSQL, and returns a compact `201 Created` response with the persisted
`match_id`. PostgreSQL is required for API persistence.

Tic-Tac-Toe:

```json
{
  "game": "tictactoe",
  "players": [
    {"bot": "random"},
    {"bot": "random"}
  ]
}
```

Connect Four:

```json
{
  "game": "connect-four",
  "players": [
    {"bot": "random"},
    {"bot": "random"}
  ]
}
```

Successful responses include a `Location: /matches/{match_id}` header and a
compact result summary:

```json
{
  "match_id": 42,
  "game": "tictactoe",
  "winner_bot_id": 1,
  "result_reason": "win"
}
```

Unsupported games return a `400` response with error code `unsupported_game`.

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
    {"move_number": 1, "player": "X", "move": 0},
    {"move_number": 2, "player": "O", "move": 1},
    {"move_number": 3, "player": "X", "move": 0}
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
variable. Export a URL using the psycopg SQLAlchemy driver:

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
