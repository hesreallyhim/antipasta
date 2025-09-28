"""Module statistics collection utilities for stats command."""

from collections import defaultdict
import statistics
from typing import Any

from ..utils import should_collect_loc_metrics
from .directory import extract_file_locs_from_reports


def determine_module_name(report: Any) -> str:
    """Determine Python module name from file path.

    Args:
        report: Metric report with file path

    Returns:
        Module name or '<root>' if not in a package
    """
    module_parts: list[str] = []
    current_path = report.file_path.parent

    # Walk up looking for __init__.py files
    while current_path != current_path.parent:
        if (current_path / "__init__.py").exists():
            module_parts.insert(0, current_path.name)
            current_path = current_path.parent
        else:
            break

    return ".".join(module_parts) if module_parts else "<root>"


def group_reports_by_module(
    reports: list[Any], metrics_to_include: list[str]
) -> dict[str, dict[str, Any]]:
    """Group reports by Python module.

    Args:
        reports: List of metric reports
        metrics_to_include: Metrics to collect

    Returns:
        Dictionary mapping module names to their data
    """
    module_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "files": [],
            "function_names": set(),
            "metrics": defaultdict(list),
        }
    )

    for report in reports:
        module_name = determine_module_name(report)
        module_stats[module_name]["files"].append(report)

        # Collect metrics
        for metric in report.metrics:
            if metric.function_name:
                module_stats[module_name]["function_names"].add(metric.function_name)
            if metric.metric_type.value in metrics_to_include:
                module_stats[module_name]["metrics"][metric.metric_type.value].append(metric.value)

    return module_stats


def calculate_module_statistics(
    module_stats: dict[str, dict[str, Any]], metrics_to_include: list[str]
) -> dict[str, Any]:
    """Calculate statistics for each module.

    Args:
        module_stats: Grouped module data
        metrics_to_include: Metrics to include

    Returns:
        Module statistics dictionary
    """
    results = {}
    should_collect_loc = should_collect_loc_metrics(metrics_to_include)

    for module_name, data in module_stats.items():
        result_entry = build_base_module_result(data)

        if should_collect_loc:
            add_module_loc_statistics(result_entry, data["files"])

        add_module_metric_statistics(result_entry, data["metrics"])

        results[module_name] = result_entry

    return results


def build_base_module_result(data: dict[str, Any]) -> dict[str, Any]:
    """Build base result entry for a module.

    Args:
        data: Module data

    Returns:
        Base result dictionary with file and function counts
    """
    return {
        "file_count": len(data["files"]),
        "function_count": len(data["function_names"]),
    }


def add_module_loc_statistics(result_entry: dict[str, Any], files: list[Any]) -> None:
    """Add LOC statistics to module result entry.

    Args:
        result_entry: Result entry to modify
        files: List of files in the module
    """
    file_locs = extract_file_locs_from_reports(files)

    result_entry["avg_file_loc"] = int(statistics.mean(file_locs)) if file_locs else 0
    result_entry["total_loc"] = sum(file_locs)


def add_module_metric_statistics(
    result_entry: dict[str, Any], metrics: dict[str, list[Any]]
) -> None:
    """Add metric statistics to module result entry.

    Args:
        result_entry: Result entry to modify
        metrics: Metrics data for the module
    """
    for metric_name, values in metrics.items():
        if values:
            result_entry[f"avg_{metric_name}"] = statistics.mean(values)


def collect_module_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect statistics grouped by Python module.

    Args:
        reports: List of metric reports
        metrics_to_include: Metrics to include

    Returns:
        Dictionary of module statistics
    """
    module_stats = group_reports_by_module(reports, metrics_to_include)
    return calculate_module_statistics(module_stats, metrics_to_include)
