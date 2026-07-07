"""The `antipasta vcs` command: churn, change coupling, hotspots.

Opt-in by definition — history mining never runs on the default metrics
path. Hotspots join against the committed metrics snapshot when present
(``metrics/snapshot.json`` by convention), so no re-analysis happens here.
stdout carries data; diagnostics go to stderr.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import click

from antipasta.core.mining.vcs import complexity_from_snapshot, history_reports, mine_history
from antipasta.core.model.metrics import MetricType
from antipasta.core.model.violations import ProjectReport


@click.command()
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Repository root (default: current directory)",
)
@click.option("--window", type=int, default=90, help="History window in days (default: 90)")
@click.option(
    "--snapshot",
    type=click.Path(path_type=Path),
    default=Path("metrics/snapshot.json"),
    help="Metrics snapshot for the hotspot join (skipped when absent)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def vcs(repo: Path, window: int, snapshot: Path, output_format: str) -> None:
    """Mine git history: churn, change coupling, hotspots, suite health."""
    try:
        history = mine_history(repo.resolve(), window_days=window)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        click.echo(f"git history unavailable: {error}", err=True)
        sys.exit(1)

    complexity = _load_complexity(snapshot)
    reports = history_reports(history, complexity)
    click.echo(f"Mined {history.commit_count} commits over {window} days", err=True)
    if output_format == "json":
        click.echo(json.dumps({"reports": [r.to_dict() for r in reports]}, indent=2))
    else:
        _print_text(reports)


def _load_complexity(snapshot_path: Path) -> dict[str, float]:
    try:
        snapshot = json.loads(snapshot_path.read_text())
    except (OSError, json.JSONDecodeError):
        click.echo(f"no snapshot at {snapshot_path}; hotspot join skipped", err=True)
        return {}
    return complexity_from_snapshot(snapshot)


def _print_text(reports: list[ProjectReport]) -> None:
    sections = {
        MetricType.HOTSPOT: "HOTSPOTS (churn x worst cyclomatic)",
        MetricType.CODE_CHURN: "CHURN (lines touched)",
        MetricType.CHANGE_COUPLING: "CHANGE COUPLING (co-commits)",
        MetricType.TEST_CHURN_RATIO: "SUITE HEALTH",
    }
    for metric_type, heading in sections.items():
        lines = _section_lines(reports, metric_type)
        if lines:
            click.echo(f"\n{heading}")
            for line in lines:
                click.echo(f"  {line}")


def _section_lines(reports: list[ProjectReport], metric_type: MetricType) -> list[str]:
    if metric_type is MetricType.TEST_CHURN_RATIO:
        return _suite_health_lines(reports)
    return [
        f"{metric.value:>10.1f}  {report.subject}"
        for report in reports
        for metric in report.metrics
        if metric.metric_type is metric_type
    ]


def _suite_health_lines(reports: list[ProjectReport]) -> list[str]:
    for report in reports:
        if report.subject == "suite-health":
            return [f"{metric.metric_type.value}: {metric.value}" for metric in report.metrics]
    return []
