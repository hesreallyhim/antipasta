"""The `antipasta test-health` command: coverage-matrix analytics (D2).

Reads a coverage.py artifact recorded with test contexts
(``pytest --cov --cov-context=test``); runs nothing itself.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import click

from antipasta.core.metrics import MetricType
from antipasta.core.test_health import load_matrix, matrix_reports
from antipasta.core.violations import ProjectReport


@click.command(name="test-health")
@click.option(
    "--coverage-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path(".coverage"),
    help="coverage.py data file recorded with --cov-context=test",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def test_health(coverage_file: Path, output_format: str) -> None:
    """Analyze suite redundancy and blast radius from a coverage artifact."""
    try:
        matrix = load_matrix(coverage_file)
    except RuntimeError as error:
        click.echo(str(error), err=True)
        sys.exit(1)
    if not matrix.test_count:
        click.echo(
            "no test contexts in this artifact — record with "
            "pytest --cov --cov-context=test",
            err=True,
        )
        sys.exit(1)

    reports = matrix_reports(matrix)
    click.echo(f"Matrix: {matrix.test_count} test contexts", err=True)
    if output_format == "json":
        click.echo(json.dumps({"reports": [r.to_dict() for r in reports]}, indent=2))
    else:
        _print_text(reports)


def _print_text(reports: list[ProjectReport]) -> None:
    suite = next(r for r in reports if r.subject == "suite-redundancy")
    row = suite.metrics[0]
    details = row.details or {}
    click.echo("\nSUITE REDUNDANCY")
    click.echo(f"  index: {row.value}  (greedy cover {details['greedy_cover_size']}"
               f" of {details['tests']} tests)")
    click.echo(f"  zero-unique-coverage tests: {details['zero_unique_tests']}")

    click.echo("\nBLAST RADIUS (tests executing each file)")
    for report in reports:
        for metric in report.metrics:
            if metric.metric_type is MetricType.BLAST_RADIUS:
                click.echo(f"  {metric.value:>6.0f}  {report.subject}")
