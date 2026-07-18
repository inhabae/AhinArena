.PHONY: api worker frontend migrate test builtin-players

-include .env
export

PYTHON ?= .venv/bin/python
ALEMBIC ?= .venv/bin/alembic
UVICORN ?= .venv/bin/uvicorn
WORKER_POLL_INTERVAL_SECONDS ?= 1
CC ?= cc

api:
	PYTHONPATH=. $(UVICORN) api.main:app --reload

worker:
	PYTHONPATH=. WORKER_POLL_INTERVAL_SECONDS=$(WORKER_POLL_INTERVAL_SECONDS) $(PYTHON) -m worker.main

frontend:
	cd frontend && npm run dev

migrate:
	PYTHONPATH=. $(ALEMBIC) upgrade head

test:
	PYTHONPATH=. $(PYTHON) -m pytest

builtin-players:
	mkdir -p build/default-bots
	$(CC) -O2 -static -s -DBOARD_SIZE=3 -o build/default-bots/tictactoe players/builtin_player.c
	$(CC) -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -o build/default-bots/connect-four players/builtin_player.c
