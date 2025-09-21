# Stats Command Improvements - Implementation Tickets

## Overview
This document contains three implementation tickets for improving the `antipasta stats` command's user experience and functionality. These tickets address depth control, metric inclusion logic, and path display formatting.

## CRITICAL IMPLEMENTATION NOTES
1. **Test all changes before committing** - Run the test commands provided in each ticket
2. **Preserve backward compatibility** - Existing behavior without flags must remain unchanged
3. **Import statements needed**: The stats.py file already has all required imports at the top
4. **Working directory**: All paths are relative to `/Users/hesreallyhim/coding/projects/antipasta/`

---

## TICKET-STATS-001: Implement Unlimited Depth Option with Safety Boundary

### Summary
Add support for `--depth 0` to mean "unlimited" directory traversal while implementing a reasonable maximum boundary (e.g., 20 levels) to prevent infinite recursion or performance issues.

### Current Buggy Behavior
```bash
# Currently, --depth only accepts 1, 2, 3, etc.
# There's no way to see ALL subdirectories at once
# Users must guess the maximum depth they need
```

### Acceptance Criteria
1. `--depth 0` should traverse all directories up to MAX_DEPTH (20) levels
2. `--depth` continues to accept positive integers for specific depth limits
3. Default behavior (`--depth 1`) remains unchanged
4. Help text clearly indicates that 0 means unlimited
5. No infinite recursion or stack overflow on deeply nested directories
6. Performance remains acceptable on large directory trees

### Implementation Details

#### Sub-tasks:
1. **Add MAX_DEPTH constant** (Add after line 35, after METRIC_PREFIXES definition)
   ```python
   # Maximum depth for unlimited traversal (safety boundary)
   MAX_DEPTH = 20
   ```

2. **Update CLI option definition** (Currently at lines 97-101)
   ```python
   @click.option(
       "--depth",
       type=int,
       default=1,
       help="Directory depth to display when using --by-directory (0=unlimited, default: 1)",
   )
   ```

3. **Modify _collect_directory_stats function** (Line 312)
   - Current signature at line 312-314:
   ```python
   def _collect_directory_stats(
       reports: list[Any], metrics_to_include: list[str], base_dir: Path, depth: int
   ) -> dict[str, Any]:
   ```
   - Add after the docstring (around line 323):
   ```python
   # Handle unlimited depth with safety boundary
   effective_depth = MAX_DEPTH if depth == 0 else depth
   ```
   - Replace ALL occurrences of `depth` with `effective_depth` in the function
   - Specifically update line 407 from:
   ```python
   if dir_depth >= depth:
   ```
   to:
   ```python
   if dir_depth >= effective_depth:
   ```

4. **Update _generate_all_reports function** (Line 768)
   - Current call at line 777:
   ```python
   dir_stats = _collect_directory_stats(reports, metrics, Path("."), 1)  # Default depth of 1
   ```
   - Keep as is (depth=1 is still the default for the "all" format)

5. **Add tests**
   - Test depth=0 with shallow directory structure
   - Test depth=0 with deep directory structure (>20 levels)
   - Test that depth=1, 2, 3 still work as before

### Context & References
- **Primary file**: `/src/antipasta/cli/stats.py`
- **Function to modify**: `_collect_directory_stats` (starts around line 312)
- **Current behavior**: Depth is directly used as limit, no concept of unlimited
- **Related PR**: Recent fix for hierarchical aggregation in --by-directory

### Test Commands for Validation
```bash
# Test 1: Verify depth=0 works (should show all levels up to 20)
antipasta stats -d src --by-directory --depth 0

# Test 2: Verify depth=1 still works (default, show only top level)
antipasta stats -d src --by-directory --depth 1

# Test 3: Verify depth=2 still works
antipasta stats -d src --by-directory --depth 2

# Expected output for depth=0 should include:
# - src/antipasta (top level)
# - src/antipasta/cli
# - src/antipasta/core
# - src/antipasta/runners
# - src/antipasta/runners/python (deeper level)
# - src/antipasta/terminal/widgets (even deeper)
```

### Edge Cases to Consider
- Empty directories at various depths
- Symbolic links that might create cycles - **NOTE: MAX_DEPTH is sufficient protection, no special handling needed**
- Very deep directory structures (>20 levels) - **NOTE: No warning message needed, silent truncation at MAX_DEPTH is acceptable**
- Single file at root with no directories

