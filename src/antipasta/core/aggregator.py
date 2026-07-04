"""Aggregator for collecting and processing metrics across files.

Metric collection is a pure function of file content, so it fans out across a
process pool for large file sets (Python 3.11: processes, not threads — the
parsers are CPU-bound and hold the GIL). Violation checking is cheap and
config-dependent, so it always runs in the parent after collection.
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
from typing import Any, cast

from antipasta.core.cache import MetricsCache
from antipasta.core.config import AntipastaConfig, ComparisonOperator, LanguageConfig, MetricConfig
from antipasta.core.derivation import AnalysisResult, DerivationInput, Deriver
from antipasta.core.detector import Language, LanguageDetector
from antipasta.core.metrics import FactRow, FileMetrics, MetricResult, MetricType
from antipasta.core.violations import FileReport, ProjectReport, Violation, check_metric_violation
from antipasta.runners.base import BaseRunner
from antipasta.runners.javascript.lizard_runner import LizardRunner
from antipasta.runners.python.complexipy_runner import ComplexipyRunner
from antipasta.runners.python.house_style import HouseStyleRunner
from antipasta.runners.python.radon import RadonRunner

# Below this many files a process pool costs more in spawn overhead (~0.5s on
# macOS spawn semantics) than it saves; stay sequential.
PARALLEL_THRESHOLD = 32


def _build_runners() -> dict[Language, list[BaseRunner]]:
    """Construct the language → runners table (JS and TS share one lizard
    instance; its availability check is cached)."""
    lizard_runner = LizardRunner()
    return {
        Language.PYTHON: [RadonRunner(), ComplexipyRunner(), HouseStyleRunner()],
        Language.JAVASCRIPT: [lizard_runner],
        Language.TYPESCRIPT: [lizard_runner],
    }


# Per-process runner table for pool workers, built lazily after spawn (runner
# construction and availability checks then happen once per worker, not once
# per file).
_worker_runners: dict[Language, list[BaseRunner]] | None = None


def _collect_file_metrics(
    task: tuple[str, str],
) -> tuple[list[MetricResult], list[FactRow], list[str]]:
    """Collect raw metrics and facts for one file — worker-safe.

    Takes and returns only picklable data, needs no config, and touches no
    aggregator state; this is the unit of work shipped to pool workers (and
    the same code path the sequential mode runs in-process).
    """
    global _worker_runners
    if _worker_runners is None:
        _worker_runners = _build_runners()

    path_string, language_value = task
    file_path = Path(path_string)
    language = Language(language_value)

    all_metrics: list[MetricResult] = []
    all_facts: list[FactRow] = []
    errors: list[str] = []
    for runner in _worker_runners.get(language, []):
        if runner.is_available():
            file_metrics = runner.analyze(file_path)
            if file_metrics.error:
                errors.append(file_metrics.error)
            else:
                all_metrics.extend(file_metrics.metrics)
                all_facts.extend(file_metrics.facts)
    return all_metrics, all_facts, errors


def _default_derivers() -> list[Deriver]:
    """Derivers registered when the caller doesn't supply an explicit list."""
    from antipasta.core.class_registry import derive_class_registry
    from antipasta.core.tree_shape import derive_tree_shape

    return [derive_tree_shape, derive_class_registry]


def _resolve_jobs(requested: int | None, task_count: int) -> int:
    """Resolve the worker count: explicit arg > ANTIPASTA_JOBS env > auto."""
    if requested is None:
        env_value = os.environ.get("ANTIPASTA_JOBS", "").strip()
        if env_value.isdigit():
            requested = int(env_value)
    if requested is None:
        if task_count < PARALLEL_THRESHOLD:
            return 1
        requested = os.cpu_count() or 1
    return max(1, min(requested, task_count))


# Per-function Halstead rows are informational: they feed `antipasta report`.
# Thresholds keep applying to the file-level Halstead totals only, exactly as
# they did before per-function Halstead extraction was added.
_PER_FUNCTION_INFORMATIONAL: frozenset[MetricType] = frozenset(
    {
        MetricType.HALSTEAD_VOLUME,
        MetricType.HALSTEAD_DIFFICULTY,
        MetricType.HALSTEAD_EFFORT,
        MetricType.HALSTEAD_TIME,
        MetricType.HALSTEAD_BUGS,
    }
)


