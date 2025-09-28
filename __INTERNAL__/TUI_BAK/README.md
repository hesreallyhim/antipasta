# TUI Feature Backup

This directory contains the Terminal UI (TUI) feature that was deferred from the v1.0.0 release.

## Contents

- `terminal/` - Complete terminal module with dashboard and widgets
- `cli/tui.py` - CLI command handler for TUI
- `terminal/dashboard.tcss` - Textual CSS styling (inside terminal/)

## Restoration Instructions

To restore the TUI feature to the main codebase:

### 1. Move files back to source tree

```bash
# From project root
mv TUI_BAK/terminal src/antipasta/
mv TUI_BAK/cli/tui.py src/antipasta/cli/
```

### 2. Add Textual dependency

Edit `pyproject.toml` and add to dependencies:
```toml
"textual>=0.70.0",
```

### 3. Re-enable TUI command

Edit `src/antipasta/cli/main.py`:

Add import:
```python
from antipasta.cli.tui import tui as tui_cmd
```

Add command:
```python
cli.add_command(tui_cmd, name="tui")
```

### 4. Update documentation

Add back the TUI section to README.md with command documentation.

### 5. Test the restoration

```bash
# Reinstall with new dependencies
pip install -e .

# Test the TUI command
antipasta tui --help
antipasta tui
```

## Implementation Status

The TUI was fully implemented with:
- ✅ Interactive file tree navigation
- ✅ Real-time metrics display
- ✅ Keyboard shortcuts
- ✅ Command palette
- ✅ Filter system
- ✅ Multiple widgets (overview, heatmap, details)
- ✅ Focus management
- ✅ Terminal cleanup handling

## Notes

- All code is preserved as-is from the last working state
- The TUI was tested and functional before removal
- Consider making it an optional/plugin feature in future releases