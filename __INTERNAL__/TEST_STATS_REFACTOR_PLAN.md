# Test Stats Refactoring Plan

## Overview
This document provides a detailed plan to refactor the 797-line `tests/unit/cli/test_stats.py` file into smaller, more manageable test modules. This refactoring will improve maintainability, reduce context bloat for AI agents, and enable parallel test execution.

## Current State Analysis

### File Statistics
- **Current file**: `tests/unit/cli/test_stats.py`
- **Lines of code**: 797
- **Test classes**: 5
- **Shared fixtures**: 1 main fixture (`temp_project_dir`)

### Current Structure
```
test_stats.py
├── Imports and fixtures (lines 1-50)
├── TestUnlimitedDepthFeature (TICKET-STATS-001)
├── TestMetricInclusionLogic (TICKET-STATS-002)
├── TestPathDisplayStyles (TICKET-STATS-003)
├── TestFeatureInteractions (cross-feature tests)
└── TestEdgeCasesAndErrors (edge cases)
```

## Target State

### New Directory Structure
```
tests/unit/cli/stats/
├── __init__.py                      # Empty file for Python package
├── conftest.py                      # Shared fixtures and utilities
├── test_stats_depth.py              # ~150 lines - Depth feature tests
├── test_stats_metrics.py            # ~150 lines - Metric inclusion tests
├── test_stats_path_display.py       # ~150 lines - Path display tests
├── test_stats_interactions.py       # ~200 lines - Feature interaction tests
└── test_stats_edge_cases.py        # ~150 lines - Edge cases and errors
```

## Implementation Steps

### Step 1: Create Directory Structure
```bash
mkdir -p tests/unit/cli/stats
touch tests/unit/cli/stats/__init__.py
```

### Step 2: Extract Shared Components to conftest.py

Create `tests/unit/cli/stats/conftest.py` with:
- The `temp_project_dir` fixture
- Any shared imports
- Common test utilities if present

### Step 3: Split Test Classes

Each test class becomes its own file with appropriate imports:

#### test_stats_depth.py
- Contains: `TestUnlimitedDepthFeature` class
- Purpose: Tests for `--depth 0` unlimited traversal
- Estimated size: ~150 lines

#### test_stats_metrics.py
- Contains: `TestMetricInclusionLogic` class
- Purpose: Tests for metric inclusion/exclusion logic
- Estimated size: ~150 lines

#### test_stats_path_display.py
- Contains: `TestPathDisplayStyles` class
- Purpose: Tests for relative/parent/full path display styles
- Estimated size: ~150 lines

#### test_stats_interactions.py
- Contains: `TestFeatureInteractions` class
- Purpose: Tests for interactions between features
- Estimated size: ~200 lines

#### test_stats_edge_cases.py
- Contains: `TestEdgeCasesAndErrors` class
- Purpose: Edge cases and error conditions
- Estimated size: ~150 lines

### Step 4: Update Imports

Each new test file will need these imports at minimum:
```python
from pathlib import Path
import pytest
from click.testing import CliRunner
from antipasta.cli.stats import stats
```

Additional imports as needed based on specific test requirements.

### Step 5: Verification

Run comprehensive tests to ensure nothing broke:
```bash
# Count tests before refactoring
pytest tests/unit/cli/test_stats.py --collect-only | grep "test session starts" -A 1

# Count tests after refactoring
pytest tests/unit/cli/stats/ --collect-only | grep "test session starts" -A 1

# Run all tests to ensure they pass
pytest tests/unit/cli/stats/ -v

# Check coverage is maintained
pytest tests/unit/cli/stats/ --cov=src/antipasta/cli/stats --cov-report=term-missing
```

### Step 6: Cleanup
```bash
# After verification passes
rm tests/unit/cli/test_stats.py
```

## Automated Refactoring Script

Below is a Python script that automates this refactoring. Save as `refactor_test_stats.py` and run from the project root.

