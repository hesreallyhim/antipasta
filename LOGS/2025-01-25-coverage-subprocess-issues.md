# Coverage and Subprocess Testing Issues

**Date**: January 25, 2025
**Context**: Fixing test failures and coverage measurement issues

## Problem Summary

We encountered a complex issue where:
1. Tests were failing due to temporary test files being incorrectly ignored
2. Coverage measurement was creating dozens of `.coverage.*` files
3. Coverage was failing with "Can't combine statement coverage data with branch data"

## Root Causes

### 1. Path Handling in LanguageDetector

The `should_ignore` method was matching gitignore patterns like `tmp/` against absolute paths containing `/tmp/`. This caused test files in pytest's temporary directories to be ignored, breaking tests.

**Example**: Pattern `tmp/` was matching `/var/folders/.../tmp.../test.py`

### 2. Coverage in Subprocesses

The RadonRunner uses `subprocess.run()` to execute Radon CLI commands. When coverage was enabled:
- Each subprocess inherited the coverage environment
- Each subprocess created its own `.coverage.*` file
- Some subprocesses had different coverage settings (no branch coverage)
- pytest-cov tried to combine incompatible coverage data

## Solutions Implemented

### 1. Improved Path Handling

Modified `detector.py` to:
- Distinguish between manual ignore patterns and gitignore patterns
- Only apply gitignore patterns to files within the project directory
- Return `False` for files outside the project when checking gitignore patterns
- Apply manual patterns to all files but use filename-only matching for external files

```python
# Path is outside current directory
if self.ignore_patterns:
    spec = pathspec.PathSpec.from_lines("gitwildmatch", self.ignore_patterns)
    return spec.match_file(file_path.name)
return False
```

### 2. Coverage Configuration

- Removed coverage from default pytest options in `pyproject.toml`
- Modified Makefile to run tests without coverage by default
- Added environment variable to disable coverage in subprocesses
- Created separate `make test-cov` target for explicit coverage runs

```python
# In RadonRunner._run_radon_command
env = os.environ.copy()
env['COVERAGE_CORE'] = ''  # Disable coverage in subprocess
```

## Lessons Learned

### 1. Test Environment Isolation

Tests should work regardless of their location. Using absolute paths for pattern matching can cause unexpected behavior when tests run in temporary directories.

### 2. Coverage and Subprocesses Don't Mix Well

When code spawns subprocesses, coverage measurement becomes complex. Each subprocess may create its own coverage data file, leading to conflicts during combination.

### 3. Default Configuration Matters

Having coverage enabled by default in pytest configuration can cause hard-to-debug issues. It's better to explicitly enable coverage when needed.

## Proactive Measures for the Future

### 1. Design Considerations

- **Avoid subprocess calls when possible**: Consider using Python libraries directly instead of CLI wrappers
- **Use mocking in tests**: Mock subprocess calls to avoid coverage issues and improve test speed
- **Path handling**: Always consider both relative and absolute paths in file operations

### 2. Testing Best Practices

- **Separate coverage runs**: Keep coverage measurement separate from regular test runs
- **Test in isolation**: Ensure tests work regardless of their execution environment
- **Clear error messages**: When paths don't match expectations, provide clear diagnostic output

### 3. Configuration Guidelines

- **Minimal defaults**: Keep default test configuration minimal and explicit
- **Document subprocess behavior**: If using subprocesses, document their interaction with test infrastructure
- **Environment variables**: Be aware of environment variable inheritance in subprocesses

### 4. Alternative Approaches

For the RadonRunner specifically, we could:
- Import and use Radon's Python API directly instead of CLI
- Cache results to avoid repeated subprocess calls
- Use dependency injection to make the runner more testable

## Key Takeaway

Complex test failures often have multiple interacting causes. In this case:
- Path matching issues caused tests to fail
- The fix revealed coverage measurement issues
- Coverage issues were caused by subprocess inheritance

Breaking down the problem systematically and fixing each issue separately was crucial to resolving the complete problem.