# Virtual environment configuration
VENV_NAME := venv
VENV_DIR := $(VENV_NAME)
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

# Release configuration
VERSION_FILE := src/antipasta/__version__.py
CURRENT_VERSION := $(shell grep -oE '[0-9]+\.[0-9]+\.[0-9]+' $(VERSION_FILE))

# Detect OS for activation script
ifeq ($(OS),Windows_NT)
	VENV_ACTIVATE := $(VENV_DIR)/Scripts/activate
	PYTHON := $(VENV_DIR)/Scripts/python
	PIP := $(VENV_DIR)/Scripts/pip
else
	VENV_ACTIVATE := $(VENV_DIR)/bin/activate
endif

.PHONY: help venv install install-dev install-prod format lint type-check test test-fast test-fast-clean test-cov check check-all clean clean-venv clean-cov build build-check version-show version-bump-patch version-bump-minor version-bump-major release-test release release-check release-dry-run gh-release gh-release-draft gh-release-test gh-check-cli release-patch release-minor release-major release-dry-patch release-dry-minor release-dry-major gh-release-dry release-doctor release-safety-check gh-release-safe release-patch-safe release-minor-safe release-major-safe treemap

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
	$(VENV_DIR)/bin/black src/antipasta tests
	$(VENV_DIR)/bin/ruff check --fix src/antipasta tests

lint: install-dev  ## Run linting checks with ruff
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

# Build and Release Targets

build: clean venv  ## Build distribution packages
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

