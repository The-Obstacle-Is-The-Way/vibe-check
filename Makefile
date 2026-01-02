# Makefile - Developer convenience commands
.PHONY: help install dev test test-unit lint lint-fix format format-check typecheck ci clean

# Default target
help:
	@echo "vibe-check development commands:"
	@echo ""
	@echo "  make dev          Install all dependencies + pre-commit hooks"
	@echo "  make install      Install production dependencies only"
	@echo "  make test         Run all tests with coverage"
	@echo "  make test-unit    Run unit tests only (fast)"
	@echo "  make lint         Run ruff linter"
	@echo "  make lint-fix     Auto-fix linting issues"
	@echo "  make format       Format code with ruff"
	@echo "  make format-check Check formatting without changes"
	@echo "  make typecheck    Run mypy strict type checking"
	@echo "  make ci           Full CI: lint + typecheck + test"
	@echo "  make clean        Remove build artifacts"

# ─────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────
install:
	uv sync --locked

dev:
	uv sync --locked --all-extras
	uv run pre-commit install

# ─────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────
test:
	uv run pytest tests/ --cov=src/vibe_check --cov-report=term-missing --cov-fail-under=80

test-unit:
	uv run pytest tests/unit/ -v

# ─────────────────────────────────────────────────────────────
# Code Quality
# ─────────────────────────────────────────────────────────────
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy src tests

# ─────────────────────────────────────────────────────────────
# CI
# ─────────────────────────────────────────────────────────────
ci: format-check lint typecheck test

# ─────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
