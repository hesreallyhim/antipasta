"""The `antipasta vcs` command: churn, change coupling, hotspots.

Opt-in by definition — history mining never runs on the default metrics
path. Hotspots can join against an explicit report JSON snapshot, so no
re-analysis happens here. Mining is limited to the files the configuration
would analyze (source extensions minus ignore patterns and gitignore), so
docs and generated artifacts do not dominate churn. stdout carries data;
diagnostics go to stderr.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import subprocess
import sys

import click

from antipasta.cli.metrics import load_configuration
from antipasta.core.mining.vcs import (
    DEFAULT_MAX_COMMIT_FILES,
    complexity_from_snapshot,
    history_reports,
    mine_history,
)
from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.detector import LanguageDetector
from antipasta.core.model.metrics import MetricType
from antipasta.core.model.violations import ProjectReport

_SOURCE_SUFFIXES = frozenset({".py", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx"})


@click.command()
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Repository root (default: current directory)",
)
@click.option("--window", type=int, default=90, help="History window in days (default: 90)")
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=".antipasta.yaml",
    help="Configuration whose ignore patterns limit the mined files",
)
@click.option(
    "--max-commit-files",
    type=int,
    default=DEFAULT_MAX_COMMIT_FILES,
    show_default=True,
    help="Commits touching more source files than this are left out of change coupling",
)
@click.option(
    "--snapshot",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional report JSON snapshot for the hotspot join",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def vcs(
    repo: Path,
    window: int,
    config: Path,
    max_commit_files: int,
    snapshot: Path | None,
    output_format: str,
) -> None:
    """Mine git history: churn, change coupling, hotspots, suite health."""
    repo_root = repo.resolve()
    include = _analyzed_file_filter(load_configuration(config, quiet=True), repo_root)
    try:
        history = mine_history(
            repo_root, window_days=window, include=include, max_commit_files=max_commit_files
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        click.echo(f"git history unavailable: {error}", err=True)
        sys.exit(1)

    complexity = _load_complexity(snapshot)
    reports = history_reports(history, complexity)
    summary = f"Mined {history.commit_count} commits over {window} days"
    if history.bulk_commit_count:
        summary += (
            f" ({history.bulk_commit_count} touching more than {max_commit_files}"
            " files left out of change coupling)"
        )
    click.echo(summary, err=True)
    if output_format == "json":
        click.echo(json.dumps({"reports": [r.to_dict() for r in reports]}, indent=2))
    else:
        _print_text(reports)


def _analyzed_file_filter(config: AntipastaConfig, repo_root: Path) -> Callable[[str], bool]:
    """Accept the repo-relative paths the metrics command would analyze."""
    detector = LanguageDetector(ignore_patterns=config.ignore_patterns, base_dir=repo_root)
    if config.use_gitignore:
        detector.add_gitignore(repo_root / ".gitignore")

    def include(path: str) -> bool:
        candidate = repo_root / path
        return candidate.suffix in _SOURCE_SUFFIXES and not detector.should_ignore(candidate)

    return include


def _load_complexity(snapshot_path: Path | None) -> dict[str, float]:
    if snapshot_path is None:
        return {}
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
