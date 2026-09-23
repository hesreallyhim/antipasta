"""The ``antipasta report`` command.

Composes the existing metrics pipeline (file collection + aggregation) into a
single snapshot and renders a terminal overview, JSON, or an offline HTML
report. Terminal deltas use the previous compatible run unless explicitly pinned.

Output discipline: stdout carries data (the JSON snapshot or HTML document
when no ``--output`` is given), everything diagnostic goes to stderr.  The
``--top`` ranking table and the ``--baseline`` delta summary go to stdout when
the data is written to a file, and to stderr otherwise so piped data stays
clean.
"""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import webbrowser

import click

from antipasta.cli.metrics import (
    create_and_configure_override,
    determine_files_to_analyze,
    enable_experimental_features,
    execute_analysis,
)
from antipasta.cli.report.diff_summary import format_diff_summary
from antipasta.cli.report.history import snapshot_cache_for
from antipasta.cli.report.table import format_snapshot_table
from antipasta.core.model.config import EXPERIMENTAL_FEATURES, AntipastaConfig
from antipasta.core.model.config_layers import resolve_config
from antipasta.core.model.config_override import ConfigOverride
from antipasta.core.store.snapshot import build_snapshot, format_worst_functions_table
from antipasta.core.store.snapshot_diff import SnapshotDiff, diff
from antipasta.report.baseline import build_baseline_payload


@click.command()
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=None,
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
    type=click.Choice(["table", "html", "json"], case_sensitive=False),
    default="table",
    help="Report format (terminal table, offline HTML page or JSON snapshot)",
)
@click.option("--fail-on", is_flag=True, help="Exit 2 when metric thresholds are breached")
@click.option("--by", type=click.Choice(["directory", "module"]), help="Group table output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress and supplementary output")
@click.option("--threshold", "-t", multiple=True, help="Override a threshold: metric=value")
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
@click.option(
    "--experimental",
    "experimental",
    multiple=True,
    type=click.Choice(sorted(EXPERIMENTAL_FEATURES), case_sensitive=False),
    help="Enable an experimental metric family for this run (repeatable)",
)
def report(
    path: Path | None,
    config: Path | None,
    files: tuple[Path, ...],
    directory: Path | None,
    output: Path | None,
    output_format: str,
    fail_on: bool,
    by: str | None,
    quiet: bool,
    threshold: tuple[str, ...],
    top: int,
    open_browser: bool,
    baseline: Path | None,
    save_baseline: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
    experimental: tuple[str, ...],
) -> None:
    """Analyze PATH and report metrics; use --fail-on to enforce thresholds.

    The HTML report is a single self-contained file with no network
    references; open it from any file:// URL.  With --format json the raw
    snapshot is emitted instead.  stdout carries only the report data;
    diagnostics go to stderr.

    With --baseline, the report is diffed against a previous JSON snapshot
    (see --save-baseline): a delta summary is printed and the HTML report
    renders in "vs baseline" mode.
    """
    _validate_grouping(by, output_format)
    files, directory, root = _resolve_target(path, files, directory)
    override = create_and_configure_override(
        include_pattern, exclude_pattern, threshold, no_gitignore, force_analyze
    )
    final_config = _prepare_config(config, root, override)
    enable_experimental_features(final_config, experimental)
    target_files = determine_files_to_analyze(files, directory, final_config, override, True)
    if not quiet:
        click.echo(f"Analyzing {len(target_files)} files...", err=True)
    results = execute_analysis(target_files, final_config, True, root=root)

    snapshot = build_snapshot(
        results["reports"],
        final_config,
        root=root,
        summary=results["summary"],
        project_reports=results.get("project_reports"),
        import_graph=results.get("import_graph"),
    )
    cache = snapshot_cache_for(root, files, final_config, override, directory)
    previous = _load_baseline_snapshot(baseline) if baseline is not None else cache.load()
    render_snapshot, baseline_diff = _apply_baseline(
        snapshot, baseline, previous, output_format, by
    )
    payload = _report_payload(
        render_snapshot, results, output_format, by, root, final_config, previous, fail_on
    )
    _emit(payload, output, output_format, open_browser)
    if not any(report.error for report in results["reports"]):
        cache.save(snapshot)

    if save_baseline:
        # The pristine snapshot, never the one carrying an embedded diff.
        _save_baseline_snapshot(snapshot, output)

    _emit_supplementary(snapshot, baseline, baseline_diff, output, quiet, top)
    _exit_after_report(results, fail_on)


