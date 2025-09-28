# Stats Command Threshold Display Feature

**Date**: 2025-09-21
**Branch**: refactor/remove-tui-v1 (Note: TUI has been removed)
**Status**: Planning

## Overview

Enhance the `antipasta stats` command to display configured thresholds/targets alongside metrics, with visual indicators for violations. This provides immediate context for whether metrics are within acceptable ranges.

## Design Goals

1. **Simple & Elegant**: Add value without cluttering output
2. **Visual Clarity**: Clear indicators for pass/warning/fail states
3. **Configurable**: Load from `.antipasta.yaml` or use defaults
4. **Format Support**: Works across table, CSV, and JSON outputs

## Current State Analysis

### Files Structure (Post-TUI Removal)
- `src/antipasta/cli/stats.py` - Main stats command implementation
- `src/antipasta/core/config.py` - Configuration models with thresholds
- `.antipasta.yaml` - Example config with metric thresholds

### Key Observations
1. Stats command currently loads default config only (line 179: `config = AntipastaConfig.generate_default()`)
2. Config has threshold definitions for each metric with comparison operators
3. Three output formats: table (terminal), CSV, JSON
4. Metrics can be filtered with `-m` flag

## Feature Design

### 1. Terminal Output Enhancement

**Current Format:**
```
CYCLOMATIC COMPLEXITY STATISTICS:
  Count: 14
  Average: 13.69
  Min: 1.00
  Max: 41.00
```

**Enhanced Format:**
```
CYCLOMATIC COMPLEXITY STATISTICS:
  Target: ≤ 10.0 ✓
  Count: 14
  Average: 13.69 ⚠
  Min: 1.00 ✓
  Max: 41.00 ✗
```

### 2. Visual Indicators

**Unicode Mode (Default):**
- `✓` (green) - Value meets threshold
- `⚠` (yellow) - Value within 20% of threshold
- `✗` (red) - Value violates threshold

**ASCII Mode (--no-unicode flag):**
- `[OK]` - Pass
- `[WARN]` - Warning
- `[FAIL]` - Violation

### 3. CSV Enhancement

```csv
Metric,Value,Target,Status
Threshold,-,≤10.0,-
Total Files,1,-,-
Average Function Complexity,13.69,≤10.0,VIOLATION
Min Function Complexity,1.0,≤10.0,OK
Max Function Complexity,41.0,≤10.0,VIOLATION
```

### 4. JSON Enhancement

```json
{
  "cyclomatic_complexity": {
    "count": 14,
    "avg": 13.69,
    "min": 1.0,
    "max": 41.0,
    "threshold": {
      "value": 10.0,
      "operator": "<=",
      "avg_status": "violation",
      "min_status": "ok",
      "max_status": "violation"
    }
  }
}
```

## Implementation Architecture

### New Components

1. **Threshold Display Utilities** (`src/antipasta/cli/utils/threshold_display.py`)
   - `check_threshold(value, threshold, operator) -> ThresholdStatus`
   - `format_threshold(threshold, operator, unicode=True) -> str`
   - `get_status_indicator(status, unicode=True) -> str`
   - `colorize_value(value, status) -> str`

2. **Config Loading Enhancement**
   - Add `--config` option to stats command
   - Auto-detect `.antipasta.yaml` if exists
   - Add `--show-targets` flag (default: True)
   - Add `--no-unicode` flag for ASCII output

### Modified Components

1. **stats.py**:
   - Add config loading logic
   - Pass config to display functions
   - Update `_display_table()` to show thresholds
   - Update `_display_csv()` to add threshold row
   - Update `_display_json()` to include threshold data

## Edge Cases

1. **Missing Config**: Use defaults from `AntipastaConfig.generate_default()`
2. **Disabled Metrics**: Skip threshold display if metric disabled in config
3. **Custom Metrics**: Handle metrics not in default config gracefully
4. **Comparison Operators**: Support all operators (<=, >=, <, >, ==, !=)
5. **Directory/Module Mode**: Show thresholds in summary headers

## Testing Requirements

1. Unit tests for threshold utilities
2. Integration tests with various configs
3. Output format validation (table, CSV, JSON)
4. Visual indicator testing
5. Edge case handling

---

## Implementation Tickets

### TICKET-STATS-THRESH-001: Create Threshold Display Utilities
**Priority**: High
**Size**: Small

