# Performance Optimization Tickets V3

## Overview
Tickets derived directly from PERFORMANCE_OPTIMIZATION_PLAN_V2.md design document.
Each ticket is 15-30 minutes scope with clear testing criteria and design traceability.

## Ticket Format
- **ID**: Unique identifier
- **Title**: Descriptive name
- **Time**: Estimated time (15-30 min)
- **Implements**: Reference to V2 design section/interface
- **Dependencies**: Prerequisites
- **Sub-tasks**: Detailed implementation steps
- **Testing Criteria**: How to verify completion

---

## Phase 0: Foundation & Performance Baseline (3 tickets, 75 min)

### PERF-001: Create Performance Baseline Script
**Time**: 25 min
**Implements**: V2 Success Metrics (lines 1462-1476)
**Dependencies**: None
**Sub-tasks**:
- Create `scripts/benchmark_baseline.py`
- Measure current performance on 10/50/200 file datasets
- Record: total time, per-file time, memory usage
- Output JSON results to `__INTERNAL__/baseline_metrics.json`
**Testing Criteria**:
- Script runs without errors
- Produces reproducible measurements (±5% variance)
- JSON output contains all required metrics

### PERF-002: Create Interface Definitions Module
**Time**: 25 min
**Implements**: V2 Appendix Component Interfaces (lines 1514-1804)
**Dependencies**: None
**Sub-tasks**:
- Create `src/antipasta/interfaces/` directory
- Create `models.py` with Pydantic base models
- Define enums: ExecutorType, AnalysisStatus, ChangeType
- Define DTOs: FileMetrics, AnalysisRequest, AnalysisResult, CacheEntry
**Testing Criteria**:
- All models validate with sample data
- Enums have all required values from design
- Import succeeds from other modules

### PERF-003: Create Project Structure for Optimization
**Time**: 25 min
**Implements**: V2 Component Architecture (lines 1506-1511)
**Dependencies**: PERF-002
**Sub-tasks**:
- Create directory structure:
  - `src/antipasta/core/parallel/`
  - `src/antipasta/cache/`
  - `src/antipasta/hooks/`
  - `src/antipasta/core/monitoring/`
  - `src/antipasta/core/resources/`
- Add `__init__.py` files with proper exports
- Create placeholder classes matching interfaces
**Testing Criteria**:
- All directories created
- Imports work: `from antipasta.core.parallel import ParallelAnalyzer`
- No circular import issues

---

## Phase 1: Parallel Execution (15 tickets, 395 min)

### PERF-004: Create ExecutionStrategy Class
**Time**: 25 min
**Implements**: V2 Part A ExecutionStrategy (lines 48-77)
**Dependencies**: PERF-002
**Sub-tasks**:
- Create `src/antipasta/core/parallel/strategy.py`
- Implement `ExecutionStrategy` dataclass with thresholds
- Implement `determine_strategy()` method with memory awareness
- Add `_get_available_memory()` helper using psutil
**Testing Criteria**:
- Returns SEQUENTIAL for <5 files
- Returns THREAD_POOL for 5-20 files
- Returns PROCESS_POOL for >20 files
- Respects memory constraints

### PERF-005: Create ParallelAnalyzer Base Structure
**Time**: 30 min
**Implements**: V2 Part A ParallelAnalyzer class (lines 81-96)
**Dependencies**: PERF-004
**Sub-tasks**:
- Create `src/antipasta/core/parallel/analyzer.py`
- Define `__init__` with max_workers, timeout, retry params
- Add thread lock and results queue
- Create placeholder for `_worker_init` method
- Implement IParallelAnalyzer interface
**Testing Criteria**:
- Class instantiates with default parameters
- Parameters validate within expected ranges
- Thread lock is properly initialized

### PERF-006: Implement Executor Context Manager
**Time**: 25 min
**Implements**: V2 Part A _get_executor (lines 97-116)
**Dependencies**: PERF-005
**Sub-tasks**:
- Implement `_get_executor()` context manager
- Handle ProcessPoolExecutor with spawn context
- Handle ThreadPoolExecutor with named threads
- Ensure proper shutdown with wait=True
**Testing Criteria**:
- Context manager properly creates executor
- Executor shuts down cleanly on exit
- No resource leaks after context exit

### PERF-007: Create Smart Batch Creation Algorithm
**Time**: 30 min
**Implements**: V2 Part A _create_smart_batches (lines 190-221)
**Dependencies**: PERF-005
**Sub-tasks**:
- Implement file weight calculation based on size
- Add file type multipliers (.py = 1.2x weight)
- Implement best-fit decreasing bin packing
- Balance batches across workers
**Testing Criteria**:
- Batches have balanced total weights (±10%)
- Large files distributed across batches
- Number of batches ≤ max_workers

