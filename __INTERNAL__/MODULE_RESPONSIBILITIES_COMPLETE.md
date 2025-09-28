# Complete Module Responsibility Architecture

## The Four-Layer Architecture

After analyzing the codebase, there are actually **FOUR distinct layers** of responsibility, not just the enforcement/aggregation layers:

```
1. CALCULATION (Runners)  →  2. ORCHESTRATION (Core)  →  3. ANALYSIS (CLI)  →  4. OUTPUT
     ↓                            ↓                          ↓                      ↓
  Raw metrics              Coordination              Enforcement/Stats         Display
```

## Layer 1: Metric Calculation (`runners/`)

**Responsibility:** Actually calculate the raw complexity metrics from source code

This is the **foundational layer** that you correctly identified as missing from the initial analysis. The runners are responsible for the actual mathematical/algorithmic calculation of complexity metrics.

### Structure:
```
runners/
├── base.py                      # Abstract interface
├── python/
│   ├── radon.py                # Calculates cyclomatic, Halstead, LOC
│   └── complexipy_runner.py    # Calculates cognitive complexity
├── javascript/                  # Placeholder for JS runner
└── typescript/                  # Placeholder for TS runner
```

### Key Characteristics:
- **Language-specific** implementations
- **Tool wrappers** (Radon, Complexipy)
- **Pure calculation** - no business logic
- **Returns raw metrics** as data structures

### Example Responsibility:
```python
# RadonRunner.analyze() calculates:
- Cyclomatic complexity: 15 for function 'process_data'
- Halstead volume: 234.5
- Lines of code: 45
```

## Layer 2: Orchestration (`core/`)

**Responsibility:** Coordinate metric calculation across files and languages

The core layer acts as the **orchestrator** between raw calculation and business logic.

### Key Components:
```
core/
├── aggregator.py    # Orchestrates runners, collects metrics
├── detector.py      # Determines which runner to use
├── metrics.py       # Metric data models
└── config.py        # Configuration management
```

### Key Responsibilities:
- **Language detection** - Which runner to use?
- **Runner management** - Coordinate multiple runners
- **Data modeling** - Structure for metrics
- **File filtering** - .gitignore, include/exclude patterns

## Layer 3: Analysis/Business Logic (`cli/`)

**Responsibility:** Apply business logic to metrics (enforcement OR statistics)

This layer **diverges into two paths** based on use case:

### Path A: Enforcement (`cli/metrics/`)
- Compare metrics against thresholds
- Generate violations
- Return pass/fail status

### Path B: Statistics (`cli/stats/`)
- Calculate statistical aggregations
- Group by directory/module
- Generate analytical reports

## Layer 4: Presentation/Output

**Responsibility:** Format and display results to users

### For Metrics:
- Show violations with line numbers
- Format as text or JSON
- Exit with appropriate code

### For Stats:
- Display tables, CSV, JSON
- Show statistical summaries
- Export to files

## The Complete Flow

### Metrics Command Flow:
```
1. RUNNERS calculate raw metrics (e.g., complexity = 15)
   ↓
2. CORE aggregates from all files/runners
   ↓
3. METRICS compares against thresholds (15 > 10 = violation!)
   ↓
4. OUTPUT displays violations and exits with code 2
```

### Stats Command Flow:
```
1. RUNNERS calculate raw metrics (e.g., [15, 3, 7, 9, 2])
   ↓
2. CORE aggregates from all files/runners
   ↓
3. STATS calculates statistics (mean = 7.2, std = 5.3)
   ↓
4. OUTPUT displays formatted statistics table
```

## Why This Separation Matters

1. **Single Responsibility:** Each layer has ONE clear job
2. **Testability:** Can test calculation separately from business logic
3. **Extensibility:** Add new languages by adding runners
4. **Reusability:** Same metrics used for different purposes
5. **Maintainability:** Changes to calculation don't affect enforcement

## The Missing Piece You Identified

You were absolutely right - the **metric calculation layer** (runners) is a distinct responsibility that's fundamental to everything else. Without it, there are no metrics to enforce or aggregate!

The runners are the **data producers**, while metrics/stats are **data consumers** with different consumption patterns:
- Metrics: threshold comparison consumer
- Stats: statistical analysis consumer

## Summary

The complete architecture has four distinct responsibilities:

1. **Runners:** Calculate raw complexity metrics (the foundation)
2. **Core:** Orchestrate calculation across files/languages
3. **CLI Commands:** Apply business logic (enforce OR analyze)
4. **Output:** Present results to users

This separation ensures each module has a clear, single responsibility in the pipeline from source code to user-actionable information.