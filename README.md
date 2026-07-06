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

- ✅ Milestone 0 — Project Setup
- ⏳ Milestone 1 — Local Game Engine
- ⏳ Milestone 2 — Backend Service & API
- ⏳ Milestone 3 — Persistent Match History
- ⏳ Milestone 4 — Elo Leaderboard
- ⏳ Milestone 5 — Web Interface
- ⏳ Milestone 6 — User Accounts
- ⏳ Milestone 7 — Bot Submission
- ⏳ Milestone 8 — Docker Sandboxing
- ⏳ Milestone 9 — Queue & Workers
- ⏳ Milestone 10 — Real-Time Games
- ⏳ Milestone 11 — Production Deployment

See `docs/roadmap.md` for more details.

---

## Repository Structure

```
AhinArena/
├── backend/
├── engine/
│   └── tictactoe/
├── frontend/
├── docs/
└── .github/
```

---

## Current Status

This project is currently in **Milestone 1 - Local Game Engine**.

The repository structure, documentation, development workflow, and CI pipeline are being established before development of the core game engine begins.

---

## License

This project is licensed under the MIT License.