### PERF-008: Implement Sequential Analysis Path
**Time**: 20 min
**Implements**: V2 Part A analyze_batch sequential path (lines 128-129)
**Dependencies**: PERF-005
**Sub-tasks**:
- Implement `_analyze_sequential()` method
- Process files one by one
- Call progress callback after each file
- Aggregate results into AnalysisResult
**Testing Criteria**:
- Processes all files in order
- Progress callback called N times for N files
- Returns complete AnalysisResult

### PERF-009: Implement Parallel Analysis Core
**Time**: 30 min
**Implements**: V2 Part A _analyze_parallel (lines 134-186)
**Dependencies**: PERF-006, PERF-007
**Sub-tasks**:
- Submit batches to executor
- Track future-to-batch mapping
- Process results with as_completed
- Maintain result ordering
**Testing Criteria**:
- All batches submitted to executor
- Results maintain original file order
- Progress callback reports accurate completion

### PERF-010: Add Timeout Handling for Batches
**Time**: 25 min
**Implements**: V2 Part A _analyze_batch_with_timeout (line 149)
**Dependencies**: PERF-009
**Sub-tasks**:
- Create timeout wrapper for batch analysis
- Use concurrent.futures timeout
- Return partial results on timeout
- Log timeout occurrences
**Testing Criteria**:
- Timeout triggers after specified duration
- Partial results returned on timeout
- No hanging processes after timeout

### PERF-011: Implement Retry with Exponential Backoff
**Time**: 25 min
**Implements**: V2 Part A _retry_with_backoff (line 173)
**Dependencies**: PERF-009
**Sub-tasks**:
- Implement retry logic with configurable attempts
- Add exponential backoff (1s, 2s, 4s)
- Track retry attempts in results
- Return None if all retries fail
**Testing Criteria**:
- Retries up to max_attempts times
- Backoff delays double each attempt
- Successful retry returns valid results

### PERF-012: Create Worker Process Initialization
**Time**: 20 min
**Implements**: V2 Part A _worker_init (line 104)
**Dependencies**: PERF-005
**Sub-tasks**:
- Set up worker process environment
- Configure logging for worker
- Set process name for debugging
- Initialize any shared resources
**Testing Criteria**:
- Worker processes have unique names
- Logging works from worker processes
- No import errors in workers

### PERF-013: Implement File Analysis Worker Function
**Time**: 30 min
**Implements**: V2 Part A worker analysis logic
**Dependencies**: PERF-012
**Sub-tasks**:
- Create `_analyze_file_worker()` function
- Call appropriate language runner (Radon)
- Handle file read errors gracefully
- Return FileMetrics or error info
**Testing Criteria**:
- Analyzes Python files correctly
- Returns valid FileMetrics
- Handles missing files gracefully

### PERF-014: Add Memory Check Before Operations
**Time**: 20 min
**Implements**: V2 Part A memory awareness (lines 68-76)
**Dependencies**: PERF-004
**Sub-tasks**:
- Add memory estimation per file
- Check available memory before batch
- Switch to thread pool if memory constrained
- Log memory-based strategy changes
**Testing Criteria**:
- Estimates memory usage accurately
- Switches strategy when memory low
- No OOM errors during execution

### PERF-015: Create Parallel Analyzer Integration Test
**Time**: 30 min
**Implements**: V2 Part A complete integration
**Dependencies**: PERF-004 through PERF-014
**Sub-tasks**:
- Test with 5, 20, 50 files
- Verify strategy selection
- Verify result ordering
- Measure performance improvement
**Testing Criteria**:
- Correct strategy for each file count
- Results match sequential analysis
- Performance ≥2x faster for 20+ files

### PERF-016: Add Parallel Analysis Error Aggregation
**Time**: 25 min
**Implements**: V2 Part A error handling (lines 178-180)
**Dependencies**: PERF-009
**Sub-tasks**:
- Create AnalysisError dataclass
- Collect errors from failed batches
- Include errors in AnalysisResult
- Categorize errors by type
**Testing Criteria**:
- All errors captured and returned
- Error details include file and exception
- Analysis continues despite errors

### PERF-017: Implement Progress Reporting Callback
**Time**: 20 min
**Implements**: V2 Part A progress callback (lines 119, 169)
**Dependencies**: PERF-009
**Sub-tasks**:
- Define progress callback protocol
- Call with (completed, total) counts
- Thread-safe progress updates
- Support for custom callbacks
**Testing Criteria**:
- Callback called for each completed file
- Accurate completion counts
- Thread-safe under concurrent updates

### PERF-018: Add Parallel Execution Benchmarks
**Time**: 30 min
**Implements**: V2 Success Metrics validation (lines 1464-1469)
**Dependencies**: PERF-001, PERF-015
**Sub-tasks**:
- Benchmark 10, 50, 200 file datasets
- Compare against baseline metrics
- Verify <500ms, <2s, <5s targets
- Generate performance report
**Testing Criteria**:
- Meets performance targets
- Reproducible results
- Report shows improvement percentage

---

