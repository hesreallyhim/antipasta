# Antipasta Performance Optimization Plan

## Executive Summary

The current implementation processes files sequentially, with each file taking ~350ms. For a typical project with 100+ Python files, this results in 35+ seconds of analysis time. This document outlines a comprehensive plan to reduce this to under 3 seconds through parallel execution and intelligent caching.

## Current Performance Analysis

### Bottlenecks Identified

1. **Sequential Processing**: Files analyzed one at a time in `MetricAggregator.analyze_files()`
2. **Subprocess Overhead**: Each Radon call spawns 4 separate subprocesses (cc, mi, hal, raw)
3. **No Caching**: Every run re-analyzes all files, even unchanged ones
4. **Redundant Parsing**: Files parsed multiple times by different metric extractors

### Performance Metrics
- Single file analysis: ~350ms
- 28 files in antipasta itself: ~10 seconds
- Large project (100+ files): 35+ seconds
- Pre-commit hook tolerance: <2 seconds ideal, <5 seconds acceptable

## Part A: Parallel Execution Design

### Architecture Overview

```python
# New structure in src/antipasta/core/parallel.py
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import cpu_count
import asyncio
```

### Implementation Strategy

#### 1. Worker Pool Architecture

```python
class ParallelAnalyzer:
    def __init__(self, max_workers: int | None = None):
        self.max_workers = max_workers or min(cpu_count(), 8)
        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)

    def analyze_batch(self, files: list[Path]) -> list[FileMetrics]:
        # Batch files by size for load balancing
        batches = self._create_balanced_batches(files)
        futures = []

        for batch in batches:
            future = self.executor.submit(self._analyze_batch_worker, batch)
            futures.append(future)

        results = []
        for future in concurrent.futures.as_completed(futures):
            results.extend(future.result())

        return results
```

#### 2. Load Balancing Strategy

```python
def _create_balanced_batches(self, files: list[Path]) -> list[list[Path]]:
    """Create batches with similar total file sizes"""
    # Sort files by size
    files_with_size = [(f, f.stat().st_size) for f in files]
    files_with_size.sort(key=lambda x: x[1], reverse=True)

    # Distribute using round-robin to balance load
    batches = [[] for _ in range(self.max_workers)]
    batch_sizes = [0] * self.max_workers

    for file, size in files_with_size:
        # Add to smallest batch
        min_idx = batch_sizes.index(min(batch_sizes))
        batches[min_idx].append(file)
        batch_sizes[min_idx] += size

    return [b for b in batches if b]  # Remove empty batches
```

#### 3. Process Pool vs Thread Pool Decision Tree

```python
def choose_executor(self, file_count: int, avg_file_size: int) -> Executor:
    """Choose optimal executor based on workload"""
    if file_count < 5:
        # Small workload: overhead not worth it
        return None  # Use sequential
    elif file_count < 20 and avg_file_size < 10_000:
        # Medium workload, small files: threads sufficient
        return ThreadPoolExecutor(max_workers=4)
    else:
        # Large workload: use processes
        return ProcessPoolExecutor(max_workers=self.max_workers)
```

#### 4. Integration Points

- Modify `MetricAggregator.analyze_files()` to use `ParallelAnalyzer`
- Add `--parallel` flag to CLI (default: auto-detect based on file count)
- Add `--max-workers` flag to CLI (default: CPU count, max 8)

### Expected Performance Gains

- **Sequential (current)**: 100 files × 350ms = 35 seconds
- **Parallel (8 workers)**: 35 seconds ÷ 8 = ~4.4 seconds
- **With caching (below)**: ~1-2 seconds for subsequent runs

## Part B: Caching System Design

### Cache Architecture

```python
# src/antipasta/cache/cache.py
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta
```

### 1. Cache Storage Design

#### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS metrics_cache (
    cache_key TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    antipasta_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_file_path ON metrics_cache(file_path);
CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics_cache(timestamp);
```

#### Cache Key Generation

```python
def generate_cache_key(file_path: Path, config: AntipastaConfig) -> str:
    """Generate deterministic cache key"""
    # Include file content hash
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]

    # Include config hash (sorted for determinism)
    config_str = json.dumps(config.to_dict(), sort_keys=True)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:8]

    # Include antipasta version for invalidation on updates
    version_hash = hashlib.sha256(__version__.encode()).hexdigest()[:4]

    return f"{file_path.stem}_{file_hash}_{config_hash}_{version_hash}"
