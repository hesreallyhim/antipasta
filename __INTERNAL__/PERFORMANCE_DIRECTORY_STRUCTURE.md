# Performance Enhancement Directory Structure

## Overview
Directory structure designed to support the 82 tickets in PERFORMANCE_TICKETS_V3.md, organized by component responsibility.

```
antipasta/
├── __init__.py
├── __version__.py
│
├── interfaces/                      # PERF-002: Interface definitions
│   ├── __init__.py
│   ├── models.py                    # All Pydantic models and interfaces
│   ├── enums.py                     # ExecutorType, AnalysisStatus, ChangeType
│   └── protocols.py                 # Progress callbacks, other protocols
│
├── core/                            # Core business logic
│   ├── __init__.py
│   │
│   ├── parallel/                    # Phase 1: PERF-004 to PERF-018
│   │   ├── __init__.py
│   │   ├── strategy.py              # PERF-004: ExecutionStrategy
│   │   ├── analyzer.py              # PERF-005,009: ParallelAnalyzer
│   │   ├── batching.py              # PERF-007: Smart batch creation
│   │   ├── worker.py                # PERF-012,013: Worker functions
│   │   └── progress.py              # PERF-017: Progress reporting
│   │
│   ├── errors/                      # Phase 4: PERF-051 to PERF-054
│   │   ├── __init__.py
│   │   ├── classification.py        # PERF-051: Error classification
│   │   ├── handler.py               # PERF-052: ErrorHandler base
│   │   ├── recovery.py              # PERF-053,054: Recovery strategies
│   │   └── fallback.py              # Fallback analysis methods
│   │
│   ├── monitoring/                  # Phase 4: PERF-055 to PERF-062
│   │   ├── __init__.py
│   │   ├── metrics.py               # PERF-055: PerformanceMetrics
│   │   ├── monitor.py               # PERF-056: PerformanceMonitor
│   │   ├── export.py                # PERF-057: Export formats
│   │   ├── logger.py                # PERF-058: Structured logging
│   │   ├── tracing.py               # PERF-059: Operation tracing
│   │   └── pipeline.py              # PERF-060: ObservabilityPipeline
│   │
│   ├── resources/                   # Phase 5: PERF-063 to PERF-072
│   │   ├── __init__.py
│   │   ├── memory.py                # PERF-063: MemoryManager
│   │   ├── filesystem.py            # PERF-064: FileSystemGuard
│   │   ├── allocation.py            # PERF-065: Resource allocation
│   │   ├── cleanup.py               # PERF-066,067: CleanupManager
│   │   ├── sandbox.py               # PERF-068: Simple sandboxing
│   │   ├── monitoring.py            # PERF-069: Resource monitoring
│   │   ├── pools.py                 # PERF-070: Resource pools
│   │   └── pressure.py              # PERF-071: Pressure handling
│   │
│   └── coordinator.py               # PERF-073: SystemCoordinator
│
├── cache/                           # Phase 2: PERF-019 to PERF-036
│   ├── __init__.py
│   ├── manager.py                   # PERF-021,025,026: Cache operations
│   ├── schema.py                    # PERF-020: SQLite schema
│   ├── connection.py                # PERF-021,022: Connection pool
│   ├── keys.py                      # PERF-023: Cache key generation
│   ├── compression.py               # PERF-024: Compression support
│   ├── eviction.py                  # PERF-028,029: LRU/LFU strategies
│   ├── maintenance.py               # PERF-031: Maintenance thread
│   ├── statistics.py                # PERF-033: Hit/miss metrics
│   └── debug.py                     # PERF-034: Debugging tools
│
├── hooks/                           # Phase 3: PERF-037 to PERF-050
│   ├── __init__.py
│   ├── git/                         # Git integration
│   │   ├── __init__.py
│   │   ├── integration.py           # PERF-037,038: GitIntegration
│   │   ├── changes.py               # PERF-039,040: Change detection
│   │   ├── diff.py                  # PERF-041,042: Diff analysis
│   │   └── staging.py               # PERF-041: Staged content
│   │
│   ├── incremental/                 # Incremental analysis
│   │   ├── __init__.py
│   │   ├── analyzer.py              # PERF-044: IncrementalAnalyzer
│   │   └── significance.py          # PERF-043: Change significance
│   │
│   ├── pre_commit.py                # PERF-045,048: PreCommitOptimizer
│   ├── time_budget.py               # PERF-046: Time management
│   └── sampling.py                  # PERF-047: Critical file sampling
│
├── cli/                             # CLI Integration (existing + new)
│   ├── __init__.py
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── metrics.py               # Existing metrics command
│   │   ├── analyze.py               # PERF-074: New performance flags
│   │   ├── cache.py                 # Cache management commands
│   │   └── debug.py                 # PERF-061: Debug mode
│   └── utils.py
│
├── runners/                         # Language-specific runners (existing)
│   ├── __init__.py
│   ├── base.py                      # Base runner interface
│   ├── python.py                    # Python/Radon runner
│   └── complexipy.py                # Complexipy runner
│
├── config/                          # Configuration (existing + new)
│   ├── __init__.py
│   ├── loader.py                    # Config loading
│   ├── validator.py                 # Config validation
│   └── defaults.py                  # Default values
│
└── utils/                           # Shared utilities
    ├── __init__.py
    ├── paths.py                     # Path utilities
    ├── async_utils.py               # Async/threading utilities
    └── platform.py                  # Platform-specific code

tests/
├── __init__.py
├── conftest.py                      # Pytest configuration
│
├── unit/                            # Unit tests by component
│   ├── __init__.py
│   ├── test_interfaces/             # Interface tests
│   ├── test_parallel/               # PERF-015: Parallel tests
│   ├── test_cache/                  # PERF-035,036: Cache tests
│   ├── test_hooks/                  # PERF-050: Pre-commit tests
│   ├── test_errors/                 # Error handling tests
│   ├── test_monitoring/             # PERF-062: Observability tests
│   ├── test_resources/              # PERF-072: Resource tests
│   └── test_coordinator.py          # System coordinator tests
│
├── integration/                     # Integration tests
│   ├── __init__.py
│   ├── test_pipeline.py             # PERF-075: End-to-end tests
│   ├── test_performance.py          # PERF-076: Performance validation
│   ├── test_load.py                 # PERF-077: Load testing
│   └── test_pre_commit.py           # Pre-commit integration
│
├── fixtures/                        # Test fixtures and data
│   ├── __init__.py
│   ├── sample_projects/             # Sample codebases
│   │   ├── small_10_files/
│   │   ├── medium_50_files/
│   │   └── large_200_files/
│   ├── mock_git_repo/               # Git test repository
│   └── test_configs/                # Test configurations
│
└── benchmarks/                      # Performance benchmarks
    ├── __init__.py
    ├── bench_parallel.py            # PERF-018: Parallel benchmarks
    ├── bench_cache.py               # PERF-036: Cache benchmarks
    ├── bench_pre_commit.py          # PERF-050: Pre-commit benchmarks
    └── bench_system.py              # PERF-082: System benchmarks

scripts/                             # Utility scripts
├── benchmark_baseline.py            # PERF-001: Baseline measurement
├── install_pre_commit.py            # PERF-049: Hook installation
├── cache_admin.py                   # Cache administration
└── performance_report.py            # Generate performance reports

config/                              # Configuration files
├── .pre-commit-hooks.yaml           # PERF-049: Pre-commit config
├── antipasta.yaml                   # Default configuration
└── performance.yaml                 # Performance tuning config

docs/                                # Documentation
├── architecture/                    # Architecture docs
│   ├── overview.md
│   ├── parallel_execution.md
│   ├── caching.md
│   └── pre_commit.md
├── api/                             # API documentation
├── performance/                     # PERF-078,081: Performance docs
│   ├── tuning.md                   # Performance tuning guide
│   ├── benchmarks.md               # Benchmark results
│   └── monitoring.md               # Monitoring setup
└── development/                     # Development guides
    ├── testing.md
    └── contributing.md

__INTERNAL__/                        # Internal development files
├── baseline_metrics.json            # PERF-001: Baseline measurements
├── cache/                           # Development cache
│   └── metrics.db                  # SQLite cache database
└── logs/                            # Development logs
    ├── performance/                 # Performance logs
    ├── errors/                      # Error logs
    └── debug/                       # Debug logs
```