## Phase 2: Caching System (18 tickets, 460 min)

### PERF-019: Create Cache Directory Structure
**Time**: 15 min
**Implements**: V2 Part B cache initialization (lines 292-295)
**Dependencies**: PERF-003
**Sub-tasks**:
- Create cache directory at `~/.antipasta/cache/`
- Set appropriate permissions (700)
- Create cache config file
- Handle missing directory creation
**Testing Criteria**:
- Directory created with correct permissions
- Works on Linux/macOS/Windows
- Handle existing directory gracefully

### PERF-020: Design SQLite Cache Schema
**Time**: 25 min
**Implements**: V2 Part B SQLite schema (lines 256-280)
**Dependencies**: PERF-019
**Sub-tasks**:
- Create schema SQL with version table
- Define metrics_cache table with all columns
- Add optimized indexes
- Create schema migration system stub
**Testing Criteria**:
- Schema creates without errors
- All indexes created
- UUID primary keys work
- Version tracking functional

### PERF-021: Implement Database Connection Pool
**Time**: 30 min
**Implements**: V2 Part B connection pooling (lines 308-327)
**Dependencies**: PERF-020
**Sub-tasks**:
- Create connection pool with queue.Queue
- Implement `_get_connection()` context manager
- Handle pool exhaustion gracefully
- Add connection recycling
**Testing Criteria**:
- Pool limits connections to max_connections
- Connections returned to pool after use
- No connection leaks
- Thread-safe access

### PERF-022: Configure SQLite for Concurrency
**Time**: 20 min
**Implements**: V2 Part B _create_connection (lines 328-342)
**Dependencies**: PERF-021
**Sub-tasks**:
- Enable WAL mode for concurrency
- Set pragmas: synchronous, cache_size, temp_store
- Configure connection timeout
- Add connection health check
**Testing Criteria**:
- WAL mode enabled
- Multiple readers work concurrently
- No database locked errors
- Pragmas correctly set

### PERF-023: Implement Cache Key Generation
**Time**: 25 min
**Implements**: V2 Part B generate_cache_entry (lines 344-376)
**Dependencies**: PERF-022
**Sub-tasks**:
- Generate SHA256 file content hash
- Generate deterministic config hash
- Create UUID for cache_id
- Handle large files efficiently
**Testing Criteria**:
- Consistent hashes for same content
- Config changes produce different hash
- UUIDs are unique
- No memory issues with large files

### PERF-024: Add Metrics Compression Support
**Time**: 20 min
**Implements**: V2 Part B compression (lines 360-364)
**Dependencies**: PERF-023
**Sub-tasks**:
- Compress metrics JSON with zlib
- Add compression flag to schema
- Handle compression/decompression
- Measure compression ratio
**Testing Criteria**:
- Compression reduces size >50%
- Decompression restores exact data
- Toggle compression via config
- No data corruption

### PERF-025: Implement Cache Get Operation
**Time**: 30 min
**Implements**: V2 Part B get method (lines 377-428)
**Dependencies**: PERF-024
**Sub-tasks**:
- Query by file path and config hash
- Verify file hasn't changed (mtime + hash)
- Update access statistics atomically
- Decompress and deserialize metrics
**Testing Criteria**:
- Returns metrics for valid cache hit
- Returns None for cache miss
- Updates access count and time
- Handles corrupted entries gracefully

### PERF-026: Implement Cache Set Operation
**Time**: 25 min
**Implements**: V2 Part B cache storage (lines 344-376)
**Dependencies**: PERF-025
**Sub-tasks**:
- Store new cache entries
- Handle duplicate key conflicts
- Update existing entries if newer
- Commit atomically
**Testing Criteria**:
- New entries stored successfully
- Updates replace old entries
- No duplicate cache_ids
- Atomic commits (all or nothing)

### PERF-027: Create Cache Invalidation Logic
**Time**: 25 min
**Implements**: V2 Part B invalidation (lines 406-407)
**Dependencies**: PERF-026
**Sub-tasks**:
- Invalidate by file path
- Invalidate by config change
- Invalidate by age
- Track invalidation reasons
**Testing Criteria**:
- Invalidated entries not returned
- Cascade invalidation for dependencies
- Invalidation logged with reason
- No orphaned entries

### PERF-028: Implement LRU Eviction Strategy
**Time**: 25 min
**Implements**: V2 Part B _evict_lru (lines 475-491)
**Dependencies**: PERF-027
**Sub-tasks**:
- Query least recently used entries
- Delete bottom 25% when over limit
- Preserve frequently accessed entries
- Log eviction events
**Testing Criteria**:
- Evicts least recently used first
- Maintains cache size under limit
- Keeps frequently used entries
- No data loss for recent entries