```python
#!/usr/bin/env python3
"""
Refactoring script to split test_stats.py into smaller test modules.
Run from project root: python refactor_test_stats.py
"""

import re
import shutil
from pathlib import Path
from typing import List, Tuple

def extract_imports_and_fixtures(content: str) -> Tuple[str, str]:
    """Extract imports and fixtures from the original file."""
    lines = content.split('\n')

    # Find where the first test class starts
    first_class_idx = next(
        (i for i, line in enumerate(lines) if line.startswith('class Test')),
        len(lines)
    )

    # Everything before the first class is imports/fixtures
    header_content = '\n'.join(lines[:first_class_idx])

    # Extract fixture definitions
    fixture_pattern = r'(@pytest\.fixture.*?(?=\n@pytest\.fixture|\nclass |\Z))'
    fixtures = re.findall(fixture_pattern, header_content, re.DOTALL)

    # Get imports (lines that start with import or from)
    imports = []
    for line in lines[:first_class_idx]:
        if line.startswith(('import ', 'from ')) or line.startswith('"""'):
            imports.append(line)
        elif line and not line.startswith('#') and '"""' in line:
            imports.append(line)

    return '\n'.join(imports), '\n'.join(fixtures)

def extract_test_class(content: str, class_name: str) -> str:
    """Extract a specific test class from the content."""
    pattern = rf'(class {class_name}:.*?)(?=\nclass |\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1)
    return ""

def create_conftest(imports: str, fixtures: str, output_dir: Path) -> None:
    """Create conftest.py with shared fixtures."""
    conftest_content = f'''"""Shared fixtures and utilities for stats tests."""

{imports}


{fixtures}
'''

    conftest_path = output_dir / 'conftest.py'
    conftest_path.write_text(conftest_content)
    print(f"Created: {conftest_path}")

def create_test_file(
    class_name: str,
    class_content: str,
    output_file: str,
    output_dir: Path,
    description: str
) -> None:
    """Create a test file with the given class content."""

    # Base imports that every test file needs
    base_imports = """\"\"\"{}\"\"\"

from pathlib import Path

import pytest
from click.testing import CliRunner

from antipasta.cli.stats import stats""".format(description)

    # Add MAX_DEPTH import if needed
    if 'MAX_DEPTH' in class_content:
        base_imports += ", MAX_DEPTH"

    file_content = f'''{base_imports}


{class_content}
'''

    file_path = output_dir / output_file
    file_path.write_text(file_content)
    print(f"Created: {file_path}")

def main():
    """Main refactoring logic."""

    # Paths
    original_file = Path('tests/unit/cli/test_stats.py')
    output_dir = Path('tests/unit/cli/stats')

    if not original_file.exists():
        print(f"Error: {original_file} not found!")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / '__init__.py').touch()
    print(f"Created directory: {output_dir}")

    # Read original content
    content = original_file.read_text()

    # Extract shared components
    imports, fixtures = extract_imports_and_fixtures(content)

    # Create conftest.py
    create_conftest(imports, fixtures, output_dir)

    # Define test classes to extract
    test_files = [
        ('TestUnlimitedDepthFeature', 'test_stats_depth.py',
         'Tests for unlimited depth traversal feature.'),
        ('TestMetricInclusionLogic', 'test_stats_metrics.py',
         'Tests for metric inclusion logic.'),
        ('TestPathDisplayStyles', 'test_stats_path_display.py',
         'Tests for path display styles.'),
        ('TestFeatureInteractions', 'test_stats_interactions.py',
         'Tests for feature interactions.'),
        ('TestEdgeCasesAndErrors', 'test_stats_edge_cases.py',
         'Tests for edge cases and error conditions.'),
    ]

    # Extract and create each test file
    for class_name, file_name, description in test_files:
        class_content = extract_test_class(content, class_name)
        if class_content:
            create_test_file(
                class_name,
                class_content,
                file_name,
                output_dir,
                description
            )
        else:
            print(f"Warning: Could not find class {class_name}")

    print("\n✅ Refactoring complete!")
    print("\nNext steps:")
    print("1. Run: pytest tests/unit/cli/stats/ -v")
    print("2. Verify all tests pass")
    print("3. Check test count matches original")
    print("4. If successful, run: rm tests/unit/cli/test_stats.py")

    return 0

if __name__ == '__main__':
    exit(main())
```

## Verification Checklist

After running the refactoring:

- [ ] Directory `tests/unit/cli/stats/` exists
- [ ] File `conftest.py` contains the shared fixture
- [ ] All 5 test files created successfully
- [ ] Test count matches original (run pytest --collect-only)
- [ ] All tests pass (pytest tests/unit/cli/stats/ -v)
- [ ] Coverage maintained (pytest with --cov flag)
- [ ] Original test_stats.py can be safely removed

## Benefits

### For AI Agents
- **75% context reduction**: From 797 lines to ~150-200 lines per file
- **Focused context**: Agent working on depth features doesn't see metric logic
- **Faster processing**: Less tokens to process = faster responses

### For Developers
- **Better organization**: Clear separation of concerns
- **Easier navigation**: Find specific tests quickly
- **Parallel execution**: Can run test files in parallel with pytest-xdist
- **Reduced merge conflicts**: Changes isolated to specific feature files

### For CI/CD
- **Granular test runs**: Can run subset of tests based on changed features
- **Better failure isolation**: Failures clearly tied to specific features
- **Improved performance**: Parallel test execution reduces CI time

## Rollback Plan

If issues arise, the refactoring can be reversed:

```bash
# Concatenate all test files back into one
cat tests/unit/cli/stats/test_stats_*.py > tests/unit/cli/test_stats_temp.py

# Add imports and fixtures from conftest at the top
cat tests/unit/cli/stats/conftest.py tests/unit/cli/test_stats_temp.py > tests/unit/cli/test_stats.py

# Remove the stats directory
rm -rf tests/unit/cli/stats/

# Verify original tests work
pytest tests/unit/cli/test_stats.py -v
```

## Implementation Notes

1. **Fixture Scope**: The `temp_project_dir` fixture should maintain its current scope in conftest.py
2. **Import Order**: Ensure imports are organized (stdlib → third-party → local)
3. **Test Discovery**: Pytest will automatically discover all test files in the stats/ directory
4. **Coverage Config**: May need to update .coveragerc if it has specific path configurations

## Success Criteria

The refactoring is successful when:
1. All original tests pass in the new structure
2. Test count remains the same: **30 tests** (current count in test_stats.py)
3. Code coverage remains the same or improves (baseline: tests cover src/antipasta/cli/stats.py)
4. Each new file is under 500 lines (current: 797 lines ÷ 5 files ≈ 160 lines each)
5. No test logic has been altered (only reorganized)

### Current Baseline Metrics
- **Total tests in test_stats.py**: 30
- **Lines of code**: 797
- **Test execution time**: ~63 seconds
- **Test classes**: 5 (one per planned file)
- **Expected lines per new file**: ~150-200 lines (well under 500 line limit)