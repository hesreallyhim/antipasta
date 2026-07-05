"""The `antipasta test-health` command: coverage-matrix analytics (D2).

Reads a coverage.py artifact recorded with test contexts
(``pytest --cov --cov-context=test``); runs nothing itself.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import click

from antipasta.core.mining.coverage_matrix import load_matrix, matrix_reports
from antipasta.core.model.metrics import MetricType
from antipasta.core.model.violations import ProjectReport


@click.command(name="test-health")
@click.option(
    "--coverage-file",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
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
    coverage_file = _resolve_coverage_file(coverage_file)
    try:
        matrix = load_matrix(coverage_file)
    except RuntimeError as error:
        click.echo(str(error), err=True)
        sys.exit(1)
    if not matrix.test_count:
        click.echo(
            "no test contexts in this artifact — record with pytest --cov --cov-context=test",
            err=True,
        )
        sys.exit(1)

    reports = matrix_reports(matrix)
    click.echo(f"Matrix: {matrix.test_count} test contexts", err=True)
    if output_format == "json":
        click.echo(json.dumps({"reports": [r.to_dict() for r in reports]}, indent=2))
    else:
        _print_text(reports)


def _resolve_coverage_file(path: Path) -> Path:
    """Resolve pytest-cov layouts where .coverage is a directory."""
    if path.is_file():
        return path

    nested = path / ".coverage"
    if path.is_dir() and nested.is_file():
        return nested

    raise click.BadParameter(
        f"{path} is a directory, but {nested} was not found",
        param_hint="--coverage-file",
    )


def _print_text(reports: list[ProjectReport]) -> None:
    suite = next(r for r in reports if r.subject == "suite-redundancy")
    row = suite.metrics[0]
    details = row.details or {}
    click.echo("\nSUITE REDUNDANCY")
    click.echo(
        f"  index: {row.value}  (greedy cover {details['greedy_cover_size']}"
        f" of {details['tests']} tests)"
    )
    click.echo(f"  zero-unique-coverage tests: {details['zero_unique_tests']}")

    click.echo("\nBLAST RADIUS (tests executing each file)")
    for report in reports:
        for metric in report.metrics:
            if metric.metric_type is MetricType.BLAST_RADIUS:
                click.echo(f"  {metric.value:>6.0f}  {report.subject}")
