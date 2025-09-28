# Naming Change Log - 2024-01-24

## Project Rebranding: ccguard → antipasta

### Summary
The project has been rebranded from "ccguard" to "antipasta" across all documentation and code.

### Changes Made

1. **Package Name**: `ccguard` → `antipasta` (Python package naming convention)
2. **CLI Command**: `ccguard-metrics` → `antipasta` (with subcommands)
3. **Configuration File**: `.ccguard.metrics.yaml` → `.antipasta.yaml`
4. **Hook Commands**: `ccguard-claude-hook` → `antipasta-claude-hook`

### Files Modified
- `main.py` - All references to ccguard in comments and strings
- `test_main.py` - Test file documentation and config file references
- `TICKET_LIST.md` - CLI command names and config file names
- `PLANNING/directory-structure.md` - Package structure and examples
- `PLANNING/implementation-questions.md` - References in decisions

### CLI Structure
The new CLI uses a single entry point with subcommands:
- `antipasta metrics --files src/*.py` (analyze metrics)
- `antipasta validate-config .antipasta.yaml` (validate configuration)

### Rationale
- Shorter, more memorable name
- Clearer brand identity
- Aligns with the "cop" metaphor for enforcement

### Notes
- No backwards compatibility needed as this is a greenfield project
- JSON config format is being replaced with YAML as part of this change