### PERF-029: Implement LFU Eviction Strategy
**Time**: 25 min
**Implements**: V2 Part B _evict_lfu (lines 492-508)
**Dependencies**: PERF-028
**Sub-tasks**:
- Query by access count
- Consider access time as tiebreaker
- Delete least frequently used
- Balance with LRU strategy
**Testing Criteria**:
- Evicts least frequently used
- Ties broken by last access time
- Works with access_count column
- Combines well with LRU

### PERF-030: Create Cache Size Management
**Time**: 20 min
**Implements**: V2 Part B smart_invalidation (lines 437-473)
**Dependencies**: PERF-029
**Sub-tasks**:
- Calculate total cache size in MB
- Monitor entry count
- Trigger eviction at thresholds
- Report cache statistics
**Testing Criteria**:
- Accurate size calculation
- Triggers at 100MB limit
- Maintains <10000 entries
- Statistics are accurate

### PERF-031: Add Cache Maintenance Thread
**Time**: 25 min
**Implements**: V2 Part B CacheMaintenanceStrategy (lines 433-509)
**Dependencies**: PERF-030
**Sub-tasks**:
- Create maintenance thread/process
- Schedule periodic cleanup
- Remove expired entries
- Optimize database periodically
**Testing Criteria**:
- Runs without blocking main thread
- Cleans expired entries
- Database stays optimized
- No interference with reads/writes

### PERF-032: Implement Cache Warmup
**Time**: 20 min
**Implements**: V2 Part B cache initialization
**Dependencies**: PERF-025
**Sub-tasks**:
- Preload frequently used entries
- Warm up connection pool
- Prime database page cache
- Load configuration cache
**Testing Criteria**:
- Reduces first-query latency
- Pool connections ready
- Common entries in memory
- No startup delays

### PERF-033: Add Cache Hit/Miss Metrics
**Time**: 20 min
**Implements**: V2 Part B cache statistics
**Dependencies**: PERF-025, PERF-026
**Sub-tasks**:
- Track hit/miss counts
- Calculate hit rate percentage
- Track average retrieval time
- Export metrics for monitoring
**Testing Criteria**:
- Accurate hit/miss counting
- Hit rate calculation correct
- Timing measurements precise
- Metrics exported properly

### PERF-034: Create Cache Debugging Tools
**Time**: 25 min
**Implements**: V2 Part B cache debugging
**Dependencies**: PERF-033
**Sub-tasks**:
- Cache status command
- Entry inspection tool
- Cache validation/repair
- Performance profiling
**Testing Criteria**:
- Shows cache statistics
- Can inspect individual entries
- Detects and fixes corruption
- Profiles cache operations

### PERF-035: Implement Cache Thread Safety Tests
**Time**: 30 min
**Implements**: V2 Part B thread safety (lines 287-289)
**Dependencies**: PERF-021 through PERF-033
**Sub-tasks**:
- Concurrent read stress test
- Concurrent write stress test
- Mixed read/write test
- Connection pool exhaustion test
**Testing Criteria**:
- No deadlocks under load
- No data corruption
- No connection leaks
- Graceful degradation

### PERF-036: Cache Performance Benchmarks
**Time**: 30 min
**Implements**: V2 Success Metrics cache targets (lines 1469)
**Dependencies**: PERF-035
**Sub-tasks**:
- Benchmark cache operations
- Verify <500ms for cached analysis
- Test with 1000+ entries
- Compare with no-cache baseline
**Testing Criteria**:
- Cache hits <10ms
- Cached analysis <500ms total
- Handles 1000+ entries well
- 10x+ faster than no cache

---

## Phase 3: Pre-commit & Incremental Analysis (14 tickets, 360 min)

### PERF-037: Create Git Integration Base Class
**Time**: 25 min
**Implements**: V2 Part C GitIntegration (lines 537-559)
**Dependencies**: PERF-002
**Sub-tasks**:
- Create `src/antipasta/hooks/git.py`
- Implement `_verify_git_available()`
- Handle git not found errors
- Detect repository root
**Testing Criteria**:
- Detects git availability
- Finds repository root
- Handles non-git directories
- Clear error messages

### PERF-038: Implement Get Staged Files
**Time**: 25 min
**Implements**: V2 Part C get_staged_files (lines 559-590)
**Dependencies**: PERF-037
**Sub-tasks**:
- Run git diff --cached command
- Filter by file extensions
- Handle renamed/deleted files
- Return Path objects
**Testing Criteria**:
- Returns only staged files
- Filters by extension correctly
- Handles all git statuses
- No errors on empty staging

### PERF-039: Create Code Change Detection
**Time**: 30 min
**Implements**: V2 Part C CodeChange class (lines 595-604)
**Dependencies**: PERF-038
**Sub-tasks**:
- Define CodeChange dataclass
- Implement change type detection
- Track line number ranges
- Calculate complexity delta
**Testing Criteria**:
- Identifies all change types
- Accurate line numbers
- Complexity delta calculated
- Handles edge cases

