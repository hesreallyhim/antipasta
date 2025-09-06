# Planning Documents

This directory contains all planning and design documents for the antipasta project.

## Documents (in reading order)

1. **[implementation-questions.md](implementation-questions.md)** - Key decisions and rationale for the project architecture
2. **[directory-structure.md](directory-structure.md)** - Detailed package structure and organization
3. **[implementation-handoff.md](implementation-handoff.md)** - Comprehensive guide for implementing the project

## Quick Reference

- **Project Name**: antipasta (Python package: `antipasta`)
- **CLI Command**: `antipasta` with subcommands
- **Config File**: `.antipasta.yaml` (YAML format)
- **Initial Scope**: Python-only implementation
- **Build System**: pyproject.toml with hatchling

## Key Decisions

- CLI-first approach (no hooks initially)
- YAML configuration only
- Modern Python tooling (ruff, black, mypy)
- Focus on Python metrics first
- Extensible plugin architecture for future languages