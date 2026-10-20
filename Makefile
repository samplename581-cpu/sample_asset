.PHONY: setup seed index dev test lint typecheck open container-config container-up container-down

COMPOSE ?= docker compose

setup:
	cp -n .env.example .env || true
	uv sync --extra dev

seed:
	uv run python backend/scripts/export_seed_data.py

index:
	uv run python backend/scripts/build_index.py

dev:
	uv run uvicorn helpdesk.main:app --app-dir backend/src --reload --host 127.0.0.1 --port 8000

test:
	uv run pytest backend/tests -v

lint:
	uv run ruff check backend/src backend/scripts backend/tests --fix

typecheck:
	uv run mypy backend/src --ignore-missing-imports

container-config:
	APP_ENV_FILE=$${APP_ENV_FILE:-.env} $(COMPOSE) config

container-up:
	APP_ENV_FILE=$${APP_ENV_FILE:-.env} $(COMPOSE) up --build -d

container-down:
	APP_ENV_FILE=$${APP_ENV_FILE:-.env} $(COMPOSE) down
