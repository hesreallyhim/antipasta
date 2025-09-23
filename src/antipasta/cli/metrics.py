"""Metrics analysis command."""

import json
import sys
from pathlib import Path
from typing import Any

import click

from antipasta.cli.validation_utils import format_validation_error_for_cli, get_metric_help_text
from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.detector import LanguageDetector
from antipasta.core.violations import FileReport


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=".antipasta.yaml",
    help="Path to configuration file",
)
@click.option(
    "--files",
    "-f",
    multiple=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Files to analyze (can be specified multiple times)",
)
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Directory to analyze recursively",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Only show violations, suppress other output",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--include-pattern",
    "-i",
    multiple=True,
    help=(
        "Force include files matching pattern (overrides ignore patterns, "
        "can be specified multiple times"
    ),
)
@click.option(
    "--exclude-pattern",
    "-e",
    multiple=True,
    help="Add additional exclusion patterns (can be specified multiple times)",
)
@click.option(
    "--threshold",
    "-t",
    multiple=True,
    help="Override metric thresholds (format: metric_type=value, e.g., cyclomatic_complexity=15)",
)
@click.option(
    "--no-gitignore",
    is_flag=True,
    help="Disable .gitignore usage for this run",
)
@click.option(
    "--force-analyze",
    is_flag=True,
    help="Analyze all files, ignoring all exclusions",
)
def metrics(
    config: Path,
    files: tuple[Path, ...],
    directory: Path | None,
    quiet: bool,
    format: str,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> None:
    """Analyze code metrics for specified files.

    Exits with code 0 if all metrics pass, 2 if violations found.

    For an interactive terminal UI, use 'antipasta tui' instead.
    """
    configuration = _prepare_configuration(config, threshold, quiet)
    override = _create_and_configure_override(
        include_pattern, exclude_pattern, threshold, no_gitignore, force_analyze
    )
    final_config = _apply_overrides_to_configuration(configuration, override, quiet,
                                                    force_analyze, include_pattern,
                                                    exclude_pattern, threshold, no_gitignore)

    target_files = _determine_files_to_analyze(files, directory, final_config, override, quiet)
    analysis_results = _execute_analysis(target_files, final_config, quiet)
    _output_results(analysis_results, format, quiet)
    _exit_with_appropriate_code(analysis_results["summary"])


def _load_configuration(config: Path, quiet: bool) -> AntipastaConfig:
    """Load configuration from file or generate default."""
    try:
        if config.exists():
            cfg = AntipastaConfig.from_yaml(config)
            if not quiet:
                click.echo(f"Using configuration: {config}")
        else:
            # Config file doesn't exist, show helpful message and use defaults
            if not quiet:
                click.echo(f"Configuration file '{config}' not found.", err=True)
                click.echo(
                    "Run 'antipasta config generate' to create a configuration file.", err=True
                )
                click.echo("Using default configuration for now...")
            cfg = AntipastaConfig.generate_default()
        return cfg
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)


def _collect_files(
    files: tuple[Path, ...],
    directory: Path | None,
    config: AntipastaConfig,
    override: ConfigOverride | None,
) -> list[Path]:
    """Collect all files to analyze, respecting gitignore patterns and overrides."""
    # Determine base directory for pattern matching
    base_dir = directory if directory else Path.cwd()

    # Create a detector with config's ignore patterns and override include patterns
    detector = LanguageDetector(
        ignore_patterns=config.ignore_patterns,
        include_patterns=(
            override.include_patterns if override and override.include_patterns else []
        ),
        base_dir=base_dir,
    )

    # Load .gitignore if enabled
    if config.use_gitignore:
        gitignore_path = base_dir / ".gitignore"
        if gitignore_path.exists():
            detector.add_gitignore(gitignore_path)

    file_paths = list(files)

    # Add files from directory if specified
    if directory:
        patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        all_files: list[Path] = []
        for pattern in patterns:
            all_files.extend(directory.glob(pattern))

        # Filter out ignored files
        for file_path in all_files:
            if not detector.should_ignore(file_path):
                file_paths.append(file_path)

    # Remove duplicates
    return list(set(file_paths))


def _print_results(reports: list[FileReport], summary: dict[str, Any], quiet: bool) -> None:
    """Print analysis results."""
    if not quiet:
        click.echo("\n" + "=" * 70)
        click.echo("METRICS ANALYSIS SUMMARY")
        click.echo("=" * 70)
        click.echo(f"Total files analyzed: {summary['total_files']}")
        click.echo(f"Files with violations: {summary['files_with_violations']}")
        click.echo(f"Total violations: {summary['total_violations']}")

        if summary["violations_by_type"]:
            click.echo("\nViolations by type:")
            for metric_type, count in summary["violations_by_type"].items():
                click.echo(f"  - {metric_type}: {count}")

    # Print violations
    if summary["total_violations"] > 0:
        click.echo("\n" + "-" * 70)
        click.echo("VIOLATIONS FOUND:")
        click.echo("-" * 70)

        for report in reports:
            if report.has_violations:
                for violation in report.violations:
                    click.echo(f"❌ {violation.message}")

        click.echo("\n✗ Code quality check FAILED")
    elif not quiet:
        click.echo("\n✓ Code quality check PASSED")


def _prepare_configuration(config: Path, threshold: tuple[str, ...], quiet: bool) -> AntipastaConfig:
    """Load configuration and apply threshold overrides."""
    cfg = _load_configuration(config, quiet)
    return cfg


def _handle_threshold_parsing_error(error: ValueError, threshold_str: str) -> None:
    """Handle threshold parsing errors with helpful messages."""
    click.echo(f"❌ Error: {format_validation_error_for_cli(error)}", err=True)

    # If it's a range error, show the valid range
    if '=' in threshold_str:
        metric_type = threshold_str.split('=')[0].strip()
        help_text = get_metric_help_text(metric_type)
        if help_text and metric_type in help_text:
            click.echo(f"   ℹ️  {help_text}", err=True)


