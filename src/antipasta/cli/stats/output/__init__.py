"""Output management utilities for stats command."""

import contextlib
import io
import json
from pathlib import Path
from typing import Any

import click

from ..aggregation import (
    collect_directory_stats,
    collect_module_stats,
    collect_overall_stats,
)
from .display import (
    display_csv,
    display_json,
    display_table,
)


def collect_statistics_based_on_grouping(
    reports: list[Any],
    metrics_to_include: list[str],
    by_directory: bool,
    by_module: bool,
    directory: Path,
    depth: int,
    path_style: str,
) -> dict[str, Any]:
    """Collect statistics based on the requested grouping method.

    Args:
        reports: Analysis reports
        metrics_to_include: Metrics to include in statistics
        by_directory: Whether to group by directory
        by_module: Whether to group by module
        directory: Base directory
        depth: Directory depth for display
        path_style: Path display style

    Returns:
        Statistics data dictionary
    """
    if by_directory:
        return collect_directory_stats(reports, metrics_to_include, directory, depth, path_style)
    if by_module:
        return collect_module_stats(reports, metrics_to_include)
    return collect_overall_stats(reports, metrics_to_include)


def handle_output_and_display(stats_data: dict[str, Any], format: str, output: Path | None) -> None:
    """Handle output and display of statistics based on format and output options.

    Args:
        stats_data: Statistics data to output
        format: Output format
        output: Output file path (optional)
    """
    if output:
        save_stats(stats_data, format, output)
        click.echo(f"✓ Saved to {output}")
    else:
        display_stats_to_stdout(stats_data, format)


def display_stats_to_stdout(stats_data: dict[str, Any], format: str) -> None:
    """Display statistics to stdout based on format.

    Args:
        stats_data: Statistics data to display
        format: Output format (json, csv, or table)
    """
    display_functions = {
        "json": display_json,
        "csv": display_csv,
        "table": display_table,
    }

    display_func = display_functions.get(format, display_table)
    display_func(stats_data)


def save_stats(stats_data: dict[str, Any], format: str, output_path: Path) -> None:
    """Save statistics to a file in the specified format.

    Args:
        stats_data: Statistics data to save
        format: Output format
        output_path: Path to save to
    """
    if format == "json":
        with open(output_path, "w") as f:
            json.dump(stats_data, f, indent=2)
    elif format == "csv":
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            display_csv(stats_data)
        with open(output_path, "w") as f:  # noqa: FURB103
            f.write(buffer.getvalue())
    else:  # table format
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            display_table(stats_data)
        with open(output_path, "w") as f:  # noqa: FURB103
            f.write(buffer.getvalue())


def generate_all_reports(reports: list[Any], metrics: list[str], output_dir: Path) -> None:
    """Generate all report formats from a single analysis.

    Args:
        reports: Analysis reports
        metrics: Metrics to include
        output_dir: Directory to save reports to
    """
    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\nGenerating all reports in {output_dir}...")

    # Generate all three groupings
    overall_stats = collect_overall_stats(reports, metrics)
    dir_stats = collect_directory_stats(
        reports, metrics, Path("."), 1, "relative"
    )  # Default to relative style
    module_stats = collect_module_stats(reports, metrics)

    # Save each grouping in each format
    formats_saved = 0

    # Overall statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_overall.{ext}"
        save_stats(overall_stats, fmt, output_file)
        click.echo(f"  ✓ Overall statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    # Directory statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_by_directory.{ext}"
        save_stats(dir_stats, fmt, output_file)
        click.echo(f"  ✓ Directory statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    # Module statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_by_module.{ext}"
        save_stats(module_stats, fmt, output_file)
        click.echo(f"  ✓ Module statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    click.echo(f"\n✅ Generated {formats_saved} report files from a single analysis!")
    click.echo(f"   Total files analyzed: {len(reports)}")
    click.echo(f"   Total functions found: {overall_stats['functions']['count']}")
    if "total_loc" in overall_stats["files"]:
        click.echo(f"   Total LOC: {overall_stats['files']['total_loc']:,.0f}")


def generate_output(
    reports: list[Any],
    metric: tuple[str, ...],
    format: str,
    output: Path | None,
    by_directory: bool,
    by_module: bool,
    directory: Path,
    depth: int,
    path_style: str,
) -> None:
    """Generate the requested output format.

    Args:
        reports: Analysis reports
        metric: Metrics to include
        format: Output format
        output: Output path
        by_directory: Group by directory
        by_module: Group by module
        directory: Base directory
        depth: Directory depth
        path_style: Path display style
    """
    from ..collection.file_collection import get_metrics_to_include

    metrics_to_include = get_metrics_to_include(metric)

    if format == "all":
        generate_all_reports(reports, metrics_to_include, output or Path("."))
    else:
        stats_data = collect_statistics_based_on_grouping(
            reports, metrics_to_include, by_directory, by_module, directory, depth, path_style
        )
        handle_output_and_display(stats_data, format, output)
