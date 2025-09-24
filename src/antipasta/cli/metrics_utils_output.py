"""Output and formatting helper functions for metrics command."""

import json
from pathlib import Path
from typing import Any

import click

from antipasta.core.violations import FileReport


def print_results(reports: list[FileReport], summary: dict[str, Any], quiet: bool) -> None:
    """Print analysis results."""
    if not quiet:
        _print_summary_header(summary)

    if summary["total_violations"] > 0:
        _print_violations(reports)
        click.echo("\n✗ Code quality check FAILED")
    elif not quiet:
        click.echo("\n✓ Code quality check PASSED")


def _print_summary_header(summary: dict[str, Any]) -> None:
    """Print the summary header section."""
    click.echo("\n" + "=" * 70)
    click.echo("METRICS ANALYSIS SUMMARY")
    click.echo("=" * 70)
    click.echo(f"Total files analyzed: {summary['total_files']}")
    click.echo(f"Files with violations: {summary['files_with_violations']}")
    click.echo(f"Total violations: {summary['total_violations']}")

    _print_violations_by_type(summary)


def _print_violations_by_type(summary: dict[str, Any]) -> None:
    """Print violations grouped by type."""
    if not summary["violations_by_type"]:
        return

    click.echo("\nViolations by type:")
    for metric_type, count in summary["violations_by_type"].items():
        click.echo(f"  - {metric_type}: {count}")


def _print_violations(reports: list[FileReport]) -> None:
    """Print all violations found in reports."""
    click.echo("\n" + "-" * 70)
    click.echo("VIOLATIONS FOUND:")
    click.echo("-" * 70)

    for report in reports:
        if not report.has_violations:
            continue
        for violation in report.violations:
            click.echo(f"❌ {violation.message}")


def output_results(results: dict[str, Any], format: str, quiet: bool) -> None:
    """Output analysis results in the specified format."""
    if format == "json":
        output_json_results(results)
    else:
        output_text_results(results, quiet)


def output_json_results(results: dict[str, Any]) -> None:
    """Output results in JSON format."""
    reports = results["reports"]
    summary = results["summary"]

    output = {
        "summary": summary,
        "reports": [format_report_for_json(report) for report in reports],
    }
    click.echo(json.dumps(output, indent=2))


def format_report_for_json(report: FileReport) -> dict[str, Any]:
    """Format a single file report for JSON output."""
    return {
        "file": str(report.file_path),
        "language": report.language,
        "metrics": [format_metric_for_json(metric) for metric in report.metrics],
        "violations": [format_violation_for_json(violation) for violation in report.violations],
    }


def format_metric_for_json(metric: Any) -> dict[str, Any]:
    """Format a single metric for JSON output."""
    return {
        "type": metric.metric_type.value,
        "value": metric.value,
        "details": metric.details,
        "line_number": metric.line_number,
        "function_name": metric.function_name,
    }


def format_violation_for_json(violation: Any) -> dict[str, Any]:
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


def output_text_results(results: dict[str, Any], quiet: bool) -> None:
    """Output results in text format."""
    reports = results["reports"]
    summary = results["summary"]

    if not quiet or not summary["success"]:
        print_results(reports, summary, quiet)


def display_analysis_status(file_paths: list[Path], quiet: bool) -> None:
    """Display status message about files being analyzed."""
    if not quiet:
        click.echo(f"Analyzing {len(file_paths)} files...")