Create utility module for threshold comparison and display formatting.

**Tasks:**
- [ ] Create `src/antipasta/cli/utils/__init__.py`
- [ ] Create `src/antipasta/cli/utils/threshold_display.py`
- [ ] Implement `ThresholdStatus` enum (OK, WARNING, VIOLATION)
- [ ] Implement `check_threshold()` function with operator support
- [ ] Implement `format_threshold()` for display strings
- [ ] Implement `get_status_indicator()` for visual symbols
- [ ] Add unit tests for all utilities

**Files:**
- New: `src/antipasta/cli/utils/threshold_display.py`
- New: `tests/unit/cli/utils/test_threshold_display.py`

---

### TICKET-STATS-THRESH-002: Add Config Loading to Stats Command
**Priority**: High
**Size**: Medium

Enhance stats command to load configuration and pass to display functions.

**Tasks:**
- [ ] Add `--config` option with Path type
- [ ] Add `--show-targets` boolean flag (default: True)
- [ ] Add `--no-unicode` boolean flag (default: False)
- [ ] Load config file or use defaults
- [ ] Extract metric thresholds from Python language config
- [ ] Pass config and flags to display functions

**Files:**
- Modify: `src/antipasta/cli/stats.py`

---

### TICKET-STATS-THRESH-003: Enhance Terminal Table Display
**Priority**: High
**Size**: Large

Update table display to show thresholds and visual indicators.

**Tasks:**
- [ ] Modify `_display_table()` to accept config parameter
- [ ] Add threshold line after each metric header
- [ ] Compare values against thresholds
- [ ] Apply color coding with Click styles
- [ ] Add visual indicators to values
- [ ] Handle missing thresholds gracefully
- [ ] Support both Unicode and ASCII modes

**Files:**
- Modify: `src/antipasta/cli/stats.py` (_display_table function)

---

### TICKET-STATS-THRESH-004: Enhance CSV Output
**Priority**: Medium
**Size**: Medium

Add threshold information to CSV output format.

**Tasks:**
- [ ] Modify `_display_csv()` to accept config parameter
- [ ] Add "Target" and "Status" columns
- [ ] Insert threshold row after header
- [ ] Calculate status for each metric
- [ ] Ensure machine-readable format
- [ ] Handle missing thresholds

**Files:**
- Modify: `src/antipasta/cli/stats.py` (_display_csv function)

---

### TICKET-STATS-THRESH-005: Enhance JSON Output
**Priority**: Medium
**Size**: Medium

Add threshold object to JSON output structure.

**Tasks:**
- [ ] Modify `_display_json()` to accept config parameter
- [ ] Add "threshold" object to each metric
- [ ] Include value, operator, and status fields
- [ ] Calculate status for avg, min, max
- [ ] Ensure backward compatibility
- [ ] Handle missing thresholds

**Files:**
- Modify: `src/antipasta/cli/stats.py` (_display_json function)

---

### TICKET-STATS-THRESH-006: Add Integration Tests
**Priority**: Medium
**Size**: Medium

Create comprehensive tests for threshold display feature.

**Tasks:**
- [ ] Test with custom config file
- [ ] Test with default config
- [ ] Test all output formats
- [ ] Test visual indicators
- [ ] Test edge cases (missing config, disabled metrics)
- [ ] Test directory and module grouping modes
- [ ] Test Unicode vs ASCII modes

**Files:**
- New: `tests/unit/cli/test_stats_thresholds.py`
- Modify: `tests/unit/cli/test_stats.py`

---

### TICKET-STATS-THRESH-007: Update Documentation
**Priority**: Low
**Size**: Small

Document the new threshold display feature.

**Tasks:**
- [ ] Update stats command help text
- [ ] Add examples to README
- [ ] Document in CHANGELOG
- [ ] Add configuration examples

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md` (if exists)

---

## Implementation Order

1. **Phase 1**: Foundation (THRESH-001, THRESH-002)
2. **Phase 2**: Display Updates (THRESH-003, THRESH-004, THRESH-005)
3. **Phase 3**: Testing & Docs (THRESH-006, THRESH-007)

## Notes

- Consider caching loaded config for performance
- Ensure backward compatibility - feature should be optional
- Color output should respect terminal capabilities
- Consider adding `--strict` mode that exits with error on violations