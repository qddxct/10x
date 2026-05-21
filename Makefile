.PHONY: help env up down logs ps clean install install-backend install-frontend \
        test test-backend test-frontend lint lint-backend lint-frontend \
        format dev build

help:
	@echo "Targets:"
	@echo "  install          Install backend (.venv) and frontend deps"
	@echo "  dev              docker compose up -d --build"
	@echo "  build            docker compose build"
	@echo "  up / down / logs / ps / clean"
	@echo "  test             Run backend + frontend tests"
	@echo "  lint             Run backend + frontend linters"
	@echo "  format           Auto-format backend + frontend"

env:
	@test -f .env || cp .env.example .env

install-backend:
	cd backend && python3.11 -m venv .venv && . .venv/bin/activate && \
		pip install --upgrade pip pip-tools && pip install -r requirements.txt

install-frontend:
	cd frontend && pnpm install

install: install-backend install-frontend

up: env
	docker compose up -d

dev: env
	docker compose up -d --build

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v

test-backend:
	cd backend && . .venv/bin/activate && MYSQL_HOST=localhost pytest -v

test-frontend:
	cd frontend && pnpm test

test: test-backend test-frontend

lint-backend:
	cd backend && . .venv/bin/activate && ruff check . && black --check .

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

lint: lint-backend lint-frontend

format:
	cd backend && . .venv/bin/activate && ruff check --fix . && black .
	cd frontend && pnpm format
