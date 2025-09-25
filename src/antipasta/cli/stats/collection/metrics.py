"""Metric collection and statistics utilities for stats command."""

import statistics
from typing import Any

from antipasta.core.metrics import MetricType

from ..utils import (
    calculate_file_loc_statistics,
    calculate_function_complexity_statistics,
    collect_function_complexities_from_reports,
    collect_function_names_from_reports,
    collect_metrics_from_reports,
    should_collect_loc_metrics,
)


def collect_overall_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect overall statistics across all files.

    Args:
        reports: List of metric reports
        metrics_to_include: Metrics to include in statistics

    Returns:
        Dictionary of overall statistics
    """
    stats = {
        "files": {"count": len(reports)},
        "functions": {"count": 0},
    }

    should_collect_loc = should_collect_loc_metrics(metrics_to_include)
    function_names = collect_function_names_from_reports(reports)
    function_complexities = collect_function_complexities_from_reports(reports)

    # Add file-level LOC statistics if requested
    if should_collect_loc:
        loc_stats = calculate_file_loc_statistics(reports)
        if loc_stats["total_loc"] > 0:  # Only add if data was found
            stats["files"].update(loc_stats)

    # Add function statistics
    stats["functions"]["count"] = len(function_names)
    if function_complexities:
        complexity_stats = calculate_function_complexity_statistics(function_complexities)
        stats["functions"].update(complexity_stats)

    # Add additional metrics if requested
    for metric_name in metrics_to_include:
        stats[metric_name] = collect_metric_stats(reports, metric_name)

    return stats


def collect_metric_stats(reports: list[Any], metric_name: str) -> dict[str, Any]:
    """Collect statistics for a specific metric.

    Args:
        reports: List of metric reports
        metric_name: Name of the metric to collect

    Returns:
        Dictionary of metric statistics
    """
    try:
        MetricType(metric_name)  # Validate metric name
    except ValueError:
        return {"error": f"Unknown metric: {metric_name}"}

    values = collect_metrics_from_reports(reports, metric_name)
    return calculate_metric_statistics(values)


def calculate_metric_statistics(values: list[float]) -> dict[str, Any]:
    """Calculate statistics for a list of metric values.

    Args:
        values: List of metric values

    Returns:
        Dictionary containing statistics
    """
    if not values:
        return {"count": 0, "avg": 0, "min": 0, "max": 0, "std_dev": 0}

    return {
        "count": len(values),
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
    }


def add_metric_statistics_to_result(
    result_entry: dict[str, Any], metrics: dict[str, list[Any]], unique_files: list[Any]
) -> None:
    """Add metric statistics to result entry.

    Args:
        result_entry: Result entry to modify
        metrics: Metrics data
        unique_files: List of unique files
    """
    for metric_name, values in metrics.items():
        if values:
            # Remove duplicates from aggregated metrics
            unique_values = values[: len(unique_files)]
            result_entry[f"avg_{metric_name}"] = statistics.mean(unique_values)