### PERF-040: Implement AST-based Diff Analysis
**Time**: 30 min
**Implements**: V2 Part C _get_code_changes (lines 647-709)
**Dependencies**: PERF-039
**Sub-tasks**:
- Parse Python files to AST
- Extract function definitions
- Compare AST structures
- Identify changed functions
**Testing Criteria**:
- Parses valid Python correctly
- Detects function changes
- Handles syntax errors gracefully
- Accurate change detection

### PERF-041: Get Staged File Content
**Time**: 20 min
**Implements**: V2 Part C _get_staged_content (lines 711-726)
**Dependencies**: PERF-038
**Sub-tasks**:
- Run git show command
- Handle newly added files
- Set timeout for git operations
- Return file content as string
**Testing Criteria**:
- Retrieves staged content
- Handles new files (return empty)
- Timeout prevents hanging
- Encoding handled correctly

### PERF-042: Compare Function Changes
**Time**: 25 min
**Implements**: V2 Part C _has_function_changed (lines 728-733)
**Dependencies**: PERF-040
**Sub-tasks**:
- Normalize AST for comparison
- Ignore whitespace/comments
- Detect semantic changes
- Handle renamed functions
**Testing Criteria**:
- Detects real changes only
- Ignores formatting changes
- Handles function renames
- No false positives

### PERF-043: Determine Change Significance
**Time**: 25 min
**Implements**: V2 Part C _are_changes_significant (lines 735-754)
**Dependencies**: PERF-042
**Sub-tasks**:
- Check for added/deleted functions
- Calculate change percentage
- Check critical function list
- Return re-analysis decision
**Testing Criteria**:
- Triggers on additions/deletions
- Triggers on >20% changes
- Respects critical functions
- Conservative when uncertain

### PERF-044: Create Incremental Analyzer Class
**Time**: 30 min
**Implements**: V2 Part C IncrementalAnalyzer (lines 605-646)
**Dependencies**: PERF-043
**Sub-tasks**:
- Initialize with git and cache
- Implement analyze_changes method
- Handle analysis failures
- Return files needing analysis
**Testing Criteria**:
- Correctly filters files
- Uses cache when available
- Falls back on errors
- Returns accurate file list

### PERF-045: Create PreCommitOptimizer Class
**Time**: 30 min
**Implements**: V2 Part C PreCommitOptimizer (lines 760-768)
**Dependencies**: PERF-044
**Sub-tasks**:
- Initialize components
- Create run method
- Handle configuration loading
- Coordinate analysis pipeline
**Testing Criteria**:
- Initializes all components
- Loads configuration correctly
- Coordinates pipeline
- Returns proper result

### PERF-046: Implement Time Budget Management
**Time**: 25 min
**Implements**: V2 Part C time budget (lines 780-782, 802)
**Dependencies**: PERF-045
**Sub-tasks**:
- Track elapsed time
- Estimate remaining time
- Timeout long operations
- Return partial results
**Testing Criteria**:
- Enforces 5-second default
- Calculates time remaining
- Timeouts work correctly
- Partial results on timeout

### PERF-047: Add Critical File Sampling
**Time**: 25 min
**Implements**: V2 Part C _sample_critical_files (lines 834-867)
**Dependencies**: PERF-046
**Sub-tasks**:
- Identify critical paths
- Sort by file size
- Prioritize recent changes
- Limit to time budget
**Testing Criteria**:
- Prioritizes critical paths
- Includes large files
- Returns subset within budget
- Maintains priority order

### PERF-048: Create Pre-commit Entry Point
**Time**: 25 min
**Implements**: V2 Part C run method (lines 769-832)
**Dependencies**: PERF-045 through PERF-047
**Sub-tasks**:
- Get staged files
- Run incremental analysis
- Check violations
- Format result message
**Testing Criteria**:
- Complete pipeline works
- Violations detected
- Proper exit codes
- User-friendly messages

### PERF-049: Add Pre-commit Installation Script
**Time**: 20 min
**Implements**: V2 Part C pre-commit integration
**Dependencies**: PERF-048
**Sub-tasks**:
- Create .pre-commit-hooks.yaml
- Add installation script
- Configure hook parameters
- Document installation
**Testing Criteria**:
- Hook installs correctly
- Runs on git commit
- Configurable parameters
- Clear documentation

### PERF-050: Pre-commit Performance Test
**Time**: 30 min
**Implements**: V2 Success Metrics pre-commit (lines 1469)
**Dependencies**: PERF-049
**Sub-tasks**:
- Test with typical commits (1-10 files)
- Verify <2 second requirement
- Test timeout behavior
- Test cache effectiveness
**Testing Criteria**:
- Meets <2 second target
- Timeouts work properly
- Cache improves performance
- No false positives

---

## Phase 4: Error Handling & Observability (12 tickets, 300 min)

