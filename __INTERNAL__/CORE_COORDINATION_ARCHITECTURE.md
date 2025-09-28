# Core as the Central Coordinator

## YES - Core is the Hub!

After tracing the dependencies, **the `core/` layer acts as the central coordinator** that connects all components. Here's how:

## Dependency Flow Diagram

```
       CLI Layer (metrics/stats)
              ↓
       [Uses Core APIs]
              ↓
    ┌─────────────────────┐
    │    CORE LAYER       │ <-- Central Hub
    │                     │
    │  • MetricAggregator  │
    │  • Config           │
    │  • Detector          │
    │  • Violations        │
    └─────────────────────┘
              ↓
       [Core manages]
              ↓
         RUNNERS Layer
```

## How Core Coordinates Everything

### 1. **Configuration Flow**

The configuration flows THROUGH core to reach the runners:

```python
# CLI creates config
config = AntipastaConfig.generate_default()
    ↓
# Passes to Core's MetricAggregator
aggregator = MetricAggregator(config)
    ↓
# Core applies config to:
- LanguageDetector(ignore_patterns=config.ignore_patterns)
- Gitignore filtering
- Language-specific thresholds
    ↓
# Core passes relevant config to Runners
runner.analyze(file_path)  # Runner uses thresholds from Core
```

### 2. **File Filtering Coordination**

Core coordinates which files get analyzed:

```python
# Core's Detector handles all filtering
self.detector = LanguageDetector(ignore_patterns=config.ignore_patterns)
self.detector.add_gitignore(gitignore_path)  # Add .gitignore
files_by_language = self.detector.group_by_language(file_paths)
```

The CLI never directly filters files - it asks Core to do it!

### 3. **Runner Management**

**Only Core knows about Runners:**

```python
# In core/aggregator.py
self.runners: dict[Language, list[BaseRunner]] = {
    Language.PYTHON: [RadonRunner(), ComplexipyRunner()],
}
```

Key insight: **CLI layers NEVER import runners directly!** They go through Core's `MetricAggregator`.

### 4. **Violation Detection**

Core coordinates threshold checking:

```python
# Core checks metrics against config thresholds
violations = check_metric_violation(metric, config.thresholds)
# Creates FileReport with violations
# CLI just displays what Core determined
```

## The Complete Coordination Flow

### For Metrics Command:
```
1. CLI prepares config with overrides
2. CLI passes config to Core.MetricAggregator
3. Core applies filters (gitignore, patterns)
4. Core detects languages
5. Core selects appropriate runners
6. Core calls runners.analyze()
7. Core checks thresholds → violations
8. Core returns FileReports
9. CLI displays violations
```

### For Stats Command:
```
1. CLI creates default config
2. CLI passes config to Core.MetricAggregator
3. Core applies filters
4. Core detects languages
5. Core selects runners
6. Core calls runners.analyze()
7. Core returns raw metrics
8. CLI calculates statistics
9. CLI displays statistics
```

## Why This Architecture is Brilliant

### 1. **Single Source of Truth**
- Only Core knows how to coordinate runners
- Only Core knows how to apply configurations
- Only Core knows how to detect languages

### 2. **Clean Boundaries**
```
CLI doesn't know:     Core doesn't know:       Runners don't know:
- About runners       - About CLI commands     - About other runners
- About languages     - About output formats   - About thresholds
- About filtering     - About user interface   - About violations
```

### 3. **Configuration Isolation**
- Config flows DOWN through Core
- Runners never see the full config
- CLI never needs to understand runner requirements

### 4. **Dependency Inversion**
```
Instead of:  CLI → Runners (tight coupling)
We have:     CLI → Core ← Runners (loose coupling)
```

## Evidence from Imports

**CLI imports from Core:**
```python
from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.detector import LanguageDetector
```

**Core imports from Runners:**
```python
from antipasta.runners.python.radon import RadonRunner
from antipasta.runners.python.complexipy_runner import ComplexipyRunner
```

**CLI NEVER imports from Runners!** ✅

## The Answer to Your Question

**YES**, everything flows through Core:

1. **Configuration** enters through Core (`MetricAggregator(config)`)
2. **Filters** are applied by Core (`LanguageDetector`)
3. **Runners** are managed by Core (only Core knows about them)
4. **Metrics** are collected by Core (coordinates runners)
5. **Violations** are determined by Core (checks thresholds)

Core is the **orchestration layer** that:
- Receives high-level commands from CLI
- Coordinates low-level operations with Runners
- Manages all the complexity in between

This is a textbook example of the **Facade Pattern** - Core provides a simplified interface to the complex subsystem of runners, filters, and configurations!