def _emit_supplementary(
    snapshot: dict[str, Any],
    baseline: Path | None,
    baseline_diff: SnapshotDiff | None,
    output: Path | None,
    quiet: bool,
    top: int,
) -> None:
    """Print supplementary tables without mixing them into stdout report data."""
    # The delta summary and --top table share stdout only when report data
    # itself went to a file.
    if not quiet and baseline is not None and baseline_diff is not None:
        summary = format_diff_summary(baseline_diff, baseline_label=str(baseline))
        click.echo(summary, err=output is None)

    if not quiet and top > 0:
        table = format_worst_functions_table(snapshot, top)
        click.echo(table, err=output is None)


def _validate_grouping(by: str | None, output_format: str) -> None:
    """Keep aggregation output distinct from the stable snapshot formats."""
    if by and output_format != "table":
        raise click.UsageError("--by requires --format table")


def _resolve_target(
    path: Path | None, files: tuple[Path, ...], directory: Path | None
) -> tuple[tuple[Path, ...], Path | None, Path]:
    """Resolve one analysis root without silently combining positional targets."""
    if path is not None:
        if files or directory is not None:
            raise click.UsageError("PATH cannot be combined with --files or --directory")
        if path.is_dir():
            directory = path
        else:
            files = (path,)
    if directory is not None:
        return files, directory, directory.resolve()
    if files:
        parents = [str(file.resolve().parent) for file in files]
        return files, None, Path(os.path.commonpath(parents))
    return files, None, Path.cwd()


def _prepare_config(config: Path | None, root: Path, override: ConfigOverride) -> AntipastaConfig:
    """Resolve layers and apply overrides without writing diagnostics to stdout."""
    try:
        resolved = resolve_config(root=root, config_path=config)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    for warning in resolved.warnings:
        click.echo(f"Warning: {warning}", err=True)
    return resolved.config.apply_overrides(override)


def _report_payload(
    snapshot: dict[str, Any],
    results: dict[str, Any],
    output_format: str,
    by: str | None,
    root: Path,
    config: AntipastaConfig,
    previous: dict[str, Any] | None,
    fail_on: bool,
) -> str:
    """Reuse collected reports for table aggregation, without another analysis."""
    if output_format != "table":
        return _render_payload(snapshot, output_format)
    if by is None:
        return format_snapshot_table(snapshot, config, baseline=previous, fail_on=fail_on)
    return _grouped_table(results, by, root, fail_on)


def _grouped_table(results: dict[str, Any], by: str, root: Path, fail_on: bool) -> str:
    """Preserve the existing directory/module statistics display."""
    from antipasta.cli.stats.collection.file_collection import get_metrics_to_include
    from antipasta.cli.stats.output import collect_statistics_based_on_grouping
    from antipasta.cli.stats.output.display import display_table

    statistics = collect_statistics_based_on_grouping(
        results["reports"],
        get_metrics_to_include(()),
        by == "directory",
        by == "module",
        root,
        1,
        "relative",
    )
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        display_table(statistics)
    count = results["summary"]["total_violations"]
    footer = f"Violations: {count}"
    if fail_on:
        footer += f" | Exit status: {_report_exit_status(results, fail_on)}"
    return buffer.getvalue().rstrip() + "\n\n" + footer


def _report_exit_status(results: dict[str, Any], fail_on: bool) -> int:
    """Give analysis failures precedence over threshold violations."""
    if any(report.error for report in results["reports"]):
        return 1
    if fail_on and results["summary"]["total_violations"]:
        return 2
    return 0


def _exit_after_report(results: dict[str, Any], fail_on: bool) -> None:
    """Analysis errors remain failures even when threshold gating is disabled."""
    errors = [report.error for report in results["reports"] if report.error]
    if errors:
        raise click.ClickException("Analysis failed: " + "; ".join(errors))
    status = _report_exit_status(results, fail_on)
    if status:
        raise click.exceptions.Exit(status)


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
    snapshot: dict[str, Any],
    baseline: Path | None,
    old: dict[str, Any] | None,
    output_format: str,
    by: str | None = None,
) -> tuple[dict[str, Any], SnapshotDiff | None]:
    """Diff the snapshot against the baseline file, when one was given.

    Returns the snapshot to render (for HTML, a copy carrying the embedded
    ``baseline`` payload for "vs baseline" mode) and the diff result.  Schema
    drift warnings go to stderr.
    """
    if baseline is None or old is None:
        return snapshot, None
    if output_format == "table" and by is None:
        return snapshot, None
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