### PERF-051: Create Error Classification System
**Time**: 20 min
**Implements**: V2 Part D ErrorSeverity, AnalysisError (lines 891-906)
**Dependencies**: PERF-002
**Sub-tasks**:
- Define ErrorSeverity enum
- Create AnalysisError dataclass
- Add error context structure
- Include recovery suggestions
**Testing Criteria**:
- All severity levels defined
- Error context captured
- Stack traces included
- Recovery actions suggested

### PERF-052: Implement Error Handler Base
**Time**: 25 min
**Implements**: V2 Part D ErrorHandler (lines 908-933)
**Dependencies**: PERF-051
**Sub-tasks**:
- Create error handler class
- Map error types to handlers
- Implement handler registry
- Add error collection
**Testing Criteria**:
- Handlers registered correctly
- Errors routed to handlers
- Collection maintains history
- Thread-safe error handling

### PERF-053: Add File Error Recovery
**Time**: 25 min
**Implements**: V2 Part D file error handlers (lines 935-969)
**Dependencies**: PERF-052
**Sub-tasks**:
- Handle FileNotFoundError
- Handle PermissionError
- Handle SyntaxError with fallback
- Implement fallback analysis
**Testing Criteria**:
- Missing files skipped gracefully
- Permission errors logged
- Syntax errors use fallback
- Fallback provides basic metrics

### PERF-054: Add Timeout and Memory Recovery
**Time**: 25 min
**Implements**: V2 Part D timeout/memory handlers (lines 970-990)
**Dependencies**: PERF-052
**Sub-tasks**:
- Handle TimeoutError with batch split
- Handle MemoryError with cleanup
- Trigger emergency cleanup
- Switch to streaming mode
**Testing Criteria**:
- Timeouts trigger batch split
- Memory errors trigger cleanup
- Emergency cleanup works
- Streaming mode activates

### PERF-055: Create Performance Metrics Class
**Time**: 25 min
**Implements**: V2 Part D PerformanceMetrics (lines 1003-1020)
**Dependencies**: PERF-002
**Sub-tasks**:
- Define metrics dataclass
- Track file counts
- Track timing breakdowns
- Calculate efficiency metrics
**Testing Criteria**:
- All metrics tracked
- Calculations accurate
- Thread-safe updates
- Serializable to JSON

### PERF-056: Implement Performance Monitor
**Time**: 25 min
**Implements**: V2 Part D PerformanceMonitor (lines 1021-1082)
**Dependencies**: PERF-055
**Sub-tasks**:
- Track analysis phases
- Record file-level timing
- Calculate parallel efficiency
- Generate summary reports
**Testing Criteria**:
- Phase timing accurate
- File timing recorded
- Efficiency calculated correctly
- Summary readable

### PERF-057: Add Metrics Export Formats
**Time**: 20 min
**Implements**: V2 Part D export_metrics (lines 1074-1082)
**Dependencies**: PERF-056
**Sub-tasks**:
- Export to JSON format
- Export to Prometheus format
- Add CSV export option
- Support custom formats
**Testing Criteria**:
- Valid JSON output
- Prometheus format correct
- CSV properly formatted
- Extensible for new formats

### PERF-058: Create Structured Logger
**Time**: 25 min
**Implements**: V2 Part D structured logging (lines 1090-1105)
**Dependencies**: None
**Sub-tasks**:
- Configure JSON formatter
- Set up log levels
- Add context injection
- Configure log rotation
**Testing Criteria**:
- JSON logs parseable
- Context included in logs
- Log levels work
- Rotation prevents growth

### PERF-059: Implement Operation Tracing
**Time**: 25 min
**Implements**: V2 Part D trace_operation (lines 1108-1141)
**Dependencies**: PERF-058
**Sub-tasks**:
- Create trace context manager
- Add timing to traces
- Include operation metadata
- Handle trace errors
**Testing Criteria**:
- Traces include timing
- Context preserved
- Errors logged in trace
- Nested traces work

### PERF-060: Create Observability Pipeline
**Time**: 30 min
**Implements**: V2 Part D ObservabilityPipeline (lines 1083-1141)
**Dependencies**: PERF-059
**Sub-tasks**:
- Integrate monitor and logger
- Coordinate error handler
- Add trace correlation
- Export aggregated metrics
**Testing Criteria**:
- Components integrated
- Traces correlated
- Metrics aggregated
- Exports complete view

### PERF-061: Add Debug Mode Support
**Time**: 25 min
**Implements**: V2 Part D detailed monitoring
**Dependencies**: PERF-060
**Sub-tasks**:
- Add --debug flag handling
- Enable detailed metrics
- Increase log verbosity
- Add performance profiling
**Testing Criteria**:
- Debug flag recognized
- Detailed output produced
- Profiling data captured
- No performance impact when off

### PERF-062: Observability Integration Test
**Time**: 30 min
**Implements**: V2 Part D complete observability
**Dependencies**: PERF-051 through PERF-061
**Sub-tasks**:
- Test error recovery paths
- Verify metrics accuracy
- Check log completeness
- Validate trace correlation
**Testing Criteria**:
- All errors handled
- Metrics match reality
- Logs contain needed info
- Traces show full flow

