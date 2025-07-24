# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**code-cop** is a code quality enforcement tool that analyzes code complexity metrics. It's designed to work as a CLI tool with future support for git hooks and pre-commit integration.

### Current State

- Working prototype in `main.py` that functions as a Claude Code hook
- Analyzes Python code using Radon, with heuristic fallback for JS/TS
- Uses JSON config (`.code_cop.config.json`)

### Target Architecture

- Modular Python package (`code_cop/`)
- CLI-first design: `code-cop metrics`, `code-cop validate-config`
- YAML configuration (`.code_cop.yaml`)
- Extensible plugin architecture for language runners

## Development Commands

```bash
# Set up development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest
pytest tests/unit/test_main.py::TestLoadConfig::test_load_config_defaults  # Single test

# Lint and format (when set up)
ruff check .
black .
mypy .
```

## Architecture Decisions

### Modular Structure

The codebase is being refactored from a monolithic script to a modular package:

- `code_cop/core/` - Language-agnostic business logic
- `code_cop/runners/` - Language-specific metric runners (Radon, Complexipy)
- `code_cop/cli/` - Command-line interface
- `code_cop/hooks/` - Adapters for various hook systems

### Configuration Format

Moving from JSON to YAML for better readability and language-specific settings:

```yaml
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
```

### Python-First Implementation

Initial focus is Python-only with:

- Radon for traditional metrics (cyclomatic complexity, maintainability index)
- Complexipy for cognitive complexity
- Pathspec for .gitignore support

TypeScript/JavaScript support is designed but deferred.

## Key Implementation Files

- `TICKET_LIST.md` - Feature requirements broken into implementation tickets
- `PLANNING/implementation-questions.md` - Architecture decisions and rationale
- `PLANNING/directory-structure.md` - Target package structure
- `main.py` - Current working prototype (to become `code_cop/hooks/claude.py`)

## Metric Definitions

**Cyclomatic Complexity**: Number of linearly independent paths through code
**Cognitive Complexity**: Measure of how difficult code is to understand
**Maintainability Index**: Combined score (0-100) based on complexity, volume, and LOC
**Halstead Metrics**: Token-based complexity measures (volume, difficulty, effort)

## Development Approach

1. Build "steel thread" - minimal working implementation
2. Use modern Python tooling (pyproject.toml, hatchling, ruff, black, mypy)
3. Test-driven development with pytest
4. Focus on correctness over performance initially
5. Design for extensibility to support multiple languages