```

### 2. Cache Manager Implementation

```python
class MetricsCache:
    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".antipasta_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / "metrics.db"
        self._init_db()

    def get(self, file_path: Path, config: AntipastaConfig) -> Optional[FileMetrics]:
        """Retrieve cached metrics if valid"""
        cache_key = generate_cache_key(file_path, config)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT metrics_json, timestamp FROM metrics_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if row:
                metrics_json, timestamp = row
                # Check if file was modified after cache
                if file_path.stat().st_mtime > timestamp:
                    return None

                return FileMetrics.from_json(metrics_json)

        return None

    def set(self, file_path: Path, config: AntipastaConfig, metrics: FileMetrics):
        """Store metrics in cache"""
        cache_key = generate_cache_key(file_path, config)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO metrics_cache
                   (cache_key, file_path, file_hash, config_hash, metrics_json, timestamp, antipasta_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    cache_key,
                    str(file_path),
                    hashlib.sha256(file_path.read_bytes()).hexdigest(),
                    hashlib.sha256(json.dumps(config.to_dict(), sort_keys=True).encode()).hexdigest(),
                    metrics.to_json(),
                    int(datetime.now().timestamp()),
                    __version__
                )
            )
```

### 3. Cache Invalidation Strategy

```python
class CacheInvalidator:
    """Handle cache invalidation scenarios"""

    def invalidate_file(self, file_path: Path):
        """Invalidate cache for specific file"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metrics_cache WHERE file_path = ?", (str(file_path),))

    def invalidate_old_entries(self, max_age_days: int = 7):
        """Remove old cache entries"""
        cutoff = int((datetime.now() - timedelta(days=max_age_days)).timestamp())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metrics_cache WHERE timestamp < ?", (cutoff,))

    def invalidate_version(self, version: str):
        """Invalidate cache from different version"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metrics_cache WHERE antipasta_version != ?", (version,))

    def clear_all(self):
        """Clear entire cache"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM metrics_cache")
```

### 4. Integration with Analysis Pipeline

```python
class CachedMetricAggregator(MetricAggregator):
    def __init__(self, config: AntipastaConfig, use_cache: bool = True):
        super().__init__(config)
        self.cache = MetricsCache() if use_cache else None
        self.cache_hits = 0
        self.cache_misses = 0

    def analyze_files(self, file_paths: list[Path]) -> list[FileReport]:
        """Analyze files with caching"""
        reports = []
        files_to_analyze = []

        # Check cache first
        for file_path in file_paths:
            if self.cache:
                cached_metrics = self.cache.get(file_path, self.config)
                if cached_metrics:
                    self.cache_hits += 1
                    # Convert metrics to report
                    report = self._metrics_to_report(cached_metrics)
                    reports.append(report)
                else:
                    self.cache_misses += 1
                    files_to_analyze.append(file_path)
            else:
                files_to_analyze.append(file_path)

        # Analyze uncached files in parallel
        if files_to_analyze:
            analyzer = ParallelAnalyzer()
            new_reports = analyzer.analyze_batch(files_to_analyze)

            # Cache the results
            if self.cache:
                for report in new_reports:
                    self.cache.set(report.file_path, self.config, report.to_metrics())

            reports.extend(new_reports)

        if self.cache:
            print(f"Cache performance: {self.cache_hits} hits, {self.cache_misses} misses")

        return reports
```

### 5. Cache Configuration

```yaml
# In .antipasta.yaml
cache:
  enabled: true
  directory: ~/.antipasta_cache  # or ./.antipasta_cache for project-local
  max_age_days: 7
  max_size_mb: 100
  compression: gzip  # optional compression for large projects
```

### 6. CLI Integration

```python
# New cache management commands
@cli.group()
def cache():
    """Manage antipasta cache"""
    pass

@cache.command()
def clear():
    """Clear all cached metrics"""
    cache = MetricsCache()
    cache.clear_all()
    click.echo("Cache cleared")

@cache.command()
def stats():
    """Show cache statistics"""
    cache = MetricsCache()
    stats = cache.get_stats()
    click.echo(f"Cache size: {stats['size_mb']:.2f} MB")
    click.echo(f"Entries: {stats['entry_count']}")
    click.echo(f"Oldest entry: {stats['oldest_entry']}")

@cache.command()
@click.option('--days', default=7, help='Remove entries older than N days')
def prune(days: int):
    """Remove old cache entries"""
    cache = MetricsCache()
    invalidator = CacheInvalidator()
    invalidator.invalidate_old_entries(days)
    click.echo(f"Removed entries older than {days} days")
```

## Part C: Pre-commit Hook Optimizations

### 1. Staged Files Only

```python
def get_staged_files() -> list[Path]:
    """Get only staged files for pre-commit"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True
    )

    files = []
    for line in result.stdout.strip().split('\n'):
        if line and line.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
            files.append(Path(line))

    return files