## Component Mapping to Tickets

### Phase 0: Foundation (PERF-001 to PERF-003)
- `scripts/benchmark_baseline.py` - PERF-001
- `interfaces/models.py` - PERF-002
- Overall structure creation - PERF-003

### Phase 1: Parallel Execution (PERF-004 to PERF-018)
- `core/parallel/strategy.py` - PERF-004
- `core/parallel/analyzer.py` - PERF-005, 006, 009, 010, 011, 014
- `core/parallel/batching.py` - PERF-007
- `core/parallel/worker.py` - PERF-008, 012, 013
- `core/parallel/progress.py` - PERF-016, 017
- `tests/benchmarks/bench_parallel.py` - PERF-018

### Phase 2: Caching (PERF-019 to PERF-036)
- `cache/` directory structure - PERF-019
- `cache/schema.py` - PERF-020
- `cache/connection.py` - PERF-021, 022
- `cache/keys.py` - PERF-023
- `cache/compression.py` - PERF-024
- `cache/manager.py` - PERF-025, 026, 027
- `cache/eviction.py` - PERF-028, 029, 030
- `cache/maintenance.py` - PERF-031, 032
- `cache/statistics.py` - PERF-033
- `cache/debug.py` - PERF-034
- `tests/unit/test_cache/` - PERF-035
- `tests/benchmarks/bench_cache.py` - PERF-036

