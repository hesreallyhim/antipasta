# Complexipy Runner Implementation Plan

**Date**: January 25, 2025
**Task**: Implement Complexipy runner for cognitive complexity metrics

## Overview

Complexipy is a Python tool that measures cognitive complexity, which differs from cyclomatic complexity by focusing on how difficult code is to understand rather than just counting execution paths. This implementation will add cognitive complexity as a new metric type alongside our existing Radon metrics.

## Pre-Implementation Research

### 1. Understanding Complexipy
- **Package**: complexipy (already in dependencies)
- **Command**: `complexipy <file>` or as Python module
- **Output Format**: JSON with cognitive complexity scores
- **Key Difference**: Penalizes nested structures more heavily than cyclomatic

### 2. Current Architecture Review
- Radon runner pattern in `code_cop/runners/python/radon.py`
- Base runner interface expectations
- Config structure for new metric types
- How metrics are aggregated and reported

## Implementation Sub-Tasks

### Task 1: Create Complexipy Runner Module
**File**: `code_cop/runners/python/complexipy_runner.py`

```python
# Skeleton structure:
class ComplexipyRunner:
    def __init__(self)
    def extract_metrics(self, file_path: Path) -> FileMetrics
    def _run_complexipy(self, file_path: Path) -> dict
    def _parse_output(self, output: dict) -> list[FunctionMetric]
```

**Steps**:
1. Copy RadonRunner as template
2. Modify subprocess command for complexipy
3. Handle complexipy-specific output format
4. Map cognitive complexity to our metric structure

### Task 2: Update Configuration Schema
**Files**:
- `code_cop/core/config.py`
- `.code_cop.yaml`

**Changes Needed**:
1. Add `cognitive_complexity` to MetricType enum
2. Add default threshold (suggested: 15)
3. Update YAML schema documentation
4. Add to default config generation

### Task 3: Integrate Runner into Detector
**File**: `code_cop/core/detector.py`

**Steps**:
1. Import ComplexipyRunner
2. Add to runner initialization logic
3. Handle optional import (complexipy might not be installed)
4. Add cognitive complexity to supported metrics list

### Task 4: Test Complexipy Output Format
**Manual Testing First**:
```bash
# Test on our demo files
complexipy DEMOS/02_password_validator_complex.py
complexipy DEMOS/05_metrics_analyzer_cognitive.py

# Compare with JSON output
complexipy --output-format json DEMOS/02_password_validator_complex.py
```

**Expected Challenges**:
- Different output format than Radon
- Function-level vs file-level metrics
- Handling import failures gracefully

### Task 5: Create Unit Tests
**File**: `tests/unit/test_complexipy_runner.py`

**Test Cases**:
1. Test successful metric extraction
2. Test handling missing complexipy
3. Test parsing various output formats
4. Test error handling for invalid files
5. Test integration with aggregator

### Task 6: Update Demo Files Testing
**Validation**:
1. Run on all demo files
2. Verify cognitive complexity differences from cyclomatic
3. Document expected values in DEMOS/README.md
4. Ensure file 5 shows high cognitive complexity

### Task 7: Update Documentation
**Files to Update**:
- README.md (add cognitive complexity to metrics)
- CLAUDE.md (document new metric)
- Config example in docs

## Technical Considerations

### 1. Subprocess vs Import
```python
# Option A: Subprocess (like Radon)
result = subprocess.run(['complexipy', '--json', str(file_path)])

# Option B: Direct import
from complexipy import cognitive_complexity
result = cognitive_complexity.calculate(code)
```

**Decision**: Start with subprocess for consistency, consider direct import later

### 2. Error Handling
- Complexipy not installed → graceful degradation
- Invalid Python files → return empty metrics
- Subprocess failures → log and continue

### 3. Performance
- Add same subprocess environment fix as Radon
- Consider caching if performance is poor
- Batch processing possibilities

### 4. Metric Aggregation
- How to aggregate function-level cognitive complexity
- Max vs average for file-level reporting
- Threshold application (per function or per file?)

## Implementation Order

1. **Research Phase** (30 min) ✓ COMPLETED
   - Run complexipy manually on demo files
   - Understand output format
   - Review complexipy documentation

2. **Basic Implementation** (1 hour)
   - Create ComplexipyRunner class
   - Implement basic subprocess calling
   - Parse JSON output

3. **Integration** (45 min)
   - Update config schema
   - Integrate into detector
   - Test with existing CLI

4. **Testing** (1 hour)
   - Unit tests for runner
   - Integration tests
   - Demo file validation

5. **Documentation** (30 min)
   - Update all docs
   - Add examples
   - Document thresholds

## Complexity and Time Estimates

### Overall Complexity Assessment
- **Technical Complexity**: Medium (6/10)
  - Following established RadonRunner pattern reduces complexity
  - JSON parsing is straightforward
  - Main challenge: handling edge cases and optional imports

- **Integration Complexity**: Low-Medium (4/10)
  - Clear integration points in existing architecture
  - Config schema changes are minimal
  - Detector already supports multiple runners

- **Testing Complexity**: Low (3/10)
  - Can follow existing test patterns
  - Clear expected outputs from manual testing
  - Demo files provide good test cases

### Time Estimates

**Total Estimated Time**: 3.5 - 4.5 hours

**Breakdown by Phase**:
1. ~~Research Phase: 30 min~~ ✓ COMPLETED
2. Basic Implementation: 45-60 min
3. Integration: 30-45 min
4. Testing: 60-90 min
5. Documentation: 20-30 min
6. Buffer for issues: 30-45 min

**Confidence Level**: 85%
- High confidence due to clear pattern to follow
- Existing RadonRunner provides good template
- JSON output format is simple and well-structured

### Risk Factors
1. **Low Risk**: Subprocess handling (already solved in RadonRunner)
2. **Medium Risk**: Edge cases in output parsing (mitigated by tests)
3. **Low Risk**: Performance impact (can be optimized later if needed)

### Expected Completion
- With focused effort: 3.5 hours
- With normal interruptions: 4.5 hours
- Could be split across 2-3 sessions

## Success Criteria

- [ ] Cognitive complexity appears in `code-cop metrics` output
- [ ] Demo file 5 shows high cognitive complexity (>15)
- [ ] All existing tests still pass
- [ ] New metric can be configured in YAML
- [ ] Graceful handling when complexipy not installed
- [ ] Unit tests achieve >90% coverage for new code

## Example Expected Output

```bash
# After implementation
$ code-cop metrics --files DEMOS/05_metrics_analyzer_cognitive.py

❌ DEMOS/05_metrics_analyzer_cognitive.py:30 (analyze_project_metrics):
   Cognitive Complexity is 25.00 (threshold: <= 15.0)
```

## Notes

- Cognitive complexity penalizes nesting more than cyclomatic
- Better represents actual code readability challenges
- Should highlight different issues than cyclomatic complexity
- May need different thresholds than cyclomatic (typically higher)