class MetricAggregator:
    """Aggregates metrics and violations across multiple files."""

    def __init__(
        self,
        config: AntipastaConfig,
        cache: MetricsCache | None = None,
        derivers: list[Deriver] | None = None,
    ) -> None:
        """Initialize the aggregator with configuration.

        Args:
            config: Antipasta configuration
            cache: Metric cache (default: a content-addressed store under the
                user cache dir; see core.cache for locations and kill switches)
            derivers: Whole-program derivation functions run after per-file
                collection (default: none registered in Phase 0; see
                docs/design/metrics-adoption-plan.md)
        """
        self.config = config
        self.cache = cache if cache is not None else MetricsCache()
        self.derivers: list[Deriver] = (
            list(derivers) if derivers is not None else _default_derivers()
        )
        self.detector = LanguageDetector(ignore_patterns=config.ignore_patterns)

        # Load .gitignore patterns if enabled
        if config.use_gitignore:
            gitignore_path = Path(".gitignore")
            if gitignore_path.exists():
                self.detector.add_gitignore(gitignore_path)

        # Runner table (kept as an attribute: tests and callers introspect it;
        # pool workers build their own per-process copy via _build_runners).
        self.runners: dict[Language, list[BaseRunner]] = _build_runners()

    def analyze_files(self, file_paths: list[Path], jobs: int | None = None) -> list[FileReport]:
        """Analyze multiple files and generate per-file reports.

        Compatibility wrapper around :meth:`analyze` for callers that only
        consume file reports.
        """
        return self.analyze(file_paths, jobs=jobs).file_reports

    def analyze(
        self,
        file_paths: list[Path],
        jobs: int | None = None,
        root: Path | None = None,
    ) -> AnalysisResult:
        """Analyze files and run project-scoped derivations.

        Args:
            file_paths: List of files to analyze
            jobs: Worker process count (None = auto: sequential for small
                sets, one worker per CPU beyond PARALLEL_THRESHOLD files;
                overridable via the ANTIPASTA_JOBS environment variable)
            root: Directory the derivation stage treats as the project root
                (default: the current working directory)

        Returns:
            AnalysisResult with per-file reports and project reports
        """
        # Group files by language and resolve each language's config once
        files_by_language = self.detector.group_by_language(file_paths)

        work: list[tuple[Path, Language, LanguageConfig]] = []
        for language, files in files_by_language.items():
            if not self.runners.get(language, []):
                # Skip unsupported languages
                continue

            lang_config = self.config.get_language_config(language.value)
            if not lang_config:
                # Use defaults if no specific config
                lang_config = self._create_default_language_config(language)

            for file_path in files:
                work.append((file_path, language, lang_config))

        # Collect metrics (the expensive, config-free part — cached and
        # parallelizable), then derive violations in the parent (cheap,
        # config-dependent — threshold changes never invalidate the cache).
        collected = self._collect_with_cache(work, jobs)

        facts_by_file: dict[Path, list[FactRow]] = {}
        file_reports: list[FileReport] = []
        for (file_path, language, lang_config), (metrics, facts, errors) in zip(
            work, collected, strict=True
        ):
            if facts:
                facts_by_file[file_path] = facts
            file_reports.append(
                self._finalize_report(file_path, language, metrics, errors, lang_config.metrics)
            )

        return AnalysisResult(
            file_reports=file_reports,
            project_reports=self._derive(file_reports, facts_by_file, root),
        )

    def _derive(
        self,
        file_reports: list[FileReport],
        facts_by_file: dict[Path, list[FactRow]],
        root: Path | None,
    ) -> list[ProjectReport]:
        """Run every registered deriver over the collected facts."""
        if not self.derivers:
            return []
        derivation_input = DerivationInput(
            file_reports=file_reports,
            facts_by_file=facts_by_file,
            root=(root or Path.cwd()).resolve(),
            config=self.config,
        )
        project_reports: list[ProjectReport] = []
        for deriver in self.derivers:
            project_reports.extend(deriver(derivation_input))
        return project_reports

    def _collect_with_cache(
        self, work: list[tuple[Path, Language, LanguageConfig]], jobs: int | None
    ) -> list[tuple[list[MetricResult], list[FactRow], list[str]]]:
        """Serve collection results from the cache; dispatch only the misses."""
        collected: list[tuple[list[MetricResult], list[FactRow], list[str]] | None] = []
        keys: list[str | None] = []
        miss_tasks: list[tuple[str, str]] = []
        miss_indices: list[int] = []

        for index, (file_path, language, _) in enumerate(work):
            key: str | None = None
            cached: tuple[list[MetricResult], list[FactRow], list[str]] | None = None
            if self.cache.enabled:
                try:
                    content = file_path.read_bytes()
                except OSError:
                    content = None
                if content is not None:
                    key = self.cache.key_for(content, language.value)
                    cached = self.cache.get(key, file_path)
            keys.append(key)
            collected.append(cached)
            if cached is None:
                miss_tasks.append((str(file_path), language.value))
                miss_indices.append(index)

        # Only misses reach the (possibly parallel) collection stage, so a
        # warm run never pays pool spawn overhead.
        results = self._collect_all(miss_tasks, jobs)
        for index, result in zip(miss_indices, results, strict=True):
            collected[index] = result
            key = keys[index]
            if key is not None:
                self.cache.put(key, *result)

        # Every slot is now filled: hits at read time, misses just above.
        # (A cast, not a filter — dropping a slot would silently misalign
        # reports with `work`; unpacking None downstream fails loudly.)
        return cast("list[tuple[list[MetricResult], list[FactRow], list[str]]]", collected)

    def _collect_all(
        self, tasks: list[tuple[str, str]], jobs: int | None
    ) -> list[tuple[list[MetricResult], list[FactRow], list[str]]]:
        """Run metric collection for every task, in-process or via a pool."""
        worker_count = _resolve_jobs(jobs, len(tasks))
        if worker_count <= 1:
            return [_collect_file_metrics(task) for task in tasks]

        chunksize = max(1, len(tasks) // (worker_count * 4))
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            # map preserves input order, keeping report order deterministic.
            return list(pool.map(_collect_file_metrics, tasks, chunksize=chunksize))

    def _finalize_report(
        self,
        file_path: Path,
        language: Language,
        all_metrics: list[MetricResult],
        errors: list[str],
        metric_configs: list[MetricConfig],
    ) -> FileReport:
        """Combine collected metrics with config-derived violations."""
        # Only report errors if no metrics were collected
        error = None
        if errors and not all_metrics:
            error = "; ".join(errors)

        violations = []
        if all_metrics:
            # Create a temporary FileMetrics object for violation checking
            combined_metrics = FileMetrics(
                file_path=file_path,
                language=language.value,
                metrics=all_metrics,
                error=error,
            )
            violations = self._check_violations(combined_metrics, metric_configs)

        return FileReport(
            file_path=file_path,
            language=language.value,
            metrics=all_metrics,
            violations=violations,
            error=error,
        )

    def _check_violations(
        self, file_metrics: FileMetrics, metric_configs: list[MetricConfig]
    ) -> list[Violation]:
        """Check metrics against configured thresholds.

        Args:
            file_metrics: Metrics for the file
            metric_configs: Configurations to check against

        Returns:
            List of violations found
        """
        violations = []

        # Create a map of metric type to config for easy lookup
        config_map = {config.type: config for config in metric_configs}

        for metric in file_metrics.metrics:
            # Skip metrics without configuration
            if metric.metric_type not in config_map:
                continue

            # Skip informational per-function rows (see _PER_FUNCTION_INFORMATIONAL)
            if (
                metric.function_name is not None
                and metric.metric_type in _PER_FUNCTION_INFORMATIONAL
            ):
                continue

            config = config_map[metric.metric_type]
            violation = check_metric_violation(metric, config)
            if violation:
                violations.append(violation)

        return violations

    def _create_default_language_config(self, language: Language) -> LanguageConfig:
        """Create default language configuration using defaults.

        Args:
            language: Language to create config for

        Returns:
            Language configuration with default metrics
        """
        from antipasta.core.config import LanguageConfig

        # Map default values to metric configs
        default_metrics = []

        if language == Language.PYTHON:
            default_metrics = [
                MetricConfig(
                    type=MetricType.CYCLOMATIC_COMPLEXITY,
                    threshold=self.config.defaults.max_cyclomatic_complexity,
                    comparison=ComparisonOperator.LE,
                ),
                MetricConfig(
                    type=MetricType.MAINTAINABILITY_INDEX,
                    threshold=self.config.defaults.min_maintainability_index,
                    comparison=ComparisonOperator.GE,
                ),
                MetricConfig(
                    type=MetricType.HALSTEAD_VOLUME,
                    threshold=self.config.defaults.max_halstead_volume,
                    comparison=ComparisonOperator.LE,
                ),
                MetricConfig(
                    type=MetricType.HALSTEAD_DIFFICULTY,
                    threshold=self.config.defaults.max_halstead_difficulty,
                    comparison=ComparisonOperator.LE,
                ),
                MetricConfig(
                    type=MetricType.HALSTEAD_EFFORT,
                    threshold=self.config.defaults.max_halstead_effort,
                    comparison=ComparisonOperator.LE,
                ),
                MetricConfig(
                    type=MetricType.COGNITIVE_COMPLEXITY,
                    threshold=self.config.defaults.max_cognitive_complexity,
                    comparison=ComparisonOperator.LE,
                ),
            ]
        elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            # lizard produces cyclomatic complexity only; enabling other
            # metric thresholds here would silently never fire.
            default_metrics = [
                MetricConfig(
                    type=MetricType.CYCLOMATIC_COMPLEXITY,
                    threshold=self.config.defaults.max_cyclomatic_complexity,
                    comparison=ComparisonOperator.LE,
                ),
            ]

        return LanguageConfig(
            name=language.value,
            metrics=default_metrics,
        )

    def generate_summary(self, reports: list[FileReport]) -> dict[str, Any]:
        """Generate a summary of all reports.

        Args:
            reports: List of file reports

        Returns:
            Summary dictionary with statistics
        """
        total_files = len(reports)
        files_with_violations = sum(1 for r in reports if r.has_violations)
        total_violations = sum(r.violation_count for r in reports)

        # Group violations by type
        violations_by_type: dict[str, int] = defaultdict(int)
        for report in reports:
            for violation in report.violations:
                violations_by_type[violation.metric_type.value] += 1

        # Group by language
        files_by_language: dict[str, int] = defaultdict(int)
        for report in reports:
            files_by_language[report.language] += 1

        return {
            "total_files": total_files,
            "files_with_violations": files_with_violations,
            "total_violations": total_violations,
            "violations_by_type": dict(violations_by_type),
            "files_by_language": dict(files_by_language),
            "success": total_violations == 0,
        }