### Phase 3: Pre-commit (PERF-037 to PERF-050)
- `hooks/git/integration.py` - PERF-037, 038
- `hooks/git/changes.py` - PERF-039, 040
- `hooks/git/staging.py` - PERF-041
- `hooks/git/diff.py` - PERF-042
- `hooks/incremental/significance.py` - PERF-043
- `hooks/incremental/analyzer.py` - PERF-044
- `hooks/pre_commit.py` - PERF-045, 048
- `hooks/time_budget.py` - PERF-046
- `hooks/sampling.py` - PERF-047
- `scripts/install_pre_commit.py` - PERF-049
- `tests/integration/test_pre_commit.py` - PERF-050

### Phase 4: Observability (PERF-051 to PERF-062)
- `core/errors/classification.py` - PERF-051
- `core/errors/handler.py` - PERF-052
- `core/errors/recovery.py` - PERF-053, 054
- `core/monitoring/metrics.py` - PERF-055
- `core/monitoring/monitor.py` - PERF-056
- `core/monitoring/export.py` - PERF-057
- `core/monitoring/logger.py` - PERF-058
- `core/monitoring/tracing.py` - PERF-059
- `core/monitoring/pipeline.py` - PERF-060
- `cli/commands/debug.py` - PERF-061
- `tests/unit/test_monitoring/` - PERF-062

### Phase 5: Resources (PERF-063 to PERF-072)
- `core/resources/memory.py` - PERF-063
- `core/resources/filesystem.py` - PERF-064
- `core/resources/allocation.py` - PERF-065
- `core/resources/cleanup.py` - PERF-066, 067
- `core/resources/sandbox.py` - PERF-068
- `core/resources/monitoring.py` - PERF-069
- `core/resources/pools.py` - PERF-070
- `core/resources/pressure.py` - PERF-071
- `tests/unit/test_resources/` - PERF-072

### Phase 6: Integration (PERF-073 to PERF-082)
- `core/coordinator.py` - PERF-073
- `cli/commands/analyze.py` - PERF-074
- `tests/integration/test_pipeline.py` - PERF-075
- `tests/integration/test_performance.py` - PERF-076
- `tests/integration/test_load.py` - PERF-077
- `docs/performance/` - PERF-078
- Migration handled in existing files - PERF-079
- `.pre-commit-hooks.yaml` - PERF-080
- `docs/performance/monitoring.md` - PERF-081
- `tests/benchmarks/bench_system.py` - PERF-082

## Key Design Decisions

### 1. Separation of Concerns
- **interfaces/**: All contracts and models in one place
- **core/**: Business logic organized by responsibility
- **cache/**: Isolated caching subsystem
- **hooks/**: Git and pre-commit specific code
- **cli/**: User interface layer

### 2. Testability
- Parallel structure in tests/ mirrors src/
- Fixtures organized by type
- Benchmarks separate from functional tests

### 3. Configuration
- Centralized config directory
- YAML for human readability
- Defaults provided

### 4. Documentation
- Architecture docs map to components
- Performance docs for operations
- Development guides for contributors

### 5. Internal Development
- __INTERNAL__/ for development artifacts
- Logs organized by type
- Baseline metrics preserved

## File Count Estimates

### Source Code
- **interfaces/**: 4 files
- **core/parallel/**: 6 files
- **core/errors/**: 5 files
- **core/monitoring/**: 7 files
- **core/resources/**: 9 files
- **cache/**: 10 files
- **hooks/**: 10 files
- **Total new source files**: ~51 files

### Tests
- **unit tests**: ~40 files
- **integration tests**: 5 files
- **benchmarks**: 5 files
- **Total test files**: ~50 files

### Supporting Files
- **scripts/**: 4 files
- **config/**: 3 files
- **docs/**: ~10 files
- **Total supporting**: ~17 files

**Grand Total**: ~118 new files organized into clear, logical structure

## Implementation Order

Following ticket phases:
1. Create base structure (interfaces, core directories)
2. Implement parallel execution in core/parallel/
3. Build cache system in cache/
4. Add hooks and git integration
5. Layer in observability and error handling
6. Add resource management
7. Integrate with SystemCoordinator
8. Complete with tests and documentation

This structure provides clear boundaries between components while maintaining cohesion within related functionality.