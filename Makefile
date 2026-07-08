# Virtual environment configuration
VENV_NAME := venv
VENV_DIR := $(VENV_NAME)
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip
TOX := $(VENV_DIR)/bin/tox

# Release configuration
VERSION_FILE := src/antipasta/__version__.py
CURRENT_VERSION = $(shell grep -oE '[0-9]+\.[0-9]+\.[0-9]+' $(VERSION_FILE))

# Detect OS for activation script
ifeq ($(OS),Windows_NT)
	VENV_ACTIVATE := $(VENV_DIR)/Scripts/activate
	PYTHON := $(VENV_DIR)/Scripts/python
	PIP := $(VENV_DIR)/Scripts/pip
else
	VENV_ACTIVATE := $(VENV_DIR)/bin/activate
endif

.PHONY: install-hooks help venv install install-dev install-prod format lint type-check test test-fast test-fast-clean test-cov check check-ci check-all clean clean-venv clean-cov clean-tox build build-check version-show release-check release-dry-run gh-release-test gh-check-cli release-doctor treemap

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

# Antipasta metrics analysis targets

metrics: install  ## Run antipasta metrics analysis on src/ (verbose)
	@echo "Running complexity analysis on src/..."
	@$(VENV_DIR)/bin/antipasta metrics -d src/ || (echo ""; echo "❌ Code complexity check FAILED"; exit 2)
	@echo ""
	@echo "✅ Code complexity check PASSED"

metrics-quiet: install  ## Run antipasta metrics analysis on src/ (quiet mode - violations only)
	@$(VENV_DIR)/bin/antipasta metrics -d src/ -q || exit 2

metrics-json: install  ## Run antipasta metrics analysis and output JSON
	@$(VENV_DIR)/bin/antipasta metrics -d src/ --format json

install-hooks:  ## Point git at the committed hooks
	@git config core.hooksPath .githooks
	@echo "✅ core.hooksPath -> .githooks"

metrics-report: install  ## Generate detailed metrics report with statistics
	@echo "═══════════════════════════════════════════════════════"
	@echo "         ANTIPASTA METRICS REPORT"
	@echo "═══════════════════════════════════════════════════════"
	@echo ""
	@echo "📊 Overall Statistics:"
	@$(VENV_DIR)/bin/antipasta stats -p "src/**/*.py" -m cyc -m cog -m mai | head -20
	@echo ""
	@echo "📁 Metrics by Module:"
	@$(VENV_DIR)/bin/antipasta stats -p "src/**/*.py" --by-module -m cyc -m cog -m mai
	@echo ""
	@echo "⚠️  Violations:"
	@$(VENV_DIR)/bin/antipasta metrics -d src/ -q 2>&1 | grep -E "^❌" | head -10 || echo "No violations found"
	@echo ""
	@$(VENV_DIR)/bin/antipasta metrics -d src/ -q > /dev/null 2>&1 && echo "✅ PASS: All metrics within thresholds" || echo "❌ FAIL: $(shell $(VENV_DIR)/bin/antipasta metrics -d src/ -q 2>&1 | grep -c '^❌') violations found"

self-check: install  ## Run antipasta on its own source code
	@echo "════════════════════════════════════════════════════════"
	@echo "       ANTIPASTA SELF-CHECK"
	@echo "════════════════════════════════════════════════════════"
	@echo ""
	@$(VENV_DIR)/bin/antipasta metrics -d src/antipasta || (echo ""; echo "⚠️  Some violations detected. Consider refactoring complex code."; exit 1)
	@echo ""
	@echo "✅ All complexity checks passed!"

TREEMAP_METRIC ?= sloc
TREEMAP_OUTPUT ?= treemap_loc.html

treemap: install-dev  ## Generate Plotly treemap for src (override METRIC=loc|sloc|lloc)
	$(PYTHON) treemap_loc.py --root src --metric $(TREEMAP_METRIC) --output $(TREEMAP_OUTPUT)

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

# Build and Release Targets

build: clean venv  ## Build distribution packages
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

