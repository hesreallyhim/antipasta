"""Display utilities for statistics command."""

import json
from typing import Any

import click

from ..utils import (
    determine_statistics_grouping_type,
    truncate_path_for_display,
)

# Display constants
STATISTICS_SEPARATOR = "=" * 60
GROUPED_STATISTICS_SEPARATOR = "=" * 80
DEFAULT_LOCATION_WIDTH = 30
STANDARD_COLUMN_WIDTHS = [30, 8, 10, 12, 10]
EXTRA_COLUMN_WIDTH = 15

# CSV constants
CSV_METRIC_HEADER = "Metric"
CSV_VALUE_HEADER = "Value"
CSV_LOCATION_HEADER = "location"


def display_statistics_header(title: str = "CODE METRICS STATISTICS") -> None:
    """Display the statistics header with customizable title.

    Args:
        title: Header title to display
    """
    separator = GROUPED_STATISTICS_SEPARATOR if len(title) > 30 else STATISTICS_SEPARATOR
    click.echo("\n" + separator)
    click.echo(title)
    click.echo(separator + "\n")


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
    """Display function statistics with complexity or LOC metrics.

    Args:
        func_stats: Function statistics data
    """
    click.echo("\nFUNCTION STATISTICS:")
    click.echo(f"  Total functions: {func_stats.get('count', 0)}")

    if func_stats.get("count", 0) == 0:
        return

    # Display complexity metrics if available, otherwise LOC metrics
    if "avg_complexity" in func_stats:
        click.echo(f"  Average complexity: {func_stats['avg_complexity']:.1f}")
        click.echo(f"  Min complexity: {func_stats['min_complexity']:.1f}")
        click.echo(f"  Max complexity: {func_stats['max_complexity']:.1f}")
    elif "avg_loc" in func_stats:
        click.echo(f"  Average LOC per function: {func_stats['avg_loc']:.1f}")
        click.echo(f"  Min LOC: {func_stats['min_loc']}")
        click.echo(f"  Max LOC: {func_stats['max_loc']}")


def display_additional_metrics(stats_data: dict[str, Any]) -> None:
    """Display additional metrics beyond files and functions.

    Args:
        stats_data: Overall statistics data
    """
    for key, value in stats_data.items():
        if key not in ["files", "functions"] and isinstance(value, dict):
            metric_name = key.upper().replace("_", " ")
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
    display_statistics_header("CODE METRICS STATISTICS")
    display_file_statistics(stats_data.get("files", {}))
    display_function_statistics(stats_data.get("functions", {}))
    display_additional_metrics(stats_data)


def display_grouped_statistics(stats_data: dict[str, Any]) -> None:
    """Display directory or module grouped statistics in table format.

    Args:
        stats_data: Grouped statistics data
    """
    grouping_type = determine_statistics_grouping_type(stats_data)
    display_statistics_header(f"CODE METRICS BY {grouping_type}")

    headers = build_grouped_statistics_headers(stats_data)
    click.echo(format_table_row(headers))
    click.echo("-" * sum(len(h) + 3 for h in headers))

    for location, data in sorted(stats_data.items()):
        row = build_grouped_statistics_row(location, data, headers)
        click.echo(format_table_row(row))


def build_grouped_statistics_headers(stats_data: dict[str, Any]) -> list[str]:
    """Build header row for grouped statistics table.

    Args:
        stats_data: Grouped statistics data

    Returns:
        List of header column names
    """
    all_keys = set()
    for data in stats_data.values():
        all_keys.update(data.keys())

    headers = ["Location", "Files", "Functions"]

    # Add LOC headers if present
    if any("avg_file_loc" in data for data in stats_data.values()):
        headers.append("Avg File LOC")
    if any("total_loc" in data for data in stats_data.values()):
        headers.append("Total LOC")

    # Add metric headers for average values
    for key in sorted(all_keys):
        if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
            formatted_header = key.replace("avg_", "Avg ").replace("_", " ").title()
            headers.append(formatted_header)

    return headers


def build_grouped_statistics_row(
    location: str, data: dict[str, Any], headers: list[str]
) -> list[str]:
    """Build a single row for grouped statistics display.

    Args:
        location: Location identifier
        data: Statistics data for this location
        headers: Table headers for column ordering

    Returns:
        List of formatted row values
    """
    row = [
        truncate_path_for_display(location, DEFAULT_LOCATION_WIDTH),
        str(data.get("file_count", 0)),
        str(data.get("function_count", 0)),
    ]

    # Add LOC data if present in headers
    if "Avg File LOC" in headers:
        row.append(f"{data.get('avg_file_loc', 0):.1f}")
    if "Total LOC" in headers:
        row.append(f"{data.get('total_loc', 0):,}")

    # Add metric data for displayable average metrics
    for key in sorted(data.keys()):
        if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
            row.append(f"{data.get(key, 0):.2f}")

    return row


def display_table(stats_data: dict[str, Any]) -> None:
    """Display statistics as a formatted table."""
    if isinstance(stats_data, dict) and "files" in stats_data:
        display_overall_statistics(stats_data)
    else:
        display_grouped_statistics(stats_data)


def format_table_row(values: list[Any]) -> str:
    """Format a row for table display."""
    num_columns = len(values)
    widths = STANDARD_COLUMN_WIDTHS[: min(5, num_columns)] + [EXTRA_COLUMN_WIDTH] * max(
        0, num_columns - 5
    )

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

    if isinstance(stats_data, dict) and "files" in stats_data:
        # Overall statistics format
        writer.writerow([CSV_METRIC_HEADER, CSV_VALUE_HEADER])
        writer.writerow(["Total Files", stats_data["files"]["count"]])

        # Add file LOC metrics if available
        if "total_loc" in stats_data["files"]:
            writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
            writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])

        writer.writerow(["Total Functions", stats_data["functions"]["count"]])

        # Add function complexity or LOC metrics
        if "avg_complexity" in stats_data["functions"]:
            writer.writerow(
                [
                    "Average Function Complexity",
                    stats_data["functions"]["avg_complexity"],
                ]
            )
        elif "avg_loc" in stats_data["functions"]:
            writer.writerow(["Average LOC per Function", stats_data["functions"]["avg_loc"]])
    else:
        # Grouped statistics format
        if not stats_data:
            return

        all_keys = set()
        for data in stats_data.values():
            all_keys.update(data.keys())

        headers = [CSV_LOCATION_HEADER] + sorted(all_keys)
        writer.writerow(headers)

        for location, data in sorted(stats_data.items()):
            row = [location] + [data.get(key, 0) for key in sorted(all_keys)]
            writer.writerow(row)
