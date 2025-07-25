"""Metrics analysis command."""

import sys
from pathlib import Path

import click

from code_cop.core.aggregator import MetricAggregator
from code_cop.core.config import CodeCopConfig


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=".code_cop.yaml",
    help="Path to configuration file",
)
@click.option(
    "--files",
    "-f",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
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
def metrics(
    config: Path, files: tuple[Path, ...], directory: Path | None, quiet: bool
) -> None:
    """Analyze code metrics for specified files.

    Exits with code 0 if all metrics pass, 2 if violations found.
    """
    # Load configuration
    try:
        if config.exists():
            cfg = CodeCopConfig.from_yaml(config)
            if not quiet:
                click.echo(f"Using configuration: {config}")
        else:
            cfg = CodeCopConfig.generate_default()
            if not quiet:
                click.echo("Using default configuration")
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)

    # Collect files to analyze
    file_paths = list(files)

    # Add files from directory if specified
    if directory:
        for pattern in ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]:
            file_paths.extend(directory.glob(pattern))

    if not file_paths:
        click.echo("No files specified to analyze", err=True)
        sys.exit(1)

    # Remove duplicates
    file_paths = list(set(file_paths))

    if not quiet:
        click.echo(f"Analyzing {len(file_paths)} files...")

    # Analyze files
    aggregator = MetricAggregator(cfg)
    reports = aggregator.analyze_files(file_paths)

    # Generate summary
    summary = aggregator.generate_summary(reports)

    # Print results
    if not quiet or not summary["success"]:
        _print_results(reports, summary, quiet)

    # Exit with appropriate code
    sys.exit(0 if summary["success"] else 2)


def _print_results(reports, summary, quiet):
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