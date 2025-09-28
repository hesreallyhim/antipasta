# TUI Feature Migration Log

**Date**: 2025-09-21
**Decision**: Defer TUI feature from v1.0.0 release

## Summary

The Terminal UI (TUI) feature is being temporarily removed from the v1.0.0 release to focus on core functionality and CLI commands. The TUI code will be preserved in a backup directory for potential future development.

## Rationale

1. **Scope Management**: The v1.0.0 release should focus on core metrics analysis functionality
2. **Dependency Reduction**: Removing Textual dependency simplifies installation and reduces package size
3. **Development Focus**: Allows concentration on perfecting CLI commands and core engine
4. **Future Option**: TUI can be reintroduced in a v1.1.0 or v2.0.0 release when mature

## Migration Details

### Components Being Moved

1. **Main TUI Module**: `src/antipasta/terminal/` directory containing:
   - Dashboard application (`dashboard.py`)
   - Data bridge for metrics integration (`data_bridge.py`)
   - Focus and filter management
   - All widget components (file tree, metrics overview, heatmap, etc.)
   - Terminal cleanup utilities
   - Keyboard shortcuts system

2. **CLI Integration**: `src/antipasta/cli/tui.py` command handler

3. **Styling**: `dashboard.tcss` Textual CSS file

4. **Test Fixtures**: TUI code copies in test fixtures (for clarity)

### Preservation Strategy

All TUI code is being moved to `TUI_BAK/` directory at project root:
- Complete terminal module preserved as-is
- CLI command preserved for easy reintegration
- Styling and configuration preserved
- Can be easily restored by moving files back and re-adding dependency

### Changes to Main Codebase

1. **Dependencies**: Removed `textual>=0.70.0` from `pyproject.toml`
2. **CLI**: Removed TUI command from main CLI group
3. **Documentation**: Updated README to remove TUI references
4. **Git**: Added `TUI_BAK/` to `.gitignore` to keep backup local

## Implementation Timeline

- **Phase 1** (Jan 27): Initial TUI implementation completed
  - Base dashboard, widgets, data bridge
  - Interactive features, keyboard shortcuts
  - Command palette and filtering

- **Phase 2** (Sep 21): Migration decision
  - Move to backup directory
  - Remove from public API
  - Focus on v1.0.0 core features

- **Future**: Potential reintroduction
  - After v1.0.0 stabilization
  - With enhanced features and performance
  - Possibly as optional plugin/extension

## Technical Notes

### File Organization in TUI_BAK

```
TUI_BAK/
├── terminal/          # Complete terminal module
├── cli/
│   └── tui.py        # CLI command handler
├── dashboard.tcss    # Textual styling
└── README.md         # Restoration instructions
```

### Restoration Process

To restore the TUI feature:
1. Move `TUI_BAK/terminal/` back to `src/antipasta/`
2. Move `TUI_BAK/cli/tui.py` back to `src/antipasta/cli/`
3. Move `TUI_BAK/dashboard.tcss` to appropriate location
4. Add `textual>=0.70.0` back to dependencies
5. Re-add TUI command to CLI in `main.py`
6. Update documentation

## Lessons Learned

1. **Feature Creep**: TUI added significant complexity for v1.0.0
2. **Dependency Weight**: Textual is a large dependency for optional feature
3. **Core First**: Better to perfect core functionality before UI layers
4. **Modular Design**: Clean separation made this migration straightforward

## Related Documents

- `INTERNAL/PLANNING/DASHBOARD/terminal-dashboard-design.md` - Original design
- `INTERNAL/PLANNING/DASHBOARD/terminal-dashboard-tickets.md` - Implementation tickets
- `INTERNAL/LOGS/2025-01-27-terminal-dashboard-*.md` - Implementation logs