"""Display utilities for statistics command."""

import json
import statistics
from pathlib import Path
from typing import Any

import click

from .stats_utils import (
    determine_statistics_grouping_type,
    truncate_path_for_display,
)


def display_statistics_header() -> None:
    """Display the statistics header."""
    click.echo("\n" + "=" * 60)
    click.echo("CODE METRICS STATISTICS")
    click.echo("=" * 60 + "\n")


def display_file_statistics(file_stats: dict[str, Any]) -> None:
    """Display file statistics.

    Args:
        file_stats: File statistics data
    """
    click.echo("FILE STATISTICS:")
    click.echo(f"  Total files: {file_stats.get('count', 0)}")

    if "total_loc" not in file_stats:
        return

    click.echo(f"  Total LOC: {file_stats['total_loc']:,}")
    click.echo(f"  Average LOC per file: {file_stats['avg_loc']:.1f}")
    click.echo(f"  Min LOC: {file_stats['min_loc']}")
    click.echo(f"  Max LOC: {file_stats['max_loc']}")

    std_dev = file_stats.get("std_dev", 0)
    if std_dev > 0:
        click.echo(f"  Standard deviation: {std_dev:.1f}")


def display_function_statistics(func_stats: dict[str, Any]) -> None:
    """Display function statistics.

    Args:
        func_stats: Function statistics data
    """
    click.echo("\nFUNCTION STATISTICS:")
    click.echo(f"  Total functions: {func_stats.get('count', 0)}")

    if func_stats.get("count", 0) == 0:
        return

    # Display complexity metrics if available
    if "avg_complexity" in func_stats:
        display_complexity_metrics(func_stats)
    elif "avg_loc" in func_stats:
        display_function_loc_metrics(func_stats)


def display_complexity_metrics(func_stats: dict[str, Any]) -> None:
    """Display function complexity metrics.

    Args:
        func_stats: Function statistics with complexity data
    """
    click.echo(f"  Average complexity: {func_stats['avg_complexity']:.1f}")
    click.echo(f"  Min complexity: {func_stats['min_complexity']:.1f}")
    click.echo(f"  Max complexity: {func_stats['max_complexity']:.1f}")


def display_function_loc_metrics(func_stats: dict[str, Any]) -> None:
    """Display function LOC metrics (backward compatibility).

    Args:
        func_stats: Function statistics with LOC data
    """
    click.echo(f"  Average LOC per function: {func_stats['avg_loc']:.1f}")
    click.echo(f"  Min LOC: {func_stats['min_loc']}")
    click.echo(f"  Max LOC: {func_stats['max_loc']}")


def display_additional_metrics(stats_data: dict[str, Any]) -> None:
    """Display additional metrics beyond files and functions.

    Args:
        stats_data: Overall statistics data
    """
    for key, value in stats_data.items():
        if key in ["files", "functions"] or not isinstance(value, dict):
            continue

        metric_name = key.upper().replace('_', ' ')
        click.echo(f"\n{metric_name} STATISTICS:")
        click.echo(f"  Count: {value.get('count', 0)}")
        click.echo(f"  Average: {value.get('avg', 0):.2f}")
        click.echo(f"  Min: {value.get('min', 0):.2f}")
        click.echo(f"  Max: {value.get('max', 0):.2f}")


def display_overall_statistics(stats_data: dict[str, Any]) -> None:
    """Display overall statistics in table format.

    Args:
        stats_data: Overall statistics data
    """
    display_statistics_header()
    display_file_statistics(stats_data.get("files", {}))
    display_function_statistics(stats_data.get("functions", {}))
    display_additional_metrics(stats_data)


def display_grouped_statistics(stats_data: dict[str, Any]) -> None:
    """Display directory or module grouped statistics in table format.

    Args:
        stats_data: Grouped statistics data
    """
    display_grouped_statistics_header(stats_data)
    headers = build_grouped_statistics_headers(stats_data)
    display_table_headers(headers)
    display_grouped_statistics_rows(stats_data, headers)


def display_grouped_statistics_header(stats_data: dict[str, Any]) -> None:
    """Display header section for grouped statistics."""
    click.echo("\n" + "=" * 80)
    grouping_type = determine_statistics_grouping_type(stats_data)
    click.echo(f"CODE METRICS BY {grouping_type}")
    click.echo("=" * 80 + "\n")


def build_grouped_statistics_headers(stats_data: dict[str, Any]) -> list[str]:
    """Build header row for grouped statistics table.

    Args:
        stats_data: Grouped statistics data

    Returns:
        List of header column names
    """
    all_keys = collect_all_statistic_keys(stats_data)
    headers = ["Location", "Files", "Functions"]

    add_loc_headers_if_present(headers, stats_data)
    add_metric_headers(headers, all_keys)

    return headers


def add_loc_headers_if_present(headers: list[str], stats_data: dict[str, Any]) -> None:
    """Add LOC-related headers if present in the data."""
    if any("avg_file_loc" in data for data in stats_data.values()):
        headers.append("Avg File LOC")
    if any("total_loc" in data for data in stats_data.values()):
        headers.append("Total LOC")


def add_metric_headers(headers: list[str], all_keys: set[str]) -> None:
    """Add metric headers for average values."""
    for key in sorted(all_keys):
        if is_displayable_average_metric(key):
            formatted_header = format_metric_header(key)
            headers.append(formatted_header)


