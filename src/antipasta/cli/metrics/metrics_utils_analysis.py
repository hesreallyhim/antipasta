"""Analysis workflow helper functions for metrics command."""

from pathlib import Path
import sys
from typing import Any

import click

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_override import ConfigOverride
from antipasta.engine import MetricAggregator

from .metrics_utils_collection import collect_files


def determine_files_to_analyze(
    files: tuple[Path, ...],
    directory: Path | None,
    cfg: AntipastaConfig,
    override: ConfigOverride,
    quiet: bool,
) -> list[Path]:
    """Determine which files to analyze based on input parameters."""
    file_paths = collect_files(files, directory, cfg, override)

    if _should_use_default_directory(file_paths, files, directory):
        file_paths = handle_default_directory_analysis(cfg, override, quiet)

    validate_files_found(file_paths)
    if not quiet:
        click.echo(f"Analyzing {len(file_paths)} files...")

    return file_paths


def _should_use_default_directory(
    file_paths: list[Path], files: tuple[Path, ...], directory: Path | None
) -> bool:
    """Check if we should analyze the current directory by default."""
    return not file_paths and not files and not directory


def handle_default_directory_analysis(
    cfg: AntipastaConfig, override: ConfigOverride, quiet: bool
) -> list[Path]:
    """Handle analysis when no specific files or directory are specified."""
    if not quiet:
        click.echo("No files or directory specified, analyzing current directory...")
    return collect_files((), Path.cwd(), cfg, override)


def validate_files_found(file_paths: list[Path]) -> None:
    """Validate that files were found for analysis."""
    if not file_paths:
        click.echo("No files found to analyze", err=True)
        sys.exit(1)


def execute_analysis(
    file_paths: list[Path],
    cfg: AntipastaConfig,
    quiet: bool,
    root: Path | None = None,
) -> dict[str, Any]:
    """Execute metrics analysis on the specified files.

    ``root`` anchors project-scoped derivation (module names, directory
    subjects); the metrics/report commands pass their -d directory.
    """
    aggregator = MetricAggregator(cfg)
    result = aggregator.analyze(file_paths, root=root)
    summary = aggregator.generate_summary(result.file_reports)
    _fold_project_findings(summary, result.project_reports)

    return {
        "reports": result.file_reports,
        "project_reports": result.project_reports,
        "summary": summary,
    }


def _fold_project_findings(summary: dict[str, Any], project_reports: list[Any]) -> None:
    """Fold project-scoped violations into the summary (counts + exit code)."""
    project_violations = sum(report.violation_count for report in project_reports)
    if not project_violations:
        return
    summary["total_violations"] += project_violations
    summary["success"] = False
    by_type = summary["violations_by_type"]
    for report in project_reports:
        for violation in report.violations:
            key = violation.metric_type.value
            by_type[key] = by_type.get(key, 0) + 1


def exit_with_appropriate_code(summary: dict[str, Any]) -> None:
    """Exit with appropriate status code based on analysis results."""
    sys.exit(0 if summary["success"] else 2)