build-check: build  ## Build and validate distribution packages
	$(PYTHON) -m pip install --upgrade check-wheel-contents
	$(VENV_DIR)/bin/check-wheel-contents dist/*.whl

# Version and release helpers

version-show:  ## Show current version
	@echo "Current version: $(CURRENT_VERSION)"

release-check:  ## Show the Release Please release checklist
	@echo "Release Checklist:"
	@echo "=================="
	@echo "[ ] CI parity passing (make check-ci)"
	@echo "[ ] PR titles use conventional commits"
	@echo "[ ] Release Please PR version and changelog reviewed"
	@echo "[ ] Publish to PyPI workflow monitored after release PR merge"
	@echo ""
	@echo "Current version: $(CURRENT_VERSION)"
	@echo ""
	@echo "Normal releases are handled by Release Please and GitHub trusted publishing."

release-dry-run: build-check  ## Build and show distribution packages without uploading
	@echo "Files that will be uploaded:"
	@ls -la dist/

gh-check-cli:  ## Check if GitHub CLI is installed
	@which gh > /dev/null 2>&1 || (echo "Error: GitHub CLI (gh) is not installed. Install from: https://cli.github.com/" && exit 1)
	@gh auth status > /dev/null 2>&1 || (echo "Error: Not authenticated with GitHub. Run: gh auth login" && exit 1)

gh-release-test: gh-check-cli  ## Trigger TestPyPI deployment via GitHub Actions
	@echo "Triggering TestPyPI deployment workflow..."
	gh workflow run "Publish to PyPI" \
		--field target=testpypi
	@echo "✅ Workflow triggered! Monitor progress at:"
	@echo "https://github.com/hesreallyhim/antipasta/actions/workflows/publish.yml"
	@echo ""
	@echo "Once deployed, test with:"
	@echo "pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ antipasta"

release-doctor:  ## Check release workflow prerequisites
	@echo "Release Doctor"
	@echo "=============="
	@echo ""
	@echo "Checking GitHub CLI..."
	@which gh > /dev/null 2>&1 && echo "  ✓ GitHub CLI installed" || echo "  ✗ GitHub CLI not found - install from https://cli.github.com/"
	@gh auth status > /dev/null 2>&1 && echo "  ✓ GitHub authenticated" || echo "  ✗ Not authenticated - run: gh auth login"
	@echo ""
	@echo "Checking Git state..."
	@git diff --quiet HEAD 2>/dev/null && echo "  ✓ No uncommitted changes" || echo "  ⚠ Uncommitted changes detected"
	@git diff --quiet --cached 2>/dev/null && echo "  ✓ No staged changes" || echo "  ⚠ Staged changes detected"
	@echo "  Current branch: $$(git rev-parse --abbrev-ref HEAD)"
	@[ "$$(git rev-parse --abbrev-ref HEAD)" = "main" ] && echo "  ✓ On main branch" || echo "  ⚠ Not on main branch"
	@echo ""
	@echo "Checking versions..."
	@echo "  Current version: $(CURRENT_VERSION)"
	@LATEST_PYPI_VERSION=$$($(PYTHON) -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/antipasta/json', timeout=5))['info']['version'])" 2>/dev/null || echo "unknown"); \
	echo "  Latest PyPI release: $$LATEST_PYPI_VERSION"
	@echo ""
	@echo "Checking Python environment..."
	@echo "  Python: $$($(PYTHON) --version 2>&1 || echo 'not found')"
	@$(PYTHON) -m pip show build > /dev/null 2>&1 && echo "  ✓ build installed" || echo "  ✗ build not installed"
	@$(PYTHON) -m pip show hatchling > /dev/null 2>&1 && echo "  ✓ hatchling installed" || echo "  ℹ hatchling is installed in build isolation when needed"
	@echo ""
	@echo "Checking GitHub repository..."
	@gh repo view --json name,url 2>/dev/null | jq -r '"  Repository: " + .url' || echo "  ✗ Cannot access repository"
	@if gh workflow list 2>/dev/null | grep -q "Release Please"; then \
		echo "  ✓ 'Release Please' workflow found"; \
	else \
		echo "  ✗ 'Release Please' workflow not found"; \
	fi
	@if gh workflow list 2>/dev/null | grep -q "Publish to PyPI"; then \
		echo "  ✓ 'Publish to PyPI' workflow found"; \
	else \
		echo "  ✗ 'Publish to PyPI' workflow not found"; \
	fi
	@echo ""
	@echo "Normal releases are created by merging the Release Please PR."
