"""Aggregator for collecting and processing metrics across files."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from antipasta.core.config import AntipastaConfig, ComparisonOperator, LanguageConfig, MetricConfig
from antipasta.core.detector import Language, LanguageDetector
from antipasta.core.metrics import FileMetrics, MetricType
from antipasta.core.violations import FileReport, Violation, check_metric_violation
from antipasta.runners.base import BaseRunner
from antipasta.runners.python.complexipy_runner import ComplexipyRunner
from antipasta.runners.python.radon import RadonRunner


class MetricAggregator:
    """Aggregates metrics and violations across multiple files."""

    def __init__(self, config: AntipastaConfig) -> None:
        """Initialize the aggregator with configuration.

        Args:
            config: Antipasta configuration
        """
        self.config = config
        self.detector = LanguageDetector(ignore_patterns=config.ignore_patterns)

        # Load .gitignore patterns if enabled
        if config.use_gitignore:
            gitignore_path = Path(".gitignore")
            if gitignore_path.exists():
                self.detector.add_gitignore(gitignore_path)

        # Initialize runners for each language
        self.runners: dict[Language, list[BaseRunner]] = {
            Language.PYTHON: [RadonRunner(), ComplexipyRunner()],
        }

    def analyze_files(self, file_paths: list[Path]) -> list[FileReport]:
        """Analyze multiple files and generate reports.

        Args:
            file_paths: List of files to analyze

        Returns:
            List of file reports with metrics and violations
        """
        reports = []

        # Group files by language
        files_by_language = self.detector.group_by_language(file_paths)

        for language, files in files_by_language.items():
            # Get the runners for this language
            runners = self.runners.get(language, [])
            if not runners:
                # Skip unsupported languages
                continue

            # Get language configuration
            lang_config = self.config.get_language_config(language.value)
            if not lang_config:
                # Use defaults if no specific config
                lang_config = self._create_default_language_config(language)

            # Analyze each file
            for file_path in files:
                report = self._analyze_file(file_path, language, runners, lang_config.metrics)
                reports.append(report)

        return reports

    def _analyze_file(
        self,
        file_path: Path,
        language: Language,
        runners: list[BaseRunner],
        metric_configs: list[MetricConfig],
    ) -> FileReport:
        """Analyze a single file with multiple runners.

        Args:
            file_path: Path to the file
            language: Detected language
            runners: List of runners to use for analysis
            metric_configs: Metric configurations to check

        Returns:
            FileReport with metrics and violations
        """
        # Collect metrics from all available runners
        all_metrics = []
        errors = []

        for runner in runners:
            if runner.is_available():
                # Run the analysis
                file_metrics = runner.analyze(file_path)

                if file_metrics.error:
                    errors.append(file_metrics.error)
                else:
                    all_metrics.extend(file_metrics.metrics)

        # Combine errors if any
        error = None
        if errors and not all_metrics:
            # Only report errors if no metrics were collected
            error = "; ".join(errors)

        # Check for violations
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