def is_displayable_average_metric(key: str) -> bool:
    """Check if a metric key should be displayed as a column header."""
    return key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]


def format_metric_header(key: str) -> str:
    """Format a metric key into a readable header."""
    return key.replace("avg_", "Avg ").replace("_", " ").title()


def display_table_headers(headers: list[str]) -> None:
    """Display table headers and separator line."""
    click.echo(format_table_row(headers))
    click.echo("-" * sum(len(h) + 3 for h in headers))


def display_grouped_statistics_rows(stats_data: dict[str, Any], headers: list[str]) -> None:
    """Display data rows for grouped statistics.

    Args:
        stats_data: Statistics data to display
        headers: Table headers for column ordering
    """
    for location, data in sorted(stats_data.items()):
        row = build_grouped_statistics_row(location, data, headers)
        click.echo(format_table_row(row))


def build_grouped_statistics_row(location: str, data: dict[str, Any], headers: list[str]) -> list[str]:
    """Build a single row for grouped statistics display.

    Args:
        location: Location identifier
        data: Statistics data for this location
        headers: Table headers for column ordering

    Returns:
        List of formatted row values
    """
    row = [
        truncate_path_for_display(location, 30),
        str(data.get("file_count", 0)),
        str(data.get("function_count", 0)),
    ]

    add_loc_data_to_row(row, data, headers)
    add_metric_data_to_row(row, data, headers)

    return row


def add_loc_data_to_row(row: list[str], data: dict[str, Any], headers: list[str]) -> None:
    """Add LOC data to row if present in headers."""
    if "Avg File LOC" in headers:
        row.append(f"{data.get('avg_file_loc', 0):.1f}")
    if "Total LOC" in headers:
        row.append(f"{data.get('total_loc', 0):,}")


def add_metric_data_to_row(row: list[str], data: dict[str, Any], headers: list[str]) -> None:
    """Add metric data to row for displayable average metrics."""
    all_keys = set(data.keys())
    for key in sorted(all_keys):
        if is_displayable_average_metric(key):
            row.append(f"{data.get(key, 0):.2f}")


def display_table(stats_data: dict[str, Any]) -> None:
    """Display statistics as a formatted table."""
    if isinstance(stats_data, dict) and "files" in stats_data:
        display_overall_statistics(stats_data)
    else:
        display_grouped_statistics(stats_data)


def format_table_row(values: list[Any]) -> str:
    """Format a row for table display."""
    # Dynamic widths based on number of columns
    if len(values) <= 3:
        widths = [30, 8, 10] + [15] * (len(values) - 3)
    elif len(values) <= 5:
        widths = [30, 8, 10, 12, 10] + [15] * (len(values) - 5)
    else:
        widths = [30, 8, 10, 12, 10] + [15] * (len(values) - 5)
    formatted = []
    for i, value in enumerate(values):
        if i < len(widths):
            formatted.append(str(value).ljust(widths[i])[: widths[i]])
        else:
            formatted.append(str(value))
    return " ".join(formatted)


def display_json(stats_data: dict[str, Any]) -> None:
    """Display statistics as JSON."""
    click.echo(json.dumps(stats_data, indent=2))


def display_csv(stats_data: dict[str, Any]) -> None:
    """Display statistics as CSV to stdout."""
    import csv
    import sys

    writer = csv.writer(sys.stdout)

    if is_overall_statistics(stats_data):
        display_overall_statistics_csv(writer, stats_data)
    else:
        display_grouped_statistics_csv(writer, stats_data)


def display_overall_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display overall statistics as CSV."""
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Files", stats_data["files"]["count"]])

    display_file_loc_metrics_csv(writer, stats_data)
    writer.writerow(["Total Functions", stats_data["functions"]["count"]])
    display_function_complexity_metrics_csv(writer, stats_data)


def display_file_loc_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display file LOC metrics in CSV format."""
    if "total_loc" in stats_data["files"]:
        writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
        writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])


def display_function_complexity_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display function complexity metrics in CSV format."""
    if "avg_complexity" in stats_data["functions"]:
        writer.writerow([
            "Average Function Complexity",
            stats_data["functions"]["avg_complexity"],
        ])
    elif "avg_loc" in stats_data["functions"]:
        writer.writerow([
            "Average LOC per Function",
            stats_data["functions"]["avg_loc"],
        ])


def display_grouped_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display directory/module statistics as CSV."""
    if not stats_data:
        return

    all_keys = collect_all_statistic_keys(stats_data)
    headers = ["location"] + sorted(all_keys)
    writer.writerow(headers)

    write_grouped_data_rows_csv(writer, stats_data, all_keys)


def collect_all_statistic_keys(stats_data: dict[str, Any]) -> set[str]:
    """Collect all unique keys from grouped statistics data."""
    all_keys = set()
    for data in stats_data.values():
        all_keys.update(data.keys())
    return all_keys


def write_grouped_data_rows_csv(writer: Any, stats_data: dict[str, Any], all_keys: set[str]) -> None:
    """Write data rows for grouped statistics to CSV writer."""
    for location, data in sorted(stats_data.items()):
        row = [location]
        for key in sorted(all_keys):
            row.append(data.get(key, 0))
        writer.writerow(row)


def is_overall_statistics(stats_data: dict[str, Any]) -> bool:
    """Check if statistics data represents overall statistics."""
    return isinstance(stats_data, dict) and "files" in stats_data