"""The ``antipasta report`` command.

Composes the existing metrics pipeline (file collection + aggregation) into a
single snapshot and renders it either as JSON or as a fully offline HTML
report.

Output discipline: stdout carries data (the JSON snapshot or HTML document
when no ``--output`` is given), everything diagnostic goes to stderr.  The
``--top`` ranking table and the ``--baseline`` delta summary go to stdout when
the data is written to a file, and to stderr otherwise so piped data stays
clean.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any
import webbrowser

import click

from antipasta.cli.metrics import (
    apply_overrides_to_configuration,
    create_and_configure_override,
    determine_files_to_analyze,
    execute_analysis,
    load_configuration,
)
from antipasta.cli.report.diff_summary import format_diff_summary
from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_override import ConfigOverride
from antipasta.core.store.snapshot import build_snapshot, format_worst_functions_table
from antipasta.core.store.snapshot_diff import SnapshotDiff, diff
from antipasta.report.baseline import build_baseline_payload


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
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the report to this file (default: stdout)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["html", "json"], case_sensitive=False),
    default="html",
    help="Report format (offline HTML page or JSON snapshot)",
)
@click.option(
    "--top",
    type=int,
    default=0,
    help="Also print the N worst functions (ranked by max of cyclomatic/cognitive complexity)",
)
@click.option(
    "--open/--no-open",
    "open_browser",
    default=False,
    help="Open the HTML report in a browser after writing it",
)
@click.option(
    "--baseline",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help=(
        "Baseline JSON snapshot to diff against: prints a delta summary and, "
        "for HTML, renders the report in 'vs baseline' mode"
    ),
)
@click.option(
    "--save-baseline",
    is_flag=True,
    help=(
        "Also write the JSON snapshot next to the output (<name>.baseline.json) "
        "for a later --baseline run"
    ),
)
@click.option(
    "--include-pattern",
    "-i",
    multiple=True,
    help=(
        "Force include files matching pattern (overrides ignore patterns, "
        "can be specified multiple times)"
    ),
)
@click.option(
    "--exclude-pattern",
    "-e",
    multiple=True,
    help="Add additional exclusion patterns (can be specified multiple times)",
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
def report(
    config: Path,
    files: tuple[Path, ...],
    directory: Path | None,
    output: Path | None,
    output_format: str,
    top: int,
    open_browser: bool,
    baseline: Path | None,
    save_baseline: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> None:
    """Generate a visual complexity report (offline HTML or JSON snapshot).

    The HTML report is a single self-contained file with no network
    references; open it from any file:// URL.  With --format json the raw
    snapshot is emitted instead.  stdout carries only the report data;
    diagnostics go to stderr.

    With --baseline, the report is diffed against a previous JSON snapshot
    (see --save-baseline): a delta summary is printed and the HTML report
    renders in "vs baseline" mode.
    """
    override = create_and_configure_override(
        include_pattern, exclude_pattern, (), no_gitignore, force_analyze
    )
    final_config = _prepare_config(
        config, override, include_pattern, exclude_pattern, no_gitignore, force_analyze
    )
    target_files = determine_files_to_analyze(files, directory, final_config, override, True)
    click.echo(f"Analyzing {len(target_files)} files...", err=True)
    results = execute_analysis(target_files, final_config, True, root=directory)

    snapshot = build_snapshot(
        results["reports"],
        final_config,
        root=directory or Path.cwd(),
        summary=results["summary"],
        project_reports=results.get("project_reports"),
    )
    render_snapshot, baseline_diff = _apply_baseline(snapshot, baseline, output_format)
    payload = _render_payload(render_snapshot, output_format)
    _emit(payload, output, output_format, open_browser)

    if save_baseline:
        # The pristine snapshot, never the one carrying an embedded diff.
        _save_baseline_snapshot(snapshot, output)

    # Keep stdout data-clean: the delta summary and --top table share stdout
    # only when the data itself went to a file.
    if baseline is not None and baseline_diff is not None:
        summary = format_diff_summary(baseline_diff, baseline_label=str(baseline))
        click.echo(summary, err=output is None)

    if top > 0:
        table = format_worst_functions_table(snapshot, top)
        click.echo(table, err=output is None)


def _prepare_config(
    config: Path,
    override: ConfigOverride,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> AntipastaConfig:
    """Load configuration and apply pattern overrides (diagnostics to stderr)."""
    configuration = load_configuration(config, quiet=True)
    if config.exists():
        click.echo(f"Using configuration: {config}", err=True)
    else:
        click.echo(f"Configuration file '{config}' not found; using defaults.", err=True)
    return apply_overrides_to_configuration(
        configuration,
        override,
        True,  # quiet: status messages would go to stdout, keep it data-clean
        force_analyze,
        include_pattern,
        exclude_pattern,
        (),
        no_gitignore,
    )


def _load_baseline_snapshot(path: Path) -> dict[str, Any]:
    """Read and parse a baseline snapshot, failing with a clean CLI error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot read baseline snapshot {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"Baseline snapshot {path} is not a JSON object")
    return data


def _apply_baseline(
    snapshot: dict[str, Any], baseline: Path | None, output_format: str
) -> tuple[dict[str, Any], SnapshotDiff | None]:
    """Diff the snapshot against the baseline file, when one was given.

    Returns the snapshot to render (for HTML, a copy carrying the embedded
    ``baseline`` payload for "vs baseline" mode) and the diff result.  Schema
    drift warnings go to stderr.
    """
    if baseline is None:
        return snapshot, None
    old = _load_baseline_snapshot(baseline)
    baseline_diff = diff(old, snapshot)
    for warning in baseline_diff.warnings:
        click.echo(f"Warning: {warning}", err=True)
    if output_format.lower() == "html":
        payload = build_baseline_payload(baseline_diff, old, label=baseline.name)
        snapshot = {**snapshot, "baseline": payload}
    return snapshot, baseline_diff


def _save_baseline_snapshot(snapshot: dict[str, Any], output: Path | None) -> None:
    """Write the JSON snapshot next to the output for a later --baseline run."""
    path = (
        output.with_suffix(".baseline.json") if output is not None else Path("report.baseline.json")
    )
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    click.echo(f"Baseline snapshot written to {path}", err=True)


def _render_payload(snapshot: dict[str, object], output_format: str) -> str:
    """Render the snapshot in the requested format."""
    if output_format.lower() == "json":
        return json.dumps(snapshot, indent=2)

    from antipasta.report import render_report

    return render_report(snapshot)


def _emit(payload: str, output: Path | None, output_format: str, open_browser: bool) -> None:
    """Write the payload to the output file or stdout; optionally open it."""
    is_html = output_format.lower() == "html"
    if output is not None:
        output.write_text(payload, encoding="utf-8")
        click.echo(f"Report written to {output}", err=True)
        if open_browser and is_html:
            webbrowser.open(output.resolve().as_uri())
        return

    click.echo(payload)
    if open_browser and is_html:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".html", prefix="antipasta-report-", delete=False
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        click.echo(f"Report also written to {temp_path} for browsing", err=True)
        webbrowser.open(temp_path.resolve().as_uri())