def _create_and_configure_override(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> ConfigOverride:
    """Create configuration override object and parse threshold overrides."""
    override = ConfigOverride(
        include_patterns=list(include_pattern),
        exclude_patterns=list(exclude_pattern),
        disable_gitignore=no_gitignore,
        force_analyze=force_analyze,
    )

    _parse_threshold_overrides_into_override(override, threshold)
    return override


def _parse_threshold_overrides_into_override(override: ConfigOverride, threshold: tuple[str, ...]) -> None:
    """Parse threshold override strings and add them to the override object."""
    for threshold_str in threshold:
        try:
            override.parse_threshold_string(threshold_str)
        except ValueError as e:
            _handle_threshold_parsing_error(e, threshold_str)
            sys.exit(1)


def _apply_overrides_to_configuration(
    cfg: AntipastaConfig,
    override: ConfigOverride,
    quiet: bool,
    force_analyze: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
) -> AntipastaConfig:
    """Apply configuration overrides and display status messages."""
    if override.has_overrides():
        cfg = cfg.apply_overrides(override)
        _display_override_status_messages(
            quiet, force_analyze, include_pattern, exclude_pattern, threshold, no_gitignore
        )
    return cfg


def _display_override_status_messages(
    quiet: bool,
    force_analyze: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
) -> None:
    """Display status messages about applied configuration overrides."""
    if quiet:
        return

    if force_analyze:
        click.echo("Force analyzing all files (ignoring exclusions)...")
    elif include_pattern:
        click.echo(f"Including patterns: {', '.join(include_pattern)}")
    if exclude_pattern:
        click.echo(f"Additional exclusions: {', '.join(exclude_pattern)}")
    if threshold:
        click.echo(f"Threshold overrides: {', '.join(threshold)}")
    if no_gitignore:
        click.echo("Ignoring .gitignore patterns")


def _determine_files_to_analyze(
    files: tuple[Path, ...],
    directory: Path | None,
    cfg: AntipastaConfig,
    override: ConfigOverride,
    quiet: bool,
) -> list[Path]:
    """Determine which files to analyze based on input parameters."""
    file_paths = _collect_files(files, directory, cfg, override)

    # If no files or directory specified, default to current directory
    if not file_paths and not files and not directory:
        file_paths = _handle_default_directory_analysis(cfg, override, quiet)

    _validate_files_found(file_paths)
    _display_analysis_status(file_paths, quiet)

    return file_paths


def _handle_default_directory_analysis(
    cfg: AntipastaConfig, override: ConfigOverride, quiet: bool
) -> list[Path]:
    """Handle analysis when no specific files or directory are specified."""
    if not quiet:
        click.echo("No files or directory specified, analyzing current directory...")
    return _collect_files((), Path.cwd(), cfg, override)


def _validate_files_found(file_paths: list[Path]) -> None:
    """Validate that files were found for analysis."""
    if not file_paths:
        click.echo("No files found to analyze", err=True)
        sys.exit(1)


def _display_analysis_status(file_paths: list[Path], quiet: bool) -> None:
    """Display status message about files being analyzed."""
    if not quiet:
        click.echo(f"Analyzing {len(file_paths)} files...")


def _execute_analysis(
    file_paths: list[Path], cfg: AntipastaConfig, quiet: bool
) -> dict[str, Any]:
    """Execute metrics analysis on the specified files."""
    aggregator = MetricAggregator(cfg)
    reports = aggregator.analyze_files(file_paths)
    summary = aggregator.generate_summary(reports)

    return {
        "reports": reports,
        "summary": summary,
    }


def _output_results(results: dict[str, Any], format: str, quiet: bool) -> None:
    """Output analysis results in the specified format."""
    if format == "json":
        _output_json_results(results)
    else:
        _output_text_results(results, quiet)


def _output_json_results(results: dict[str, Any]) -> None:
    """Output results in JSON format."""
    reports = results["reports"]
    summary = results["summary"]

    output = {
        "summary": summary,
        "reports": [
            _format_report_for_json(report)
            for report in reports
        ],
    }
    click.echo(json.dumps(output, indent=2))


def _format_report_for_json(report: FileReport) -> dict[str, Any]:
    """Format a single file report for JSON output."""
    return {
        "file": str(report.file_path),
        "language": report.language,
        "metrics": [
            _format_metric_for_json(metric)
            for metric in report.metrics
        ],
        "violations": [
            _format_violation_for_json(violation)
            for violation in report.violations
        ],
    }


def _format_metric_for_json(metric: Any) -> dict[str, Any]:
    """Format a single metric for JSON output."""
    return {
        "type": metric.metric_type.value,
        "value": metric.value,
        "details": metric.details,
        "line_number": metric.line_number,
        "function_name": metric.function_name,
    }


def _format_violation_for_json(violation: Any) -> dict[str, Any]:
    """Format a single violation for JSON output."""
    return {
        "type": violation.metric_type.value,
        "message": violation.message,
        "line_number": violation.line_number,
        "function": violation.function_name,
        "value": violation.value,
        "threshold": violation.threshold,
        "comparison": violation.comparison.value,
    }


def _output_text_results(results: dict[str, Any], quiet: bool) -> None:
    """Output results in text format."""
    reports = results["reports"]
    summary = results["summary"]

    if not quiet or not summary["success"]:
        _print_results(reports, summary, quiet)


def _exit_with_appropriate_code(summary: dict[str, Any]) -> None:
    """Exit with appropriate status code based on analysis results."""
    sys.exit(0 if summary["success"] else 2)
