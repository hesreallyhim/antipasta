"""Directory statistics collection utilities for stats command."""

from collections import defaultdict
from pathlib import Path
import statistics
from typing import Any

from ..collection.metrics import add_metric_statistics_to_result
from ..utils import (
    calculate_relative_depth,
    extract_file_loc_from_report,
    find_common_base_directory,
    format_display_path,
    remove_duplicate_files,
    should_collect_loc_metrics,
    truncate_path_for_display,
)

# Maximum depth for unlimited traversal (safety boundary)
MAX_DEPTH = 20


def build_directory_tree_structure(
    reports: list[Any], metrics_to_include: list[str]
) -> dict[Path, dict[str, Any]]:
    """Build initial directory tree structure from reports.

    Args:
        reports: List of metric reports
        metrics_to_include: Metrics to collect

    Returns:
        Dictionary mapping directory paths to their data
    """
    dir_stats: dict[Path, dict[str, Any]] = defaultdict(
        lambda: {
            "direct_files": [],
            "all_files": [],
            "function_names": set(),
            "metrics": defaultdict(list),
        }
    )

    for report in reports:
        parent_dir = report.file_path.parent
        dir_stats[parent_dir]["direct_files"].append(report)

        for metric in report.metrics:
            if metric.function_name:
                dir_stats[parent_dir]["function_names"].add(metric.function_name)
            if metric.metric_type.value in metrics_to_include:
                dir_stats[parent_dir]["metrics"][metric.metric_type.value].append(metric.value)

    return dir_stats


def aggregate_directory_tree_upward(dir_stats: dict[Path, dict[str, Any]]) -> None:
    """Aggregate directory statistics up the tree hierarchy.

    Args:
        dir_stats: Directory statistics to aggregate (modified in-place)
    """
    # Process directories from deepest to shallowest
    sorted_dirs = sorted(dir_stats.keys(), key=lambda p: len(p.parts), reverse=True)

    for dir_path in sorted_dirs:
        propagate_stats_to_parents(dir_stats, dir_path)

    # Include direct files in all_files for each directory
    finalize_all_files(dir_stats)


def propagate_stats_to_parents(dir_stats: dict[Path, dict[str, Any]], dir_path: Path) -> None:
    """Propagate statistics from a directory to all its parent directories.

    Args:
        dir_stats: Directory statistics dictionary
        dir_path: Current directory path to propagate from
    """
    current = dir_path
    while current != current.parent:
        parent = current.parent
        ensure_parent_exists(dir_stats, parent)
        aggregate_child_to_parent(dir_stats, parent, dir_path)
        current = parent


def ensure_parent_exists(dir_stats: dict[Path, dict[str, Any]], parent: Path) -> None:
    """Ensure parent directory entry exists in stats.

    Args:
        dir_stats: Directory statistics dictionary
        parent: Parent directory path
    """
    if parent not in dir_stats:
        dir_stats[parent] = {
            "direct_files": [],
            "all_files": [],
            "function_names": set(),
            "metrics": defaultdict(list),
        }


def aggregate_child_to_parent(
    dir_stats: dict[Path, dict[str, Any]], parent: Path, child: Path
) -> None:
    """Aggregate child directory stats to parent.

    Args:
        dir_stats: Directory statistics dictionary
        parent: Parent directory path
        child: Child directory path
    """
    # Add files from child to parent's aggregated list
    dir_stats[parent]["all_files"].extend(dir_stats[child]["direct_files"])
    dir_stats[parent]["function_names"].update(dir_stats[child]["function_names"])

    # Aggregate metrics
    for metric_name, values in dir_stats[child]["metrics"].items():
        dir_stats[parent]["metrics"][metric_name].extend(values)


def finalize_all_files(dir_stats: dict[Path, dict[str, Any]]) -> None:
    """Add direct files to all_files list for each directory.

    Args:
        dir_stats: Directory statistics dictionary
    """
    for data in dir_stats.values():
        data["all_files"].extend(data["direct_files"])


