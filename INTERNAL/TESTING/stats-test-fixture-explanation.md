# Stats Test Fixture Design

## Overview

The `temp_project_dir` fixture in `tests/unit/cli/test_stats.py` creates a lightweight, synthetic directory structure for testing the stats command features without requiring real source files.

## Fixture Implementation

```python
@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with nested Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "test_project"
        base.mkdir()

        # Creates 4-level deep structure
        # Returns Path object to base directory
        yield base
        # Auto-cleanup after test
```

## Directory Structure Created

```
test_project/
├── main.py              # Root level files
├── utils.py
├── cli/                 # Level 1
│   ├── commands.py
│   ├── options.py
│   └── subcommands/     # Level 2
│       └── analyze.py
└── core/                # Level 1
    ├── engine.py
    ├── config.py
    └── modules/         # Level 2
        ├── parser.py
        └── validators/  # Level 3
            ├── rules.py
            └── builtin/ # Level 4
                └── basic.py
```

## Why This Approach?

### Advantages Over Copying Real Files

1. **Speed**: Creating 10 tiny files (~50 bytes each) vs copying 48 real files (~200KB total)
2. **Isolation**: Each test gets a fresh, predictable structure
3. **Maintainability**: Test data is defined in the test file itself
4. **No .gitignore issues**: Temp directories aren't subject to project .gitignore rules
5. **Predictable paths**: Known directory names for test assertions

### File Content Strategy

Each Python file contains minimal but valid code:
- Simple functions with basic control flow (if/for statements)
- Just enough complexity for metrics analysis
- No imports or dependencies
- Total fixture creation time: ~10ms

## Usage Patterns

### Pattern 1: Full Project Structure
```python
def test_depth_levels(temp_project_dir):
    # temp_project_dir is the base Path
    result = runner.invoke(stats, [
        "-d", str(temp_project_dir),
        "--by-directory",
        "--depth", "2"
    ])
```

### Pattern 2: Isolated Filesystem
For simpler tests that don't need deep nesting:
```python
def test_metrics(self, temp_project_dir):
    with runner.isolated_filesystem():
        # Create minimal structure inline
        Path("cli").mkdir()
        Path("cli/test.py").write_text("def f(): pass")

        result = runner.invoke(stats, ["-p", "cli/*.py"])
```

## Test Coverage Achieved

This fixture enables testing of:
- **Depth traversal**: All levels from 1 to unlimited (0)
- **Path styles**: Relative, parent, and full path display
- **Metric selection**: LOC, cyclomatic, cognitive, Halstead
- **Feature interactions**: All combinations of the above

## Lessons Learned

1. **Absolute paths cause issues**: The `Path.glob()` method doesn't support absolute patterns, requiring `os.chdir()` workarounds
2. **Truncation happens at display**: Even with `--path-style full`, very long temp paths may still truncate for readability
3. **Simple is sufficient**: Basic Python constructs provide enough complexity for metrics testing

## Future Improvements

- Consider creating a shared fixture factory for different project structures
- Add fixture variants for testing edge cases (empty dirs, non-Python files)
- Cache fixture creation for test suite performance (if needed)

---

*Created: 2025-01-21*
*Purpose: Document the design decisions behind the stats command test fixtures*