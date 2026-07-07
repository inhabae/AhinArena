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
- [ ] Milestone 3 — Multi-Game Support
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

## License

This project is licensed under the MIT License.
