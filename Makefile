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

.PHONY: help venv install install-dev install-prod format lint type-check test test-cov check clean clean-venv clean-cov

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

format: install-dev  ## Format code with black and ruff
	$(VENV_DIR)/bin/black code_cop tests
	$(VENV_DIR)/bin/ruff check --fix code_cop tests

lint: install-dev  ## Run linting checks with ruff
	$(VENV_DIR)/bin/ruff check code_cop tests

type-check: install-dev  ## Run type checking with mypy
	$(VENV_DIR)/bin/mypy code_cop tests

test: install-dev  ## Run tests with pytest
	$(VENV_DIR)/bin/pytest --no-cov

test-cov: install-dev  ## Run tests with coverage report
	# Clean up any existing coverage data
	@rm -rf .coverage htmlcov
	# Create .coverage/ directory to contain temporary parallel coverage files during execution
	# This prevents dozens of .coverage.* files from polluting the root directory
	@mkdir -p .coverage
	# Set up trap to clean up on interrupt (Ctrl+C) and preserve final .coverage file if it exists
	@trap 'mv .coverage/.coverage .coverage.tmp 2>/dev/null; rm -rf .coverage 2>/dev/null; mv .coverage.tmp .coverage 2>/dev/null || true' EXIT INT TERM; \
	$(VENV_DIR)/bin/pytest --cov=code_cop --cov-branch --cov-report=term-missing --cov-report=html -p no:cacheprovider; \
	mv .coverage/.coverage .coverage 2>/dev/null || true

check: lint type-check test  ## Run all quality checks (lint, type-check, test)

clean:  ## Clean up build artifacts and cache files
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov coverage.xml
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-venv:  ## Remove virtual environment
	rm -rf $(VENV_DIR)

clean-cov:  ## Clean up coverage files
	rm -rf .coverage htmlcov