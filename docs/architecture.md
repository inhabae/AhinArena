# AhinArena Architecture

## Overview

AhinArena is a cloud-native platform where developers upload AI agents to compete in automated board game matches.

The system consists of a web frontend, backend services, persistent storage, and isolated game execution through Docker.

---

## High-Level Architecture

```text
                Frontend (React)
                        │
                        ▼
              Backend API (FastAPI)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   PostgreSQL         Redis        Matchmaker
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

- **Frontend** — User interface
- **Backend API** — Application logic
- **PostgreSQL** — Persistent data
- **Redis** — Cache and queues
- **Matchmaker** — Selects opponents
- **Game Runner** — Executes matches
- **Docker** — Secure AI execution