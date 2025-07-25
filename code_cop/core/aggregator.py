"""Aggregator for collecting and processing metrics across files."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from code_cop.core.config import CodeCopConfig, MetricConfig
from code_cop.core.detector import Language, LanguageDetector
from code_cop.core.metrics import FileMetrics, MetricType
from code_cop.core.violations import FileReport, Violation, check_metric_violation
from code_cop.runners.base import BaseRunner
from code_cop.runners.python.radon import RadonRunner


class MetricAggregator:
    """Aggregates metrics and violations across multiple files."""

    def __init__(self, config: CodeCopConfig) -> None:
        """Initialize the aggregator with configuration.

        Args:
            config: Code cop configuration
        """
        self.config = config
        self.detector = LanguageDetector(ignore_patterns=config.ignore_patterns)

        # Load .gitignore patterns if enabled
        if config.use_gitignore:
            gitignore_path = Path(".gitignore")
            if gitignore_path.exists():
                self.detector.add_gitignore(gitignore_path)

        self.runners: dict[Language, BaseRunner] = {
            Language.PYTHON: RadonRunner(),
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
            # Get the runner for this language
            runner = self.runners.get(language)
            if not runner or not runner.is_available():
                # Skip unsupported languages
                continue

            # Get language configuration
            lang_config = self.config.get_language_config(language.value)
            if not lang_config:
                # Use defaults if no specific config
                lang_config = self._create_default_language_config(language)

            # Analyze each file
            for file_path in files:
                report = self._analyze_file(file_path, language, runner, lang_config.metrics)
                reports.append(report)

        return reports

    def _analyze_file(
        self,
        file_path: Path,
        language: Language,
        runner: BaseRunner,
        metric_configs: list[MetricConfig],
    ) -> FileReport:
        """Analyze a single file.

        Args:
            file_path: Path to the file
            language: Detected language
            runner: Runner to use for analysis
            metric_configs: Metric configurations to check

        Returns:
            FileReport with metrics and violations
        """
        # Run the analysis
        file_metrics = runner.analyze(file_path)

        # Check for violations
        violations = []
        if not file_metrics.error:
            violations = self._check_violations(file_metrics, metric_configs)

        return FileReport(
            file_path=file_path,
            language=language.value,
            metrics=file_metrics.metrics,
            violations=violations,
            error=file_metrics.error,
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

    def _create_default_language_config(self, language: Language) -> Any:
        """Create default language configuration using defaults.

        Args:
            language: Language to create config for

        Returns:
            Language configuration with default metrics
        """
        from code_cop.core.config import LanguageConfig

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


from code_cop.core.config import ComparisonOperator