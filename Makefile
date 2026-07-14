.PHONY: api worker frontend migrate test

-include .env
export

PYTHON ?= .venv/bin/python
ALEMBIC ?= .venv/bin/alembic
UVICORN ?= .venv/bin/uvicorn
WORKER_POLL_INTERVAL_SECONDS ?= 1

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
