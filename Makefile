# AegisAI Makefile
# Common commands for development, testing, and deployment

.PHONY: help install dev test lint format clean \
        docker-build docker-run docker-stop docker-logs docker-shell \
        docker-dev docker-monitoring docker-full docker-clean \
        run api

# Default target
help:
	@echo "AegisAI - Available Commands"
	@echo "============================"
	@echo ""
	@echo "Development:"
	@echo "  make install        Install dependencies"
	@echo "  make dev            Install with dev dependencies"
	@echo "  make run            Run main.py"
	@echo "  make api            Start the FastAPI server locally"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-cov       Run tests with coverage"
	@echo "  make lint           Run linters (pylint, flake8, mypy)"
	@echo "  make format         Format code (black, isort)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build production Docker image"
	@echo "  make docker-run     Run production container"
	@echo "  make docker-stop    Stop all containers"
	@echo "  make docker-logs    View container logs"
	@echo "  make docker-shell   Open shell in running container"
	@echo "  make docker-dev     Run development environment"
	@echo "  make docker-monitoring  Run with Prometheus & Grafana"
	@echo "  make docker-full    Run with all services (MLflow included)"
	@echo "  make docker-clean   Remove containers, images, and volumes"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          Clean build artifacts and caches"

# ============================================
# Development
# ============================================

install:
	uv sync

dev:
	uv sync --all-extras

run:
	uv run python main.py

api:
	uv run uvicorn aegis_ai.api.gateway:app --host 0.0.0.0 --port 8000 --reload

# ============================================
# Testing & Quality
# ============================================

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v -m unit

test-cov:
	uv run pytest tests/ -v --cov=src/aegis_ai --cov-report=html --cov-report=term

lint:
	uv run pylint src/aegis_ai
	uv run flake8 src/aegis_ai
	uv run mypy src/aegis_ai

format:
	uv run black src/ tests/
	uv run isort src/ tests/

# ============================================
# Docker Commands
# ============================================

DOCKER_IMAGE := aegis-ai
DOCKER_TAG := latest
COMPOSE := docker compose

docker-build:
	docker build --network=host -t $(DOCKER_IMAGE):$(DOCKER_TAG) -f docker/Dockerfile --target production .

docker-run:
	$(COMPOSE) up -d aegis-api

docker-stop:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f aegis-api

docker-shell:
	$(COMPOSE) exec aegis-api /bin/bash

docker-dev:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up --build

docker-monitoring:
	$(COMPOSE) --profile monitoring up --build

docker-full:
	$(COMPOSE) --profile full --profile monitoring up --build

docker-clean:
	$(COMPOSE) down -v --rmi local
	docker image prune -f

# ============================================
# Utilities
# ============================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
