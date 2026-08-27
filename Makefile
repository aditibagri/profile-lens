IMAGE ?= linkedin-profile-api
PORT ?= 8000
PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help venv run up down logs restart health ps build stop

help:
	@echo "LinkedIn Profile API"
	@echo ""
	@echo "  make run       Start locally with uvicorn (no Docker) — use this"
	@echo "  make stop      Stop whatever is listening on port $(PORT)"
	@echo "  make up        Docker if installed, otherwise same as make run"
	@echo "  make health    Hit GET /health"
	@echo "  make down      Stop the Docker container (no-op for local uvicorn)"
	@echo "  make logs      Follow Docker container logs"
	@echo "  make restart   Rebuild and restart Docker"
	@echo "  make build     Build the Docker image only"
	@echo "  make ps        Show Docker container status"
	@echo "  make venv      Create .venv and install requirements"

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -r requirements.txt

run: .env
	@test -x $(BIN)/python || (echo "Missing .venv — run: make venv" && exit 1)
	@echo "API:    http://127.0.0.1:$(PORT)"
	@echo "UI:     http://127.0.0.1:$(PORT)/"
	@echo "Docs:   http://127.0.0.1:$(PORT)/docs"
	@echo "Health: http://127.0.0.1:$(PORT)/health"
	@echo "Stop with Ctrl+C (or: make stop)"
	PYTHONPATH=backend $(BIN)/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

stop:
	@pids=$$(lsof -tiTCP:$(PORT) -sTCP:LISTEN 2>/dev/null); \
	if [ -n "$$pids" ]; then \
		kill $$pids 2>/dev/null || true; \
		sleep 0.3; \
		kill -9 $$pids 2>/dev/null || true; \
		echo "Stopped process(es) on port $(PORT)."; \
	else \
		echo "Nothing listening on port $(PORT)."; \
	fi

build:
	docker compose build

up: .env
	@if command -v docker >/dev/null 2>&1; then \
		docker compose up --build -d; \
		echo ""; \
		echo "API running at http://127.0.0.1:$(PORT)"; \
		echo "Docs:          http://127.0.0.1:$(PORT)/docs"; \
		echo "Health:        http://127.0.0.1:$(PORT)/health"; \
	else \
		echo "Docker is not installed — starting locally with uvicorn."; \
		echo "Install Docker Desktop later if you want containers."; \
		echo ""; \
		$(MAKE) run; \
	fi

.env:
	cp .env.example .env
	@echo "Created .env from .env.example — paste LINKEDIN_LI_AT and LINKEDIN_JSESSIONID, then run make run again."

down:
	@if command -v docker >/dev/null 2>&1; then docker compose down; else echo "Nothing to stop (local uvicorn: use Ctrl+C or make stop)."; fi

logs:
	docker compose logs -f

restart: down up

health:
	curl -sS http://127.0.0.1:$(PORT)/health
	@echo

ps:
	@if command -v docker >/dev/null 2>&1; then docker compose ps; else echo "Docker is not installed. For a local server, run: make run"; fi
