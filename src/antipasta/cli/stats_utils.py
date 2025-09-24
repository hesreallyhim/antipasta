"""Utility functions for statistics collection and display."""

from pathlib import Path
import statistics
from typing import Any

from antipasta.core.metrics import MetricType


def should_collect_loc_metrics(metrics_to_include: list[str]) -> bool:
    """Check if LOC metrics should be collected based on requested metrics.

    Args:
        metrics_to_include: List of metric names to include

    Returns:
        True if any LOC-related metrics are requested
    """
    loc_metrics = ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
    return any(metric in metrics_to_include for metric in loc_metrics)


def extract_file_loc_from_report(report: Any) -> int:
    """Extract file-level LOC from a metric report.

    Args:
        report: Metric report containing file metrics

    Returns:
        Lines of code for the file, or 0 if not found
    """
    return next(
        (
            m.value
            for m in report.metrics
            if m.metric_type == MetricType.LINES_OF_CODE and m.function_name is None
        ),
        0,
    )


def collect_function_names_from_reports(reports: list[Any]) -> set[tuple[Path, str]]:
    """Collect unique function names from metric reports.

    Args:
        reports: List of metric reports

    Returns:
        Set of tuples containing (file_path, function_name)
    """
    function_names = set()
    for report in reports:
        for metric in report.metrics:
            if metric.function_name:
                function_names.add((report.file_path, metric.function_name))
    return function_names


def collect_function_complexities_from_reports(reports: list[Any]) -> list[float]:
    """Collect cyclomatic complexity values for functions from reports.

    Args:
        reports: List of metric reports

    Returns:
        List of complexity values
    """
    complexities = []
    for report in reports:
        for metric in report.metrics:
            if metric.function_name and metric.metric_type == MetricType.CYCLOMATIC_COMPLEXITY:
                complexities.append(metric.value)
    return complexities


def calculate_file_loc_statistics(reports: list[Any]) -> dict[str, Any]:
    """Calculate file-level LOC statistics from reports.

    Args:
        reports: List of metric reports

    Returns:
        Dictionary containing LOC statistics
    """
    file_locs = []
    for report in reports:
        file_loc = extract_file_loc_from_report(report)
        if file_loc > 0:
            file_locs.append(file_loc)

    if not file_locs:
        return {
            "total_loc": 0,
            "avg_loc": 0.0,
            "min_loc": 0,
            "max_loc": 0,
            "std_dev": 0.0,
        }

    return {
        "total_loc": sum(file_locs),
        "avg_loc": statistics.mean(file_locs),
        "min_loc": min(file_locs),
        "max_loc": max(file_locs),
        "std_dev": statistics.stdev(file_locs) if len(file_locs) > 1 else 0.0,
    }


def calculate_function_complexity_statistics(complexities: list[float]) -> dict[str, Any]:
    """Calculate function complexity statistics.

    Args:
        complexities: List of complexity values

    Returns:
        Dictionary containing complexity statistics
    """
    if not complexities:
        return {}

    return {
        "avg_complexity": statistics.mean(complexities),
        "min_complexity": min(complexities),
        "max_complexity": max(complexities),
    }


def collect_metrics_from_reports(reports: list[Any], metric_name: str) -> list[float]:
    """Collect values for a specific metric from reports.

    Args:
        reports: List of metric reports
        metric_name: Name of the metric to collect

    Returns:
        List of metric values
    """
    values = []
    try:
        metric_type = MetricType(metric_name)
        for report in reports:
            for metric in report.metrics:
                if metric.metric_type == metric_type:
                    values.append(metric.value)
    except ValueError:
        # Unknown metric type
        pass

    return values


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


def truncate_path_for_display(path: str, max_length: int) -> str:
    """Truncate long paths for display with ellipsis.

    Args:
        path: Path string to truncate
        max_length: Maximum allowed length

    Returns:
        Truncated path string
    """
    if len(path) <= max_length:
        return path
    return "..." + path[-(max_length - 3) :]


def format_display_path(rel_path: Path, common_base: Path, path_style: str) -> str:
    """Format a relative path for display based on the specified style.

    Args:
        rel_path: Relative path to format
        common_base: Common base directory
        path_style: Display style ('parent', 'full', or 'relative')

    Returns:
        Formatted path string
    """
    if rel_path == Path("."):
        return common_base.name or "."

    if path_style == "parent":
        # Show only immediate parent/name
        parts = rel_path.parts
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2:
            # For two parts, show both (parent/child)
            return str(Path(*parts))
        # For deeper paths, show last 2 components
        return str(Path(*parts[-2:]))
    if path_style == "full":
        # Full path with NO truncation
        return str(rel_path)
    # relative (default)
    return str(rel_path)


def find_common_base_directory(reports: list[Any], base_dir: Path) -> Path:
    """Find the common base directory for all analyzed files.

    Args:
        reports: List of metric reports
        base_dir: Default base directory

    Returns:
        Common base directory path
    """
    import os

    all_file_dirs = [report.file_path.parent for report in reports]
    if all_file_dirs:
        try:
            return Path(os.path.commonpath([str(d) for d in all_file_dirs]))
        except ValueError:
            return base_dir
    else:
        return base_dir


def remove_duplicate_files(files: list[Any]) -> list[Any]:
    """Remove duplicate files from a list based on object identity.

    Args:
        files: List of file objects

    Returns:
        List with duplicates removed
    """
    return list({id(f): f for f in files}.values())


def calculate_relative_depth(dir_path: Path, common_base: Path) -> tuple[Path | None, int]:
    """Calculate the relative path and depth from common base.

    Args:
        dir_path: Directory path to analyze
        common_base: Common base directory

    Returns:
        Tuple of (relative_path, depth) or None if not under common_base
    """
    try:
        if dir_path == common_base:
            return Path("."), 0
        rel_path = dir_path.relative_to(common_base)
        return rel_path, len(rel_path.parts)
    except ValueError:
        # Directory is not under common_base
        return None, 0


def determine_statistics_grouping_type(stats_data: dict[str, Any]) -> str:
    """Determine if statistics are grouped by directory or module.

    Args:
        stats_data: Statistics data dictionary

    Returns:
        'DIRECTORY' or 'MODULE' based on key patterns
    """
    # Better detection: check if any key contains path separators or looks like a module
    is_directory = any(("/" in str(k) or "\\" in str(k) or Path(str(k)).parts) for k in stats_data)
    return "DIRECTORY" if is_directory else "MODULE"
