.PHONY: help install install-dev format lint type-check test test-cov clean

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install:  ## Install the package in production mode
	pip install .

install-dev:  ## Install the package in development mode with all dev dependencies
	pip install -e ".[dev]"

format:  ## Format code with black and ruff
	black code_cop tests
	ruff check --fix code_cop tests

lint:  ## Run linting checks with ruff
	ruff check code_cop tests

type-check:  ## Run type checking with mypy
	mypy code_cop tests

test:  ## Run tests with pytest
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=code_cop --cov-report=term-missing --cov-report=html

clean:  ## Clean up build artifacts and cache files
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete