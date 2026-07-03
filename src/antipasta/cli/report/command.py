"""The ``antipasta report`` command.

Composes the existing metrics pipeline (file collection + aggregation) into a
single snapshot and renders it either as JSON or as a fully offline HTML
report.

Output discipline: stdout carries data (the JSON snapshot or HTML document
when no ``--output`` is given), everything diagnostic goes to stderr.  The
``--top`` ranking table goes to stdout when the data is written to a file,
and to stderr otherwise so piped data stays clean.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import webbrowser

import click

from antipasta.cli.metrics import (
    apply_overrides_to_configuration,
    create_and_configure_override,
    determine_files_to_analyze,
    execute_analysis,
    load_configuration,
)
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.snapshot import build_snapshot, format_worst_functions_table


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
    """
    override = create_and_configure_override(
        include_pattern, exclude_pattern, (), no_gitignore, force_analyze
    )
    final_config = _prepare_config(
        config, override, include_pattern, exclude_pattern, no_gitignore, force_analyze
    )
    target_files = determine_files_to_analyze(files, directory, final_config, override, True)
    click.echo(f"Analyzing {len(target_files)} files...", err=True)
    results = execute_analysis(target_files, final_config, True)

    snapshot = build_snapshot(
        results["reports"],
        final_config,
        root=directory or Path.cwd(),
        summary=results["summary"],
    )
    payload = _render_payload(snapshot, output_format)
    _emit(payload, output, output_format, open_browser)

    if top > 0:
        table = format_worst_functions_table(snapshot, top)
        # Keep stdout data-clean: the table shares stdout only when the data
        # itself went to a file.
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
