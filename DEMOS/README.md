# Code Complexity Demo Files

This directory contains Python demo files that exhibit varying degrees of complexity across different metrics. These files are useful for:

1. Testing code-cop's metric analysis
2. Understanding different types of complexity
3. Learning refactoring patterns

## Files Overview

### 1. `01_simple_calculator.py` ✅
- **Complexity**: Very Low
- **Cyclomatic**: 1-2 per function
- **Cognitive**: 0-1
- **Maintainability**: ~85 (Excellent)
- **Pattern**: Clean, single-responsibility functions

### 2. `02_password_validator_complex.py` ❌
- **Complexity**: Very High (Bad Example)
- **Cyclomatic**: 15+
- **Cognitive**: 20+
- **Maintainability**: ~45 (Poor)
- **Issues**: Deep nesting, multiple concerns, long function

### 3. `03_password_validator_refactored.py` ✅
- **Complexity**: Low-Medium (Good Refactor)
- **Cyclomatic**: 2-3 per function
- **Cognitive**: 1-2 per function
- **Maintainability**: ~75 (Good)
- **Pattern**: Decomposed methods, early returns, clear separation

### 4. `04_data_processor_medium.py` ⚠️
- **Complexity**: Medium
- **Cyclomatic**: 5-8
- **Cognitive**: 4-6
- **Maintainability**: ~65 (Moderate)
- **Pattern**: Realistic business logic, some nesting

### 5. `05_metrics_analyzer_cognitive.py` ⚠️
- **Complexity**: High Cognitive
- **Cyclomatic**: 6-10
- **Cognitive**: 10-15 (high due to nesting)
- **Maintainability**: ~55 (Moderate-Poor)
- **Issues**: Deep nesting, mixed abstraction levels

## Key Learnings

### Refactoring Patterns (File 2 → File 3)

1. **Extract Method**: Break large functions into smaller ones
2. **Early Returns**: Reduce nesting with guard clauses
3. **Single Responsibility**: Each method does one thing
4. **Strategy Pattern**: Use list of rules instead of nested ifs

### Complexity Types

- **Cyclomatic**: Number of independent paths (if/else/loops)
- **Cognitive**: Mental effort to understand (nesting penalty)
- **Halstead Volume**: Amount of information (operators/operands)
- **Maintainability Index**: Combined score (0-100)

## Running Analysis

```bash
# Analyze all demo files
code-cop metrics --directory DEMOS/

# Analyze specific file
code-cop metrics --files DEMOS/02_password_validator_complex.py

# Compare before/after refactoring
code-cop metrics --files DEMOS/02_password_validator_complex.py DEMOS/03_password_validator_refactored.py
```

## Expected Results

With default thresholds:
- File 1: ✅ Pass all metrics
- File 2: ❌ Fail complexity and maintainability
- File 3: ✅ Pass all metrics (successful refactor)
- File 4: ⚠️ Possible warnings on complexity
- File 5: ❌ Fail cognitive complexity

## Using for Testing

These files are designed to trigger different code-cop rules:

```yaml
# .code_cop.yaml
defaults:
  max_cyclomatic_complexity: 10
  max_cognitive_complexity: 10
  min_maintainability_index: 50
```

- Files 2 and 5 should fail with these defaults
- Adjust thresholds to test different scenarios
- Use for regression testing of code-cop itself