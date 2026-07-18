.PHONY: api worker frontend migrate test builtin-players sleepy-players

-include .env
export

PYTHON ?= .venv/bin/python
ALEMBIC ?= .venv/bin/alembic
UVICORN ?= .venv/bin/uvicorn
WORKER_POLL_INTERVAL_SECONDS ?= 1
DOCKER ?= docker

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

# Local developer utility only; the website never invokes this target.
builtin-players:
	@$(DOCKER) info >/dev/null 2>&1 || (echo "Docker Desktop must be running to build Linux player executables."; exit 1)
	$(DOCKER) run --rm --platform linux/amd64 -v "$(CURDIR):/workspace" -w /workspace alpine:3.20 sh -c 'apk add --no-cache build-base >/dev/null && mkdir -p build/default-bots && cc -O2 -static -s -DBOARD_SIZE=3 -o build/default-bots/tictactoe players/builtin_player.c && cc -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -o build/default-bots/connect-four players/builtin_player.c'

sleepy-players:
	@$(DOCKER) info >/dev/null 2>&1 || (echo "Docker Desktop must be running to build Linux player executables."; exit 1)
	$(DOCKER) run --rm --platform linux/amd64 -v "$(CURDIR):/workspace" -w /workspace alpine:3.20 sh -c 'apk add --no-cache build-base >/dev/null && mkdir -p build/example-bots && cc -O2 -static -s -DBOARD_SIZE=3 -DMOVE_DELAY_SECONDS=3 -o build/example-bots/sleepy-tictactoe players/builtin_player.c && cc -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -DMOVE_DELAY_SECONDS=3 -o build/example-bots/sleepy-connect-four players/builtin_player.c'