---

## Phase 5: Resource Management (10 tickets, 250 min)

### PERF-063: Create Memory Manager
**Time**: 25 min
**Implements**: V2 Part E MemoryManager (lines 1164-1217)
**Dependencies**: None
**Sub-tasks**:
- Monitor process memory usage
- Check available memory
- Set resource limits
- Implement emergency cleanup
**Testing Criteria**:
- Accurate memory reporting
- Limits enforced
- Cleanup reduces usage
- No crashes from limits

### PERF-064: Add File System Safety Checks
**Time**: 25 min
**Implements**: V2 Part E FileSystemGuard (lines 1222-1272)
**Dependencies**: None
**Sub-tasks**:
- Validate file size limits
- Detect binary files
- Limit open file handles
- Clean up stale handles
**Testing Criteria**:
- Large files rejected
- Binary files detected
- Handle limit enforced
- Cleanup works

### PERF-065: Implement Resource Allocation
**Time**: 20 min
**Implements**: V2 Part E resource checks
**Dependencies**: PERF-063, PERF-064
**Sub-tasks**:
- Check before operations
- Reserve resources
- Release after use
- Handle allocation failure
**Testing Criteria**:
- Resources checked first
- Reservations honored
- Proper release on exit
- Graceful failure

### PERF-066: Create Cleanup Manager
**Time**: 25 min
**Implements**: V2 Part E CleanupManager (lines 1385-1424)
**Dependencies**: None
**Sub-tasks**:
- Register cleanup handlers
- Handle signals (SIGINT, SIGTERM)
- Execute cleanup on exit
- Manage cleanup order
**Testing Criteria**:
- Handlers registered
- Signals caught
- Cleanup runs on exit
- Order preserved

### PERF-067: Add Graceful Shutdown
**Time**: 25 min
**Implements**: V2 Part E signal handling (lines 1397-1407)
**Dependencies**: PERF-066
**Sub-tasks**:
- Catch interrupt signals
- Stop running operations
- Clean up resources
- Exit with proper code
**Testing Criteria**:
- Ctrl+C handled gracefully
- Operations stop cleanly
- Resources released
- Exit code correct

### PERF-068: Implement Simple Sandboxing
**Time**: 30 min
**Implements**: V2 Part E ProcessSandbox simplified
**Dependencies**: PERF-063
**Sub-tasks**:
- Set CPU time limits
- Set memory limits
- Restrict file access
- Drop unnecessary privileges
**Testing Criteria**:
- CPU limits enforced
- Memory limits work
- File access restricted
- Privileges dropped

### PERF-069: Add Resource Monitoring
**Time**: 25 min
**Implements**: V2 Part E resource tracking
**Dependencies**: PERF-063
**Sub-tasks**:
- Track CPU usage
- Monitor memory trends
- Count file handles
- Alert on thresholds
**Testing Criteria**:
- CPU tracked accurately
- Memory trends visible
- Handle count correct
- Alerts trigger properly

### PERF-070: Create Resource Pool Manager
**Time**: 25 min
**Implements**: V2 Part E resource pooling
**Dependencies**: PERF-065
**Sub-tasks**:
- Pool file handles
- Pool database connections
- Pool worker processes
- Manage pool lifecycle
**Testing Criteria**:
- Pools initialized
- Resources reused
- Limits enforced
- Clean shutdown

### PERF-071: Add Resource Pressure Handling
**Time**: 25 min
**Implements**: V2 Part E degradation (lines 1330-1381)
**Dependencies**: PERF-069
**Sub-tasks**:
- Detect resource pressure
- Reduce parallelism
- Switch to lighter analysis
- Free resources proactively
**Testing Criteria**:
- Pressure detected early
- Parallelism reduced
- Analysis simplified
- Resources freed

### PERF-072: Resource Management Test Suite
**Time**: 25 min
**Implements**: V2 Part E validation
**Dependencies**: PERF-063 through PERF-071
**Sub-tasks**:
- Test memory limits
- Test cleanup paths
- Test signal handling
- Test resource exhaustion
**Testing Criteria**:
- Limits enforced correctly
- Cleanup always runs
- Signals handled properly
- Graceful degradation works

---

## Phase 6: Integration & System Testing (10 tickets, 275 min)

### PERF-073: Create System Coordinator
**Time**: 30 min
**Implements**: V2 Appendix SystemCoordinator (lines 1737-1773)
**Dependencies**: All component phases
**Sub-tasks**:
- Initialize all components
- Implement analyze_project method
- Coordinate component interaction
- Handle component failures
**Testing Criteria**:
- All components initialized
- Pipeline executes correctly
- Failures handled gracefully
- Results aggregated properly