### Additional Clarifications
- **Depth comparison**: Keep the current `>=` logic. This is correct: depth=1 shows 1 level, depth=2 shows 2 levels, etc.
- **Testing**: Manual testing with provided commands is sufficient. No new test files needed at this time.
- **Symbolic links**: The MAX_DEPTH boundary provides sufficient protection against cycles. No additional logic needed.

---

## TICKET-STATS-002: Fix Metric Inclusion Logic for Explicit vs Default Behavior

### Summary
Currently, LOC (Lines of Code) metrics are always displayed in stats output, even when users explicitly request other metrics via `-m` flags. This should be changed so LOC is only the default when NO metrics are specified.

### Current Buggy Behavior
```bash
# Currently BROKEN - LOC is ALWAYS shown:
$ antipasta stats -p "src/**/*.py" -m cyc
# Shows BOTH LOC stats AND cyclomatic complexity (wrong!)

# The bug is that file/function counts and LOC are hardcoded to always display
# in _collect_overall_stats, _collect_directory_stats, _collect_module_stats
```

### Acceptance Criteria
1. When NO `-m` flags provided: Show LOC metrics by default
2. When ANY `-m` flags provided: Show ONLY the requested metrics (no implicit LOC)
3. `-m loc` should still work to explicitly request LOC metrics
4. `-m all` should include LOC along with all other metrics
5. Backward compatibility: Existing scripts using no flags still get LOC

### Implementation Details

#### Sub-tasks:
1. **Modify parse_metrics function** (Line 38-70)
   - Function is already correct - returns empty list when no args
   - No changes needed here

2. **Update stats command main logic** (Line 210-211)
   - Current code:
   ```python
   # Parse metrics to include
   metrics_to_include = parse_metrics(metric)
   ```
   - Change to:
   ```python
   # Parse metrics to include
   metrics_to_include = parse_metrics(metric)

   # If no metrics specified, default to LOC metrics
   if not metric:  # If user didn't provide ANY -m flags
       metrics_to_include = [m.value for m in METRIC_PREFIXES["loc"]]
   ```

