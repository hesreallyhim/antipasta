# Virtual environment configuration
VENV_NAME := venv
VENV_DIR := $(VENV_NAME)
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

# Detect OS for activation script
ifeq ($(OS),Windows_NT)
	VENV_ACTIVATE := $(VENV_DIR)/Scripts/activate
	PYTHON := $(VENV_DIR)/Scripts/python
	PIP := $(VENV_DIR)/Scripts/pip
else
	VENV_ACTIVATE := $(VENV_DIR)/bin/activate
endif

.PHONY: help venv install install-dev install-prod format lint type-check test test-cov clean clean-venv

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

venv:  ## Create virtual environment if it doesn't exist
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		python -m venv $(VENV_DIR); \
		$(PIP) install --upgrade pip setuptools wheel; \
	else \
		echo "Virtual environment already exists at $(VENV_DIR)"; \
	fi

install: venv  ## Install the package in development mode
	$(PIP) install -e .

install-dev: venv  ## Install the package in development mode with all dev dependencies
	$(PIP) install -e ".[dev]"

install-prod: venv  ## Install the package in production mode
	$(PIP) install .

format: venv  ## Format code with black and ruff
	$(VENV_DIR)/bin/black code_cop tests
	$(VENV_DIR)/bin/ruff check --fix code_cop tests

lint: venv  ## Run linting checks with ruff
	$(VENV_DIR)/bin/ruff check code_cop tests

type-check: venv  ## Run type checking with mypy
	$(VENV_DIR)/bin/mypy code_cop tests

test: venv  ## Run tests with pytest
	$(VENV_DIR)/bin/pytest --no-cov

test-cov: venv  ## Run tests with coverage report
	rm -f .coverage*
	$(VENV_DIR)/bin/pytest --cov=code_cop --cov-report=term-missing --cov-report=html
	@if ls .coverage.* 1> /dev/null 2>&1; then $(VENV_DIR)/bin/coverage combine; fi

clean:  ## Clean up build artifacts and cache files
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage .coverage.* coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-venv:  ## Remove virtual environment
	rm -rf $(VENV_DIR)