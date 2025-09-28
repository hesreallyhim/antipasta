"""Metrics analysis command."""

import json
import sys
from pathlib import Path
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
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
def metrics(
    config: Path, files: tuple[Path, ...], directory: Path | None, quiet: bool, format: str
) -> None:
    """Analyze code metrics for specified files.

    Exits with code 0 if all metrics pass, 2 if violations found.

    For an interactive terminal UI, use 'antipasta tui' instead.
    """
    # Load configuration
    cfg = _load_configuration(config, quiet)

    # Collect files to analyze
    file_paths = _collect_files(files, directory, cfg)

    # If no files or directory specified, default to current directory
    if not file_paths and not files and not directory:
        if not quiet:
            click.echo("No files or directory specified, analyzing current directory...")
        file_paths = _collect_files((), Path.cwd(), cfg)

    if not file_paths:
        click.echo("No files found to analyze", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(f"Analyzing {len(file_paths)} files...")

    # Analyze files
    aggregator = MetricAggregator(cfg)
    reports = aggregator.analyze_files(file_paths)

    # Generate summary
    summary = aggregator.generate_summary(reports)

    # Print results based on format
    if format == "json":
        # Output JSON format
        output = {
            "summary": summary,
            "reports": [
                {
                    "file": str(report.file_path),
                    "language": report.language,
                    "metrics": [
                        {
                            "type": metric.metric_type.value,
                            "value": metric.value,
                            "details": metric.details,
                            "line_number": metric.line_number,
                            "function_name": metric.function_name,
                        }
                        for metric in report.metrics
                    ],
                    "violations": [
                        {
                            "type": v.metric_type.value,
                            "message": v.message,
                            "line_number": v.line_number,
                            "function": v.function_name,
                            "value": v.value,
                            "threshold": v.threshold,
                            "comparison": v.comparison.value,
                        }
                        for v in report.violations
                    ],
                }
                for report in reports
            ],
        }
        click.echo(json.dumps(output, indent=2))
    else:
        # Default text format
        if not quiet or not summary["success"]:
            _print_results(reports, summary, quiet)

    # Exit with appropriate code
    sys.exit(0 if summary["success"] else 2)


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
    files: tuple[Path, ...], directory: Path | None, config: AntipastaConfig
) -> list[Path]:
    """Collect all files to analyze, respecting gitignore patterns."""
    # Create a detector with config's ignore patterns
    detector = LanguageDetector(ignore_patterns=config.ignore_patterns)

    # Load .gitignore if enabled
    if config.use_gitignore:
        gitignore_path = Path(".gitignore")
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