### PERF-074: Integrate with CLI
**Time**: 30 min
**Implements**: V2 integration with existing CLI
**Dependencies**: PERF-073
**Sub-tasks**:
- Add performance flags to CLI
- Route to SystemCoordinator
- Maintain backward compatibility
- Update help documentation
**Testing Criteria**:
- CLI flags work
- Old commands still work
- Help text updated
- No breaking changes

### PERF-075: Create End-to-End Test Suite
**Time**: 30 min
**Implements**: V2 complete system validation
**Dependencies**: PERF-073
**Sub-tasks**:
- Test full analysis pipeline
- Test with various file counts
- Test error scenarios
- Test resource limits
**Testing Criteria**:
- Pipeline completes
- Handles all file counts
- Errors recovered from
- Limits respected

### PERF-076: Performance Validation Suite
**Time**: 30 min
**Implements**: V2 Success Metrics (lines 1463-1476)
**Dependencies**: PERF-075
**Sub-tasks**:
- Validate <500ms for 10 files
- Validate <2s for 50 files
- Validate <5s for 200 files
- Validate cache performance
**Testing Criteria**:
- All targets met
- Consistent performance
- Cache effective
- No degradation over time

### PERF-077: Load and Stress Testing
**Time**: 30 min
**Implements**: V2 reliability targets (lines 1471-1476)
**Dependencies**: PERF-075
**Sub-tasks**:
- Test with 1000+ files
- Test concurrent operations
- Test memory pressure
- Test error recovery
**Testing Criteria**:
- Handles large scale
- Thread-safe under load
- Memory stays under limit
- Recovers from errors

### PERF-078: Create Integration Documentation
**Time**: 25 min
**Implements**: V2 integration guide
**Dependencies**: PERF-074
**Sub-tasks**:
- Document new CLI flags
- Document configuration options
- Add performance tuning guide
- Include troubleshooting
**Testing Criteria**:
- Flags documented
- Config explained
- Tuning guide clear
- Common issues covered

### PERF-079: Migration from Old System
**Time**: 30 min
**Implements**: V2 system replacement
**Dependencies**: PERF-073
**Sub-tasks**:
- Update existing test suite
- Verify functional parity
- Remove old code paths
- Update dependencies
**Testing Criteria**:
- Tests pass with new system
- Same functionality available
- Old code removed cleanly
- Dependencies updated

### PERF-080: Pre-commit Hook Package
**Time**: 25 min
**Implements**: V2 Part C hook distribution
**Dependencies**: PERF-049
**Sub-tasks**:
- Package hook for distribution
- Test installation process
- Document configuration
- Add to pre-commit registry
**Testing Criteria**:
- Installs via pre-commit
- Works out of box
- Configurable as needed
- Registry submission ready

### PERF-081: Performance Monitoring Setup
**Time**: 25 min
**Implements**: V2 Part D production monitoring
**Dependencies**: PERF-060
**Sub-tasks**:
- Export metrics endpoint
- Create Grafana dashboard
- Set up alerts
- Document metrics
**Testing Criteria**:
- Metrics accessible
- Dashboard functional
- Alerts trigger correctly
- Metrics documented

### PERF-082: Final System Validation
**Time**: 30 min
**Implements**: V2 complete validation
**Dependencies**: All tickets
**Sub-tasks**:
- Run full test suite
- Verify all requirements met
- Performance benchmarks
- Create release checklist
**Testing Criteria**:
- All tests pass
- Requirements satisfied
- Performance targets met
- Ready for release

---

## Summary

**Total Tickets**: 82
**Total Time**: 1,935 minutes (32.25 hours)

### Phase Breakdown:
- Phase 0 (Foundation): 3 tickets, 75 min
- Phase 1 (Parallel): 15 tickets, 395 min
- Phase 2 (Caching): 18 tickets, 460 min
- Phase 3 (Pre-commit): 14 tickets, 360 min
- Phase 4 (Observability): 12 tickets, 300 min
- Phase 5 (Resources): 10 tickets, 250 min
- Phase 6 (Integration): 10 tickets, 275 min

### Key Principles:
1. Every ticket traces to specific V2 design sections
2. Testing criteria ensure correctness
3. Dependencies create logical build order
4. 15-30 minute scope for manageability
5. Atomic but not excessive granularity

---

## Appendix: Missing Elements from V2 Design

### Items Not Ticketed (Deemed Non-Critical for MVP):
1. **Advanced Sandboxing** (V2 lines 1273-1325): Platform-specific sandboxing is complex and not essential for initial performance goals
2. **Graceful Degradation Strategies** (V2 lines 1330-1381): Advanced resilience feature, basic error handling sufficient for MVP
3. **Schema Migration System** (V2 line 259): No existing schema to migrate from
4. **Cache Export/Import**: Not critical for core caching functionality
5. **Advanced Monitoring Features** (Prometheus export details): Basic monitoring sufficient initially

### Rationale:
These features can be added in a future phase after core performance improvements are validated. The MVP focuses on the essential performance optimizations: parallel execution, caching, and pre-commit optimization.