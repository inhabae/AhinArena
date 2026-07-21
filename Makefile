.PHONY: api worker frontend migrate test production-migrate production-up production-proxy-up builtin-players sleepy-players

-include .env
export

PYTHON ?= .venv/bin/python
ALEMBIC ?= .venv/bin/alembic
UVICORN ?= .venv/bin/uvicorn
WORKER_POLL_INTERVAL_SECONDS ?= 1
DOCKER ?= docker
COMPOSE ?= $(DOCKER) compose
PRODUCTION_ENV_FILE ?= /secure/path/ahinarena.production.env
PRODUCTION_COMPOSE_FILE ?= deploy/compose.production.yaml
PRODUCTION_PROXY_COMPOSE_FILE ?= deploy/compose.caddy.yaml

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

# The only production command that applies Alembic migrations. It is intentionally
# separate from application startup so API/worker replicas never migrate schemas.
production-migrate:
	$(COMPOSE) --env-file $(PRODUCTION_ENV_FILE) -f $(PRODUCTION_COMPOSE_FILE) up -d --wait postgres
	$(COMPOSE) --env-file $(PRODUCTION_ENV_FILE) -f $(PRODUCTION_COMPOSE_FILE) up --no-deps --abort-on-container-exit --exit-code-from migrate migrate

# Run the one-shot migration before starting or replacing API/worker containers.
production-up: production-migrate
	$(COMPOSE) --env-file $(PRODUCTION_ENV_FILE) -f $(PRODUCTION_COMPOSE_FILE) up -d --no-deps --wait api worker

production-proxy-up:
	$(COMPOSE) --env-file $(PRODUCTION_ENV_FILE) -f $(PRODUCTION_COMPOSE_FILE) -f $(PRODUCTION_PROXY_COMPOSE_FILE) up -d --wait caddy

# Local developer utility only; the website never invokes this target.
builtin-players:
	@$(DOCKER) info >/dev/null 2>&1 || (echo "Docker Desktop must be running to build Linux player executables."; exit 1)
	$(DOCKER) run --rm --platform linux/amd64 -v "$(CURDIR):/workspace" -w /workspace alpine:3.20 sh -c 'apk add --no-cache build-base >/dev/null && mkdir -p build/default-bots && cc -O2 -static -s -DBOARD_SIZE=3 -o build/default-bots/tictactoe players/builtin_player.c && cc -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -o build/default-bots/connect-four players/builtin_player.c'

sleepy-players:
	@$(DOCKER) info >/dev/null 2>&1 || (echo "Docker Desktop must be running to build Linux player executables."; exit 1)
	$(DOCKER) run --rm --platform linux/amd64 -v "$(CURDIR):/workspace" -w /workspace alpine:3.20 sh -c 'apk add --no-cache build-base >/dev/null && mkdir -p build/example-bots && cc -O2 -static -s -DBOARD_SIZE=3 -DMOVE_DELAY_SECONDS=3 -o build/example-bots/sleepy-tictactoe players/builtin_player.c && cc -O2 -static -s -DBOARD_SIZE=7 -DCONNECT_FOUR=1 -DMOVE_DELAY_SECONDS=3 -o build/example-bots/sleepy-connect-four players/builtin_player.c'