def should_include_directory(
    data: dict[str, Any], dir_path: Path, common_base: Path, effective_depth: int
) -> bool:
    """Check if a directory should be included in results.

    Args:
        data: Directory data
        dir_path: Directory path
        common_base: Common base directory
        effective_depth: Maximum depth to include

    Returns:
        True if directory should be included
    """
    # Skip if no files in this directory
    if not data["all_files"]:
        return False

    # Calculate relative path and depth
    rel_path, dir_depth = calculate_relative_depth(dir_path, common_base)
    if rel_path is None:  # Directory not under common_base
        return False

    # Skip directories deeper than requested depth
    return not dir_depth >= effective_depth


def build_directory_results(
    dir_stats: dict[Path, dict[str, Any]],
    metrics_to_include: list[str],
    common_base: Path,
    effective_depth: int,
    path_style: str,
) -> dict[str, Any]:
    """Build final results from directory statistics.

    Args:
        dir_stats: Directory statistics data
        metrics_to_include: Metrics to include
        common_base: Common base directory
        effective_depth: Maximum depth to include
        path_style: Path display style

    Returns:
        Formatted results dictionary
    """
    results = {}
    should_collect_loc = should_collect_loc_metrics(metrics_to_include)

    for dir_path, data in dir_stats.items():
        if not should_include_directory(data, dir_path, common_base, effective_depth):
            continue

        rel_path, _ = calculate_relative_depth(dir_path, common_base)
        if rel_path is None:
            continue
        display_path = create_display_path(rel_path, common_base, path_style)
        unique_files = remove_duplicate_files(data["all_files"])

        # Build base result entry
        result_entry = {
            "file_count": len(unique_files),
            "function_count": len(data["function_names"]),
        }

        # Add LOC statistics if needed
        if should_collect_loc:
            add_loc_statistics_to_result(result_entry, data["all_files"])

        # Add additional metrics
        add_metric_statistics_to_result(result_entry, data["metrics"], unique_files)

        results[display_path] = result_entry

    return results


def create_display_path(rel_path: Path, common_base: Path, path_style: str) -> str:
    """Create display path based on style preferences.

    Args:
        rel_path: Relative path to format
        common_base: Common base directory
        path_style: Display style preference

    Returns:
        Formatted display path
    """
    display_path = format_display_path(rel_path, common_base, path_style)

    # Apply truncation for relative and parent styles (NOT for full)
    if path_style != "full" and len(display_path) > 30:
        display_path = truncate_path_for_display(display_path, 30)

    return display_path


def add_loc_statistics_to_result(result_entry: dict[str, Any], all_files: list[Any]) -> None:
    """Add LOC statistics to result entry.

    Args:
        result_entry: Result entry to modify
        all_files: List of all files to analyze
    """
    file_locs = extract_file_locs_from_reports(all_files)

    result_entry["avg_file_loc"] = int(statistics.mean(file_locs)) if file_locs else 0
    result_entry["total_loc"] = sum(file_locs)


def extract_file_locs_from_reports(reports: list[Any]) -> list[int]:
    """Extract LOC values from reports.

    Args:
        reports: List of reports to analyze

    Returns:
        List of LOC values
    """
    file_locs = []
    for report in reports:
        file_loc = extract_file_loc_from_report(report)
        if file_loc > 0:
            file_locs.append(file_loc)
    return file_locs


def collect_directory_stats(
    reports: list[Any], metrics_to_include: list[str], base_dir: Path, depth: int, path_style: str
) -> dict[str, Any]:
    """Collect statistics grouped by directory with hierarchical aggregation.

    Args:
        reports: List of metric reports
        metrics_to_include: Additional metrics to include
        base_dir: Base directory for relative paths
        depth: Maximum depth of directories to display (1 = top-level only)
        path_style: Path display style

    Returns:
        Dictionary of directory statistics
    """
    if not reports:
        return {}

    # Handle unlimited depth with safety boundary
    effective_depth = MAX_DEPTH if depth == 0 else depth

    # Build directory tree structure
    dir_stats = build_directory_tree_structure(reports, metrics_to_include)

    # Aggregate statistics up the directory tree
    aggregate_directory_tree_upward(dir_stats)

    # Find common base directory
    common_base = find_common_base_directory(reports, base_dir)

    # Build and return final results
    return build_directory_results(
        dir_stats, metrics_to_include, common_base, effective_depth, path_style
    )