```

### 2. Incremental Analysis

```python
class IncrementalAnalyzer:
    """Analyze only changed parts of files"""

    def get_changed_functions(self, file_path: Path) -> list[str]:
        """Get list of changed functions in staged file"""
        # Get staged version
        staged_content = subprocess.run(
            ["git", "show", f":{file_path}"],
            capture_output=True,
            text=True
        ).stdout

        # Get working version
        working_content = file_path.read_text()

        # Parse both and find differences
        staged_ast = ast.parse(staged_content)
        working_ast = ast.parse(working_content)

        # Compare function signatures and bodies
        changed_functions = []
        # ... comparison logic ...

        return changed_functions
```

## Implementation Timeline

### Phase 1: Parallel Execution (Week 1)
1. Implement `ParallelAnalyzer` class
2. Add load balancing logic
3. Integrate with `MetricAggregator`
4. Add CLI flags for parallel control
5. Test with various file counts

### Phase 2: Caching System (Week 2)
1. Implement SQLite cache backend
2. Create cache key generation
3. Add cache invalidation logic
4. Integrate with analysis pipeline
5. Add cache management CLI commands

### Phase 3: Pre-commit Optimizations (Week 3)
1. Add staged file detection
2. Implement incremental analysis
3. Create pre-commit hook entry point
4. Add `.pre-commit-hooks.yaml`
5. Test with real repositories

## Performance Targets

### Success Metrics
- **Small project (10 files)**: <500ms (from ~3.5s)
- **Medium project (50 files)**: <2s (from ~17s)
- **Large project (200 files)**: <5s (from ~70s)
- **Cached re-run**: <500ms regardless of size
- **Pre-commit (staged files)**: <1s for typical commits

### Benchmarking Plan

```python
# benchmark.py
import time
from pathlib import Path

def benchmark_analysis(file_count: int, use_parallel: bool, use_cache: bool):
    start = time.time()

    config = AntipastaConfig.from_yaml(".antipasta.yaml")
    aggregator = CachedMetricAggregator(config, use_cache=use_cache)

    files = list(Path("test_project").glob("**/*.py"))[:file_count]

    if use_parallel:
        analyzer = ParallelAnalyzer()
        reports = analyzer.analyze_batch(files)
    else:
        reports = aggregator.analyze_files(files)

    elapsed = time.time() - start

    return {
        "file_count": file_count,
        "parallel": use_parallel,
        "cache": use_cache,
        "time": elapsed,
        "files_per_second": file_count / elapsed
    }
```

## Risk Mitigation

### Potential Issues & Solutions

1. **Process Pool Overhead**
   - Solution: Auto-detect when to use threads vs processes
   - Fallback: Sequential processing for small file counts

2. **Cache Corruption**
   - Solution: Atomic writes with WAL mode in SQLite
   - Fallback: Auto-rebuild cache on corruption detection

3. **Memory Usage**
   - Solution: Stream processing for large files
   - Limit: Cap worker pool size at 8

4. **Platform Differences**
   - Solution: Test on Windows, macOS, Linux
   - Fallback: Disable parallel on unsupported platforms

## Conclusion

This two-pronged approach (parallel execution + caching) will reduce analysis time by 95%+ for most use cases. The implementation is designed to be incremental, with each phase providing immediate value. The architecture supports future enhancements like distributed analysis and cloud caching.