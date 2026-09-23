VENV_NAME := venv
VENV_DIR := $(VENV_NAME)
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
TOX := $(VENV_DIR)/bin/tox
PRE_COMMIT := $(VENV_DIR)/bin/pre-commit
ANTIPASTA := $(VENV_DIR)/bin/antipasta

.PHONY: install-hooks help venv install install-dev install-prod format lint type-check test test-fast test-fast-clean test-cov check check-ci check-all clean clean-venv clean-cov clean-tox build build-check release-dry-run treemap metrics metrics-quiet metrics-json metrics-report self-check

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

format: install-dev  ## Format code with ruff
	$(VENV_DIR)/bin/ruff format src/antipasta tests
	$(VENV_DIR)/bin/ruff check --fix src/antipasta tests

lint: install-dev  ## Run formatting and linting checks with ruff
	$(VENV_DIR)/bin/ruff format --check src/antipasta tests
	$(VENV_DIR)/bin/ruff check src/antipasta tests

type-check: install-dev  ## Run type checking with mypy
	$(VENV_DIR)/bin/mypy src/antipasta tests

test: install-dev  ## Run tests with pytest
	$(VENV_DIR)/bin/pytest --no-cov

test-fast: install-dev  ## Run targeted tests with pytest-testmon
	@mkdir -p .cache
	TESTMON_DATAFILE=.cache/testmon.sqlite $(VENV_DIR)/bin/pytest --testmon

test-fast-clean:  ## Remove cached testmon data to force a full run
	rm -f .cache/testmon.sqlite .cache/testmon.sqlite-shm .cache/testmon.sqlite-wal .testmondata*

test-cov: install-dev  ## Run tests with coverage report
	# Clean up any existing coverage data
	@rm -rf .coverage htmlcov
	# Create .coverage/ directory to contain temporary parallel coverage files during execution
	# This prevents dozens of .coverage.* files from polluting the root directory
	@mkdir -p .coverage
	# Set up trap to clean up on interrupt (Ctrl+C) and preserve final .coverage file if it exists
	@trap 'mv .coverage/.coverage .coverage.tmp 2>/dev/null; rm -rf .coverage 2>/dev/null; mv .coverage.tmp .coverage 2>/dev/null || true' EXIT INT TERM; \
	$(VENV_DIR)/bin/pytest --cov=src/antipasta --cov-branch --cov-report=term-missing --cov-report=html -p no:cacheprovider; \
	mv .coverage/.coverage .coverage 2>/dev/null || true

check: lint type-check test  ## Run all quality checks (lint, type-check, test)

check-ci: install-dev  ## Run CI parity checks in isolated tox environments
	$(TOX) run

# Antipasta report and threshold-gate targets

metrics: install  ## Report source metrics and fail on threshold violations
	$(ANTIPASTA) report src/ --format table --fail-on

metrics-quiet: install  ## Gate source metrics without progress output, retaining diagnostics
	@$(ANTIPASTA) report src/ --format table --fail-on --quiet

metrics-json: install  ## Emit a JSON snapshot and fail on threshold violations
	@$(ANTIPASTA) report src/ --format json --fail-on

install-hooks: install-dev  ## Install pre-commit hooks
	$(PRE_COMMIT) install

metrics-report: install  ## Show source overview and module statistics, then enforce thresholds
	$(ANTIPASTA) report src/ --format table
	$(ANTIPASTA) report src/ --format table --by module --fail-on

self-check: install  ## Enforce configured thresholds on antipasta's own source code
	$(ANTIPASTA) report src/antipasta --format table --fail-on

TREEMAP_METRIC ?= sloc
TREEMAP_OUTPUT ?= INTERNAL/treemap_loc.html

treemap: install-dev  ## Generate Plotly treemap for src (override METRIC=loc|sloc|lloc)
	$(PYTHON) INTERNAL/treemap_loc.py --root src --metric $(TREEMAP_METRIC) --output $(TREEMAP_OUTPUT)

check-all: check metrics-quiet  ## Run all checks including complexity metrics

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

clean-tox:  ## Remove tox-managed virtual environments
	rm -rf .tox

# Build targets

build: clean venv  ## Build distribution packages
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

build-check: build  ## Build and validate distribution packages
	$(PYTHON) -m pip install --upgrade check-wheel-contents
	$(VENV_DIR)/bin/check-wheel-contents dist/*.whl

release-dry-run: build-check  ## Build and show distribution packages without uploading
	@echo "Files that will be uploaded:"
	@ls -la dist/
