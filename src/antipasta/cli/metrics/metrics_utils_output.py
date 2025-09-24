import json
from typing import Any

import click

from antipasta.core.violations import FileReport

_SUMMARY_DIVIDER, _VIOLATION_DIVIDER = "=" * 70, "-" * 70


def print_results(reports: list[FileReport], summary: dict[str, Any], quiet: bool) -> None:
    if not quiet:
        click.echo(_format_summary(summary))

    if summary["total_violations"] > 0:
        click.echo(_format_violations(reports))
        click.echo("\n✗ Code quality check FAILED")
    elif not quiet:
        click.echo("\n✓ Code quality check PASSED")


def _format_summary(summary: dict[str, Any]) -> str:
    head = (
        f"\n{_SUMMARY_DIVIDER}\n"
        "METRICS ANALYSIS SUMMARY\n"
        f"{_SUMMARY_DIVIDER}\n"
        f"Total files analyzed: {summary['total_files']}\n"
        f"Files with violations: {summary['files_with_violations']}\n"
        f"Total violations: {summary['total_violations']}"
    )
    violations = summary["violations_by_type"]
    if not violations:
        return head
    lines = "\n".join(f"  - {metric_type}: {count}" for metric_type, count in violations.items())
    return f"{head}\n\nViolations by type:\n{lines}"


def _format_violations(reports: list[FileReport]) -> str:
    body = "\n".join(message for report in reports for message in report.violation_messages())
    return f"\n{_VIOLATION_DIVIDER}\nVIOLATIONS FOUND:\n{_VIOLATION_DIVIDER}\n{body}"


def output_results(results: dict[str, Any], output_format: str, quiet: bool) -> None:
    reports = results["reports"]
    summary = results["summary"]

    if output_format == "json":
        click.echo(
            json.dumps(
                {"summary": summary, "reports": [report.to_dict() for report in reports]}, indent=2
            )
        )
        return

    if not quiet or not summary["success"]:
        print_results(reports, summary, quiet)