build-check: build  ## Build and check package with twine
	$(PYTHON) -m pip install --upgrade twine
	$(VENV_DIR)/bin/twine check dist/*

# Version management

version-show:  ## Show current version
	@echo "Current version: $(CURRENT_VERSION)"

version-bump-patch:  ## Bump patch version (0.0.X)
	@echo "Bumping patch version from $(CURRENT_VERSION)..."
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	sed -i.bak "s/$(CURRENT_VERSION)/$$NEW_VERSION/g" $(VERSION_FILE) pyproject.toml; \
	rm $(VERSION_FILE).bak pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION"

version-bump-minor:  ## Bump minor version (0.X.0)
	@echo "Bumping minor version from $(CURRENT_VERSION)..."
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1"."$$2+1".0"}'); \
	sed -i.bak "s/$(CURRENT_VERSION)/$$NEW_VERSION/g" $(VERSION_FILE) pyproject.toml; \
	rm $(VERSION_FILE).bak pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION"

version-bump-major:  ## Bump major version (X.0.0)
	@echo "Bumping major version from $(CURRENT_VERSION)..."
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1+1".0.0"}'); \
	sed -i.bak "s/$(CURRENT_VERSION)/$$NEW_VERSION/g" $(VERSION_FILE) pyproject.toml; \
	rm $(VERSION_FILE).bak pyproject.toml.bak; \
	echo "Version bumped to $$NEW_VERSION"

# PyPI release targets

release-test: build-check  ## Upload to Test PyPI
	$(VENV_DIR)/bin/twine upload --repository testpypi dist/*

release: build-check  ## Upload to PyPI (production)
	$(VENV_DIR)/bin/twine upload dist/*

release-check:  ## Pre-release checklist
	@echo "Release Checklist:"
	@echo "=================="
	@echo "[ ] All tests passing (make test)"
	@echo "[ ] Code formatted (make format)"
	@echo "[ ] Type checks passing (make type-check)"
	@echo "[ ] Version bumped appropriately"
	@echo "[ ] CHANGELOG.md updated (if exists)"
	@echo "[ ] Git working directory clean"
	@echo "[ ] On correct branch (main/master)"
	@echo ""
	@echo "Current version: $(CURRENT_VERSION)"
	@echo ""
	@echo "Run 'make release-dry-run' to see what will be released"

release-dry-run: build  ## Show what will be released without uploading
	@echo "Files that will be uploaded:"
	@ls -la dist/
	@echo ""
	$(VENV_DIR)/bin/twine check dist/*

# GitHub Release Targets (using GitHub CLI)

gh-check-cli:  ## Check if GitHub CLI is installed
	@which gh > /dev/null 2>&1 || (echo "Error: GitHub CLI (gh) is not installed. Install from: https://cli.github.com/" && exit 1)
	@gh auth status > /dev/null 2>&1 || (echo "Error: Not authenticated with GitHub. Run: gh auth login" && exit 1)

gh-release: gh-check-cli  ## Create and publish a GitHub release (triggers PyPI deployment)
	@echo "Creating GitHub release for version $(CURRENT_VERSION)..."
	@if git rev-parse "v$(CURRENT_VERSION)" >/dev/null 2>&1 || git ls-remote --exit-code --tags origin "refs/tags/v$(CURRENT_VERSION)" >/dev/null 2>&1; then \
		echo "Error: Tag v$(CURRENT_VERSION) already exists. Bump version first."; \
		exit 1; \
	fi
	@echo "Committing version changes..."
	@git add -A
	@git diff --staged --quiet || git commit -m "chore: release v$(CURRENT_VERSION)"
	@echo "Tagging release commit..."
	@git tag -a "v$(CURRENT_VERSION)" -m "v$(CURRENT_VERSION)"
	@git push origin HEAD "v$(CURRENT_VERSION)"
	@echo "Creating release v$(CURRENT_VERSION)..."
	gh release create "v$(CURRENT_VERSION)" \
		--title "v$(CURRENT_VERSION)" \
		--generate-notes \
		--verify-tag
	@echo "✅ Release created! Check the Actions tab for PyPI deployment progress."
	@echo "📦 View on PyPI: https://pypi.org/project/antipasta/$(CURRENT_VERSION)/"

gh-release-draft: gh-check-cli  ## Create a draft GitHub release (does NOT trigger deployment)
	@echo "Creating draft release for version $(CURRENT_VERSION)..."
	@if git rev-parse "v$(CURRENT_VERSION)" >/dev/null 2>&1; then \
		echo "Warning: Tag v$(CURRENT_VERSION) already exists."; \
	fi
	gh release create "v$(CURRENT_VERSION)" \
		--title "v$(CURRENT_VERSION)" \
		--generate-notes \
		--draft \
		--verify-tag
	@echo "📝 Draft release created. Edit and publish at: https://github.com/hesreallyhim/antipasta/releases"

gh-release-test: gh-check-cli  ## Trigger TestPyPI deployment via GitHub Actions
	@echo "Triggering TestPyPI deployment workflow..."
	gh workflow run "Publish to PyPI" \
		--field target=testpypi
	@echo "✅ Workflow triggered! Monitor progress at:"
	@echo "https://github.com/hesreallyhim/antipasta/actions/workflows/publish.yml"
	@echo ""
	@echo "Once deployed, test with:"
	@echo "pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ antipasta"

# Composite release commands

release-patch: version-bump-patch gh-release  ## Bump patch version and create GitHub release
release-minor: version-bump-minor gh-release  ## Bump minor version and create GitHub release
release-major: version-bump-major gh-release  ## Bump major version and create GitHub release

# Dry-run release commands (safe testing)

release-dry-patch: version-show  ## Simulate patch release without making changes
	@echo "DRY RUN: Would bump patch version from $(CURRENT_VERSION)"
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	echo "DRY RUN: New version would be $$NEW_VERSION"; \
	echo "DRY RUN: Would commit with message: 'chore: release v'$$NEW_VERSION"; \
	echo "DRY RUN: Would create tag: v$$NEW_VERSION"; \
	echo "DRY RUN: Would trigger GitHub release and PyPI deployment"

release-dry-minor: version-show  ## Simulate minor release without making changes
	@echo "DRY RUN: Would bump minor version from $(CURRENT_VERSION)"
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1"."$$2+1".0"}'); \
	echo "DRY RUN: New version would be $$NEW_VERSION"; \
	echo "DRY RUN: Would commit with message: 'chore: release v'$$NEW_VERSION"; \
	echo "DRY RUN: Would create tag: v$$NEW_VERSION"; \
	echo "DRY RUN: Would trigger GitHub release and PyPI deployment"

release-dry-major: version-show  ## Simulate major release without making changes
	@echo "DRY RUN: Would bump major version from $(CURRENT_VERSION)"
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1+1".0.0"}'); \
	echo "DRY RUN: New version would be $$NEW_VERSION"; \
	echo "DRY RUN: Would commit with message: 'chore: release v'$$NEW_VERSION"; \
	echo "DRY RUN: Would create tag: v$$NEW_VERSION"; \
	echo "DRY RUN: Would trigger GitHub release and PyPI deployment"

gh-release-dry: gh-check-cli  ## Simulate GitHub release creation
	@echo "DRY RUN: Simulating GitHub release for version $(CURRENT_VERSION)"
	@echo "----------------------------------------"
	@if git rev-parse "v$(CURRENT_VERSION)" >/dev/null 2>&1; then \
		echo "❌ ERROR: Tag v$(CURRENT_VERSION) already exists - release would fail!"; \
		echo "   Existing tag points to: $$(git rev-parse --short v$(CURRENT_VERSION))"; \
		exit 1; \
	else \
		echo "✓ Tag v$(CURRENT_VERSION) does not exist - release would proceed"; \
	fi
	@echo "✓ Would add and commit any staged changes"
	@echo "✓ Would push to origin"
	@echo "✓ Would create GitHub release v$(CURRENT_VERSION)"
	@echo "✓ Would trigger 'Publish to PyPI' workflow"
	@echo "✓ Package would be available at: https://pypi.org/project/antipasta/$(CURRENT_VERSION)/"

# Release health check and safety commands

release-doctor:  ## Check all release prerequisites and system health
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║           Release Doctor - System Health Check            ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📋 Checking GitHub CLI..."
	@which gh > /dev/null 2>&1 && echo "  ✓ GitHub CLI installed" || echo "  ✗ GitHub CLI not found - install from https://cli.github.com/"
	@gh auth status > /dev/null 2>&1 && echo "  ✓ GitHub authenticated" || echo "  ✗ Not authenticated - run: gh auth login"
	@echo ""
	@echo "📋 Checking Git state..."
	@git diff --quiet HEAD 2>/dev/null && echo "  ✓ No uncommitted changes" || echo "  ⚠ Uncommitted changes detected"
	@git diff --quiet --cached 2>/dev/null && echo "  ✓ No staged changes" || echo "  ⚠ Staged changes detected"
	@echo "  📍 Current branch: $$(git rev-parse --abbrev-ref HEAD)"
	@[ "$$(git rev-parse --abbrev-ref HEAD)" = "main" ] && echo "  ✓ On main branch" || echo "  ⚠ Not on main branch"
	@echo ""
	@echo "📋 Checking versions..."
	@echo "  📌 Current version: $(CURRENT_VERSION)"
	@LATEST_PYPI_VERSION=$$($(PYTHON) -c "import json,urllib.request; print(json.load(urllib.request.urlopen('https://pypi.org/pypi/antipasta/json', timeout=5))['info']['version'])" 2>/dev/null || echo "unknown"); \
	echo "  📦 Latest PyPI release: $$LATEST_PYPI_VERSION"
	@NEW_VERSION=$$(echo $(CURRENT_VERSION) | awk -F. '{print $$1"."$$2"."$$3+1}'); \
	echo "  🚀 Next patch version: $$NEW_VERSION"
	@if git describe --tags --abbrev=0 2>/dev/null; then \
		echo "  🏷️  Latest git tag: $$(git describe --tags --abbrev=0)"; \
	else \
		echo "  🏷️  Latest git tag: none"; \
	fi
	@echo ""
	@echo "📋 Checking Python environment..."
	@echo "  🐍 Python: $$($(PYTHON) --version 2>&1 || echo 'not found')"
	@$(PYTHON) -m pip show build > /dev/null 2>&1 && echo "  ✓ build installed" || echo "  ✗ build not installed"
	@$(PYTHON) -m pip show twine > /dev/null 2>&1 && echo "  ✓ twine installed" || echo "  ✗ twine not installed"
	@$(PYTHON) -m pip show hatch > /dev/null 2>&1 && echo "  ✓ hatch installed" || echo "  ✗ hatch not installed"
	@echo ""
	@echo "📋 Checking GitHub repository..."
	@gh repo view --json name,url 2>/dev/null | jq -r '"  📍 Repository: " + .url' || echo "  ✗ Cannot access repository"
	@if gh workflow list 2>/dev/null | grep -q "Publish to PyPI"; then \
		echo "  ✓ 'Publish to PyPI' workflow found"; \
	else \
		echo "  ✗ 'Publish to PyPI' workflow not found"; \
	fi
	@echo ""
	@echo "📋 Checking for common issues..."
	@if git rev-parse "v$(CURRENT_VERSION)" >/dev/null 2>&1; then \
		echo "  ⚠ WARNING: Tag v$(CURRENT_VERSION) already exists!"; \
		echo "    You need to bump version before releasing"; \
	else \
		echo "  ✓ Tag v$(CURRENT_VERSION) is available"; \
	fi
	@echo ""
	@echo "════════════════════════════════════════════════════════════"
	@echo "💡 Quick commands:"
	@echo "  • Test release: make release-dry-patch"
	@echo "  • TestPyPI deploy: make gh-release-test"
	@echo "  • Production release: make release-patch"
	@echo "════════════════════════════════════════════════════════════"

release-safety-check:  ## Ensure repository is in a safe state for release
	@echo "🔒 Running pre-release safety checks..."
	@echo ""
	@# Check for uncommitted changes
	@if ! git diff --quiet HEAD 2>/dev/null; then \
		echo "❌ ERROR: Uncommitted changes detected"; \
		echo "   Run 'git status' to see changes"; \
		echo "   Commit or stash changes before releasing"; \
		exit 1; \
	fi
	@# Check for staged changes
	@if ! git diff --quiet --cached 2>/dev/null; then \
		echo "❌ ERROR: Staged changes detected"; \
		echo "   Run 'git status' to see staged files"; \
		echo "   Commit or unstage changes before releasing"; \
		exit 1; \
	fi
	@# Check branch
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "⚠️  WARNING: Not on main branch"; \
		echo "   Current branch: $$(git rev-parse --abbrev-ref HEAD)"; \
		echo "   Consider switching to main branch"; \
	fi
	@# Check if up to date with origin
	@git fetch origin main --quiet 2>/dev/null || true
	@if [ "$$(git rev-parse HEAD)" != "$$(git rev-parse origin/main 2>/dev/null || echo 'no-remote')" ]; then \
		echo "⚠️  WARNING: Local branch differs from origin/main"; \
		echo "   Consider pulling latest changes"; \
	fi
	@echo "✅ All safety checks passed!"
	@echo ""

# Safe release commands with safety checks

gh-release-safe: release-safety-check gh-release  ## Create GitHub release with safety checks
release-patch-safe: release-safety-check release-patch  ## Safe patch release with all checks
release-minor-safe: release-safety-check release-minor  ## Safe minor release with all checks
release-major-safe: release-safety-check release-major  ## Safe major release with all checks
