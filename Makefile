.PHONY: help install setup test lint format clean run docker-up docker-down

help:
	@echo "SDLC Multi-Agent System - Available Commands:"
	@echo "  make install      - Install dependencies via Poetry"
	@echo "  make setup        - Initial setup (install + configure)"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make run          - Run interactive chat"
	@echo "  make docker-up    - Start Docker services (ClickHouse, Ollama)"
	@echo "  make docker-down  - Stop Docker services"

install:
	poetry install

setup: install
	@echo "Setting up SDLC Agent System..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please configure it"; fi
	@echo "Starting Docker services..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Pulling Ollama model..."
	docker exec sdlc-ollama ollama pull llama3.1:8b
	@echo "Setup complete! Configure your .env file and run 'make run'"

test:
	poetry run pytest -v

test-cov:
	poetry run pytest --cov=sdlc_agents --cov-report=html

lint:
	poetry run ruff check src/
	poetry run mypy src/

format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov
	rm -rf dist/ build/ *.egg-info

run:
	poetry run sdlc-agent chat

run-story:
	@read -p "Enter story ID: " story_id; \
	poetry run sdlc-agent implement $$story_id

run-split:
	@read -p "Enter feature ID: " feature_id; \
	poetry run sdlc-agent split $$feature_id

docker-up:
	docker-compose up -d
	@echo "Services starting... wait for them to be ready"
	@echo "ClickHouse: http://localhost:8123"
	@echo "Ollama: http://localhost:11434"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

info:
	poetry run sdlc-agent info
