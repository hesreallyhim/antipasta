"""Analysis workflow helper functions for metrics command."""

from pathlib import Path
import sys
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride

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


def execute_analysis(file_paths: list[Path], cfg: AntipastaConfig, quiet: bool) -> dict[str, Any]:
    """Execute metrics analysis on the specified files."""
    aggregator = MetricAggregator(cfg)
    reports = aggregator.analyze_files(file_paths)
    summary = aggregator.generate_summary(reports)

    return {
        "reports": reports,
        "summary": summary,
    }


def exit_with_appropriate_code(summary: dict[str, Any]) -> None:
    """Exit with appropriate status code based on analysis results."""
    sys.exit(0 if summary["success"] else 2)