3. **Update _collect_overall_stats function** (Line 238-310)
   - IMPORTANT: Keep file/function COUNTS (they're always shown)
   - Only conditionally show LOC statistics
   - Current code starting at line 260:
   ```python
   # Collect LOC per file
   file_locs = []
   ```
   - Change to:
   ```python
   # Check if we should collect LOC metrics
   should_collect_loc = any(
       metric in metrics_to_include
       for metric in ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
   )

   # Collect LOC per file (only if requested)
   file_locs = []
   if should_collect_loc:
       # existing LOC collection code...
   ```
   - Update the stats dict creation (lines 287-294) to only include LOC stats if collected

4. **Update _collect_directory_stats function** (Line 312-449)
   - Add same LOC check around line 413:
   ```python
   # Check if we should collect LOC metrics
   should_collect_loc = any(
       metric in metrics_to_include
       for metric in ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
   )

   # Calculate statistics for this directory
   file_locs = []
   if should_collect_loc:
       for report in data["all_files"]:
           # existing LOC collection...
   ```
   - Update results dict (line 435) to conditionally include avg_file_loc and total_loc

5. **Update _collect_module_stats function** (Line 452-511)
   - Apply same pattern as directory stats
   - Add LOC check before line 484 where file_locs is collected

6. **Update _display_table function** (Line 555-643)
   - Check if LOC fields exist before displaying them
   - Around line 572-576, wrap LOC display in:
   ```python
   if "total_loc" in stats_data["files"]:
       click.echo(f"  Total LOC: {stats_data['files']['total_loc']:,}")
       click.echo(f"  Average LOC per file: {stats_data['files']['avg_loc']:.1f}")
       # etc.
   ```

### Context & References
- **Primary file**: `/src/antipasta/cli/stats.py`
- **Key functions**: `parse_metrics`, `_collect_overall_stats`, `_collect_directory_stats`, `_collect_module_stats`
- **Metric definitions**: `/src/antipasta/core/metrics.py` (MetricType enum)
- **Current METRIC_PREFIXES**: Lines 16-35 in stats.py

### Testing Scenarios
```bash
# Test 1: Should show LOC (default behavior when no -m flags)
antipasta stats -p "src/antipasta/cli/*.py"
# EXPECTED: Shows FILE STATISTICS with LOC info

# Test 2: Should show ONLY cyclomatic complexity (no LOC)
antipasta stats -p "src/antipasta/cli/*.py" -m cyc
# EXPECTED: Shows FILE STATISTICS (count only) and CYCLOMATIC COMPLEXITY STATISTICS
# MUST NOT show: Total LOC, Average LOC per file, etc.

# Test 3: Should show LOC explicitly when requested
antipasta stats -p "src/antipasta/cli/*.py" -m loc
# EXPECTED: Shows full LOC statistics including all LOC variants

# Test 4: Should show both when both requested
antipasta stats -p "src/antipasta/cli/*.py" -m loc -m cyc
# EXPECTED: Shows both LOC and cyclomatic complexity stats

# Test 5: Should show everything including LOC with -m all
antipasta stats -p "src/antipasta/cli/*.py" -m all
# EXPECTED: Shows all metrics including LOC, cyclomatic, cognitive, halstead, etc.

# Test 6: Directory grouping should respect metric selection
antipasta stats -p "src/**/*.py" --by-directory -m cyc
# EXPECTED: Directory table shows file counts but NO "Avg File LOC" or "Total LOC" columns
```

### CRITICAL VALIDATION
After implementation, this command MUST NOT show LOC:
```bash
antipasta stats -p "src/antipasta/cli/*.py" -m cyc | grep -i "loc"
# Should return NOTHING (no matches)
```

### Additional Clarifications
- **File/Function Counts**: Yes, always show file count (e.g., "Total files: 5") and function count, but NOT LOC statistics when using `-m cyc`
- **Empty metrics list**: Use `METRIC_PREFIXES["loc"]` as shown in the implementation details (this ensures consistency)
- **Backward compatibility**: Maintain exact same display format when LOC is shown - no reformatting
- **Error handling**: Use `.get()` with defaults for missing LOC data. Example: `stats_data["files"].get("total_loc", 0)`
- **Test files**: No test file updates needed at this time. Focus on implementation only.

---

## TICKET-STATS-003: Add Path Display Style Options for Directory Statistics

### Summary
Add a `--path-style` option to control how directory paths are displayed in `--by-directory` output. This helps with readability, especially in deep directory structures.

### Current Behavior
```bash
# Currently shows paths relative to the common base:
$ antipasta stats -d src/antipasta --by-directory --depth 2
Location                       Files
----------------------------------------------------------
antipasta                      48        # This is src/antipasta
cli                            11        # This is src/antipasta/cli
core                           6         # This is src/antipasta/core

# Problem: It's not clear that "cli" is under "antipasta"
```

### Acceptance Criteria
1. Add `--path-style` option with two choices: "full" (default) and "parent"
2. "full": Show complete path from base directory (current behavior)
3. "parent": Show only immediate parent + directory name
4. Works correctly with all depth values (including 0/unlimited)
5. Module stats (`--by-module`) not affected
6. Clear, unambiguous output in both modes

### Implementation Details

#### Sub-tasks:
1. **Add CLI option** (After line 101, after --depth option)
   ```python
   @click.option(
       "--path-style",
       type=click.Choice(["full", "parent"]),
       default="full",
       help="Path display style for directories (full: complete path, parent: immediate parent/name only)",
   )
   ```

2. **Update stats function signature** (Line 118)
   - Current signature:
   ```python
   def stats(
       pattern: tuple[str, ...],
       directory: Path,
       by_directory: bool,
       by_module: bool,
       depth: int,
       metric: tuple[str, ...],
       format: str,
       output: Path | None,
   ) -> None:
   ```
   - Add `path_style: str` parameter after `depth`

3. **Update stats function calls to _collect_directory_stats** (Line 219)
   - Current:
   ```python
   stats_data = _collect_directory_stats(reports, metrics_to_include, directory, depth)
   ```
   - Change to:
   ```python
   stats_data = _collect_directory_stats(reports, metrics_to_include, directory, depth, path_style)
   ```

4. **Modify _collect_directory_stats function** (Line 312)
   - Update signature to add `path_style: str` parameter:
   ```python
   def _collect_directory_stats(
       reports: list[Any], metrics_to_include: list[str], base_dir: Path, depth: int, path_style: str
   ) -> dict[str, Any]:
   ```
   - Update display path creation logic (lines 426-430):
   ```python
   # Create display path (current code at lines 426-430)
   if rel_path == Path("."):
       display_path = common_base.name if common_base.name else "."
   else:
       if path_style == "parent":
           # Show only immediate parent/name
           parts = rel_path.parts
           if len(parts) == 1:
               display_path = parts[0]
           elif len(parts) == 2:
               # For two parts, show both (parent/child)
               display_path = str(Path(*parts))
           else:
               # For deeper paths, show last 2 components
               display_path = str(Path(*parts[-2:]))
       else:  # full
           display_path = str(rel_path)
   ```

5. **Update _generate_all_reports function** (Line 777)
   - Current call:
   ```python
   dir_stats = _collect_directory_stats(reports, metrics, Path("."), 1)
   ```
   - Change to:
   ```python
   dir_stats = _collect_directory_stats(reports, metrics, Path("."), 1, "full")  # Default to full style
   ```

6. **Important Edge Cases to Handle**
   - Path with single component: "cli" → "cli" (both styles)
   - Path with two components: "antipasta/cli" → "antipasta/cli" (both styles)
   - Path with 3+ components: "antipasta/runners/python" → "runners/python" (parent style)
   - Root directory ".": Should stay as "." or base dir name
   - Windows paths: Use forward slashes consistently via Path object

### Context & References
- **Primary file**: `/src/antipasta/cli/stats.py`
- **Function to modify**: `_collect_directory_stats` (line 312+)
- **Display function**: `_display_table` (line 550+) - may need updates
- **Path handling**: Uses `pathlib.Path` throughout

### Test Commands for Validation

```bash
# Test 1: Full style (default) - should show complete paths
antipasta stats -d src/antipasta --by-directory --depth 2
# EXPECTED Output:
# Location                       Files    Functions
# ----------------------------------------------------------
# antipasta                      48       444
# antipasta/cli                  11       38
# antipasta/core                 6        57

# Test 2: Parent style - should show only parent/child
antipasta stats -d src/antipasta --by-directory --depth 2 --path-style parent
# EXPECTED Output:
# Location                       Files    Functions
# ----------------------------------------------------------
# antipasta                      48       444
# antipasta/cli                  11       38       # Note: still shows parent/
# antipasta/core                 6        57

# Test 3: Parent style with deep paths (depth 3)
antipasta stats -d src/antipasta --by-directory --depth 3 --path-style parent
# EXPECTED Output should include:
# runners/python                 3        26       # Only last 2 components
# terminal/widgets               9        120      # Only last 2 components

# Test 4: Verify it works with depth=0 (unlimited)
antipasta stats -d src --by-directory --depth 0 --path-style parent

# Test 5: Ensure --by-module is NOT affected
antipasta stats -d src --by-module
# Should work exactly as before (no path_style parameter passed)
```

### Edge Cases to Test
- Empty base directory name
- Paths with spaces or special characters
- Mixed path separators (if on Windows)
- Very deep nesting with parent style
- Interaction with depth parameter
- Duplicate directory names at different levels

### Additional Clarifications
- **Root paths in parent style**: Display just the directory name without prefix (e.g., `antipasta` not `./antipasta`)
- **Deep paths with depth=0**: Always show last 2 components for consistency (e.g., `metrics/complexity` not `complexity/py`)
- **Path separators**: Always use forward slashes via `str(Path(...))` - Path object handles OS differences
- **Column alignment**: Keep existing column width (30 chars) regardless of path style for consistency
- **Path truncation**: If path exceeds 30 chars, truncate from the FRONT with "..." prefix (e.g., "...ry/long/path/to/directory" NOT "very/long/path/to/direc...")
- **Invalid option combinations**: If `--path-style` used without `--by-directory`, silently ignore (no warning needed)

---

## Implementation Order Recommendation

1. **TICKET-STATS-002** (Metric inclusion) - Highest priority bug fix
2. **TICKET-STATS-001** (Unlimited depth) - Simple enhancement
3. **TICKET-STATS-003** (Path styles) - UX improvement

## Testing Strategy

After implementing all three tickets, perform integration testing:

```bash
# Test all three features together
antipasta stats --by-directory --depth 0 -m cyc --path-style parent

# Test edge case: no metrics with unlimited depth and parent style
antipasta stats --by-directory --depth 0 --path-style parent

# Test backward compatibility
antipasta stats --by-directory  # Should work as before
```

## Related Documentation
- `/INTERNAL/TICKET_LIST.md` - Overall project ticket list
- `/src/antipasta/cli/stats.py` - Main implementation file
- `/src/antipasta/core/metrics.py` - Metric type definitions
- `/docs/statistics_feature.md` - User documentation (needs update after implementation)