"""Statistics command for code metrics analysis."""

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.metrics import MetricType

# Metric prefix mappings for easier UX
METRIC_PREFIXES = {
    "loc": [
        MetricType.LINES_OF_CODE,
        MetricType.LOGICAL_LINES_OF_CODE,
        MetricType.SOURCE_LINES_OF_CODE,
        MetricType.COMMENT_LINES,
        MetricType.BLANK_LINES,
    ],
    "cyc": [MetricType.CYCLOMATIC_COMPLEXITY],
    "cog": [MetricType.COGNITIVE_COMPLEXITY],
    "hal": [
        MetricType.HALSTEAD_VOLUME,
        MetricType.HALSTEAD_DIFFICULTY,
        MetricType.HALSTEAD_EFFORT,
        MetricType.HALSTEAD_TIME,
        MetricType.HALSTEAD_BUGS,
    ],
    "mai": [MetricType.MAINTAINABILITY_INDEX],
    "all": list(MetricType),  # All available metrics
}

# Maximum depth for unlimited traversal (safety boundary)
MAX_DEPTH = 20


def parse_metrics(metric_args: tuple[str, ...]) -> list[str]:
    """Parse metric arguments, expanding prefixes to full metric names.

    Args:
        metric_args: Tuple of metric arguments (prefixes or full names)

    Returns:
        List of full metric names to include
    """
    metrics_to_include = []

    for arg in metric_args:
        # Check if it's a known prefix
        if arg in METRIC_PREFIXES:
            # Add all metrics for this prefix
            for metric_type in METRIC_PREFIXES[arg]:
                if metric_type.value not in metrics_to_include:
                    metrics_to_include.append(metric_type.value)
        else:
            # Try to interpret as a full metric name
            try:
                metric_type = MetricType(arg)
                if metric_type.value not in metrics_to_include:
                    metrics_to_include.append(metric_type.value)
            except ValueError:
                # Unknown metric, show warning but continue
                click.echo(
                    f"Warning: Unknown metric '{arg}'. "
                    f"Available prefixes: {', '.join(METRIC_PREFIXES.keys())}",
                    err=True,
                )

    return metrics_to_include


@click.command()
@click.option(
    "--pattern",
    "-p",
    multiple=True,
    help="Glob patterns to match files (e.g., '**/*.py', 'src/**/*.js')",
)
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Base directory to search in",
)
@click.option(
    "--by-directory",
    is_flag=True,
    help="Group statistics by directory",
)
@click.option(
    "--by-module",
    is_flag=True,
    help="Group statistics by module (Python packages)",
)
@click.option(
    "--depth",
    type=int,
    default=1,
    help="Directory depth to display when using --by-directory (0=unlimited, default: 1)",
)
@click.option(
    "--path-style",
    type=click.Choice(["relative", "parent", "full"]),
    default="relative",
    help=(
        "Path display style for directories "
        "(relative: truncated paths, parent: immediate parent/name, full: no truncation)"
    ),
)
@click.option(
    "--metric",
    "-m",
    multiple=True,
    help="Metrics to include: loc, cyc, cog, hal, mai, all (or full names)",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv", "all"]),
    default="table",
    help="Output format (use 'all' to generate all formats)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=True, dir_okay=True, path_type=Path),
    help="Output file or directory (for 'all' format)",
)
def stats(
    pattern: tuple[str, ...],
    directory: Path,
    by_directory: bool,
    by_module: bool,
    depth: int,
    path_style: str,
    metric: tuple[str, ...],
    format: str,
    output: Path | None,
) -> None:
    """Collect and display code metrics statistics.

    Performs analysis once and can output in multiple formats.

    Examples:
        # Display overall statistics in terminal
        antipasta stats -p "**/*.py"

        # Stats by directory
        antipasta stats -p "src/**/*.py" -p "tests/**/*.py" --by-directory

        # Include metrics (using short prefixes or full names)
        antipasta stats -p "**/*.py" -m cyc -m cog  # Cyclomatic & cognitive complexity
        antipasta stats -p "**/*.py" -m hal          # All Halstead metrics
        antipasta stats -p "**/*.py" -m all          # All available metrics

        # Save to file
        antipasta stats -p "**/*.py" --output report.txt
        antipasta stats -p "**/*.py" --format json --output report.json
        antipasta stats -p "**/*.py" --format csv --output report.csv

        # Generate ALL formats at once (9 files from 1 analysis!)
        antipasta stats -p "**/*.py" --format all --output ./reports/
    """
    # Default patterns if none specified
    if not pattern:
        pattern = ("**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx")

    # Collect files
    files: list[Path] = []
    for pat in pattern:
        files.extend(directory.glob(pat))

    if not files:
        click.echo("No files found matching the specified patterns.", err=True)
        return

    # Load config (use defaults)
    config = AntipastaConfig.generate_default()

    # Create aggregator and detector to preview what will be analyzed
    aggregator = MetricAggregator(config)

    # Group files by language to see what will actually be analyzed
    from antipasta.core.detector import LanguageDetector

    detector = LanguageDetector(ignore_patterns=config.ignore_patterns)
    if config.use_gitignore:
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            detector.add_gitignore(gitignore_path)

    files_by_language = detector.group_by_language(files)

    # Count analyzable files (currently only Python is supported)
    analyzable_files = sum(
        len(f) for lang, f in files_by_language.items() if lang.value == "python"
    )
    ignored_files = len(files) - sum(len(f) for f in files_by_language.values())

    # Show file breakdown
    click.echo(f"Found {len(files)} files matching patterns")
    if ignored_files > 0:
        click.echo(f"  - {ignored_files} ignored (matching .gitignore or ignore patterns)")
    for lang, lang_files in files_by_language.items():
        status = "✓" if lang.value == "python" else "✗ (not supported)"
        click.echo(f"  - {len(lang_files)} {lang.value} files {status}")

    if analyzable_files == 0:
        click.echo(
            "\nNo analyzable files found (only Python is currently supported).",
            err=True,
        )
        return

    # Analyze files
    click.echo(f"\nAnalyzing {analyzable_files} Python files...")
    reports = aggregator.analyze_files(files)

    # Parse metrics to include
    metrics_to_include = parse_metrics(metric)

    # If no metrics specified, default to LOC metrics
    if not metric:  # If user didn't provide ANY -m flags
        metrics_to_include = [m.value for m in METRIC_PREFIXES["loc"]]

    # Handle 'all' format - generate all reports
    if format == "all":
        _generate_all_reports(reports, metrics_to_include, output or Path("."))
    else:
        # Collect statistics based on grouping
        if by_directory:
            stats_data = _collect_directory_stats(
                reports, metrics_to_include, directory, depth, path_style
            )
        elif by_module:
            stats_data = _collect_module_stats(reports, metrics_to_include)
        else:
            stats_data = _collect_overall_stats(reports, metrics_to_include)

        # Display or save results
        if output:
            _save_stats(stats_data, format, output)
            click.echo(f"✓ Saved to {output}")
        else:
            if format == "json":
                _display_json(stats_data)
            elif format == "csv":
                _display_csv(stats_data)
            else:
                _display_table(stats_data)


def _collect_overall_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect overall statistics across all files."""
    stats = {
        "files": {
            "count": len(reports),
            "total_loc": 0,
            "avg_loc": 0.0,
            "min_loc": 0,
            "max_loc": 0,
            "std_dev": 0.0,
        },
        "functions": {
            "count": 0,
            "total_loc": 0,
            "avg_loc": 0.0,
            "min_loc": 0,
            "max_loc": 0,
        },
    }

    # Check if we should collect LOC metrics
    should_collect_loc = any(
        metric in metrics_to_include
        for metric in ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
    )

    # Collect LOC per file (only if requested)
    file_locs = []
    function_names = set()  # Track unique function names
    function_complexities = []  # Use complexity as proxy for function size

    for report in reports:
        # File LOC (only if requested)
        if should_collect_loc:
            file_loc = next(
                (
                    m.value
                    for m in report.metrics
                    if m.metric_type == MetricType.LINES_OF_CODE and m.function_name is None
                ),
                0,
            )
            if file_loc > 0:
                file_locs.append(file_loc)

        # Collect function-level metrics
        # Since LOC per function isn't available, use cyclomatic complexity
        for metric in report.metrics:
            if metric.function_name:  # Any metric with a function name
                function_names.add((report.file_path, metric.function_name))
                # Use cyclomatic complexity as a proxy for function complexity
                if metric.metric_type == MetricType.CYCLOMATIC_COMPLEXITY:
                    function_complexities.append(metric.value)

    # Calculate file statistics (only if LOC was collected)
    if should_collect_loc and file_locs:
        stats["files"]["total_loc"] = sum(file_locs)
        stats["files"]["avg_loc"] = statistics.mean(file_locs)
        stats["files"]["min_loc"] = min(file_locs)
        stats["files"]["max_loc"] = max(file_locs)
        if len(file_locs) > 1:
            stats["files"]["std_dev"] = statistics.stdev(file_locs)
    elif should_collect_loc:
        # LOC was requested but no data found, keep the default zeros
        pass
    else:
        # LOC was not requested, remove the LOC-specific fields
        del stats["files"]["total_loc"]
        del stats["files"]["avg_loc"]
        del stats["files"]["min_loc"]
        del stats["files"]["max_loc"]
        del stats["files"]["std_dev"]

    # Calculate function statistics
    stats["functions"]["count"] = len(function_names)
    if function_complexities:
        # Since we don't have LOC per function, report complexity instead
        stats["functions"]["avg_complexity"] = statistics.mean(function_complexities)
        stats["functions"]["min_complexity"] = min(function_complexities)
        stats["functions"]["max_complexity"] = max(function_complexities)
        # Note: We're not setting LOC metrics for functions since they're not available

    # Add additional metrics if requested
    for metric_name in metrics_to_include:
        stats[metric_name] = _collect_metric_stats(reports, metric_name)

    return stats


def _collect_directory_stats(
    reports: list[Any], metrics_to_include: list[str], base_dir: Path, depth: int, path_style: str
) -> dict[str, Any]:
    """Collect statistics grouped by directory with hierarchical aggregation.

    Args:
        reports: List of metric reports
        metrics_to_include: Additional metrics to include
        base_dir: Base directory for relative paths
        depth: Maximum depth of directories to display (1 = top-level only)
    """
    if not reports:
        return {}

    # Handle unlimited depth with safety boundary
    effective_depth = MAX_DEPTH if depth == 0 else depth

    # Build a tree structure for aggregation
    dir_stats: dict[Path, dict[str, Any]] = defaultdict(
        lambda: {
            "direct_files": [],  # Files directly in this directory
            "all_files": [],  # All files including subdirectories
            "function_names": set(),
            "metrics": defaultdict(list),
        }
    )

    # First pass: organize files by their immediate parent directory
    for report in reports:
        parent_dir = report.file_path.parent
        dir_stats[parent_dir]["direct_files"].append(report)

        # Collect metrics from this file
        for metric in report.metrics:
            if metric.function_name:
                dir_stats[parent_dir]["function_names"].add(metric.function_name)
            if metric.metric_type.value in metrics_to_include:
                dir_stats[parent_dir]["metrics"][metric.metric_type.value].append(metric.value)

    # Second pass: aggregate files up the directory tree
    # This ensures parent directories include stats from all descendants
    all_dirs = sorted(dir_stats.keys(), key=lambda p: len(p.parts), reverse=True)
    for dir_path in all_dirs:
        # Add this directory's files to all parent directories
        current = dir_path
        while current != current.parent:
            parent = current.parent
            if parent not in dir_stats:
                dir_stats[parent] = {
                    "direct_files": [],
                    "all_files": [],
                    "function_names": set(),
                    "metrics": defaultdict(list),
                }

            # Add all files from child to parent's aggregated list
            dir_stats[parent]["all_files"].extend(dir_stats[dir_path]["direct_files"])
            dir_stats[parent]["function_names"].update(dir_stats[dir_path]["function_names"])

            # Aggregate metrics
            for metric_name, values in dir_stats[dir_path]["metrics"].items():
                dir_stats[parent]["metrics"][metric_name].extend(values)

            current = parent

    # Each directory should also include its own direct files in the all_files list
    for _dir_path, data in dir_stats.items():
        data["all_files"].extend(data["direct_files"])

    # Find the common base directory for cleaner display
    import os

    all_file_dirs = [report.file_path.parent for report in reports]
    if all_file_dirs:
        try:
            common_base = Path(os.path.commonpath([str(d) for d in all_file_dirs]))
        except ValueError:
            common_base = base_dir
    else:
        common_base = base_dir

    # Build results based on depth
    results = {}
    for dir_path, data in dir_stats.items():
        # Skip if no files in this directory (shouldn't happen, but be safe)
        if not data["all_files"]:
            continue

        # Calculate depth relative to common base
        try:
            if dir_path == common_base:
                rel_path = Path(".")
                dir_depth = 0
            else:
                rel_path = dir_path.relative_to(common_base)
                dir_depth = len(rel_path.parts)
        except ValueError:
            # Directory is not under common_base, skip it
            continue

        # Skip directories deeper than requested depth
        if dir_depth >= effective_depth:
            continue

        # Check if we should collect LOC metrics
        should_collect_loc = any(
            metric in metrics_to_include
            for metric in ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
        )

        # Calculate statistics for this directory
        file_locs = []
        if should_collect_loc:
            for report in data["all_files"]:
                file_loc = next(
                    (
                        m.value
                        for m in report.metrics
                        if m.metric_type == MetricType.LINES_OF_CODE and m.function_name is None
                    ),
                    0,
                )
                if file_loc > 0:
                    file_locs.append(file_loc)

        # Create display path
        if rel_path == Path("."):
            display_path = common_base.name if common_base.name else "."
        else:
            if path_style == "parent":
                # Show only immediate parent/name
                parts = rel_path.parts
                if len(parts) == 1:
                    display_path = parts[0]
                elif len(parts) == 2:
                    # For two parts, show both (parent/child)
                    display_path = str(Path(*parts))
                else:
                    # For deeper paths, show last 2 components
                    display_path = str(Path(*parts[-2:]))
            elif path_style == "full":
                # Full path with NO truncation
                display_path = str(rel_path)
            else:  # relative (default)
                display_path = str(rel_path)

        # Apply truncation for relative and parent styles (NOT for full)
        if path_style != "full" and len(display_path) > 30:
            display_path = "..." + display_path[-(30 - 3) :]

        # Remove duplicate counts (a file might be counted multiple times in aggregation)
        unique_files = list({id(f): f for f in data["all_files"]}.values())

        results[display_path] = {
            "file_count": len(unique_files),
            "function_count": len(data["function_names"]),
        }

        # Add LOC stats only if they were collected
        if should_collect_loc:
            results[display_path]["avg_file_loc"] = (
                int(statistics.mean(file_locs)) if file_locs else 0
            )
            results[display_path]["total_loc"] = sum(file_locs)

        # Add additional metrics
        for metric_name, values in data["metrics"].items():
            if values:
                # Remove duplicates from aggregated metrics too
                unique_values = values[: len(unique_files)]  # Rough deduplication
                results[display_path][f"avg_{metric_name}"] = statistics.mean(unique_values)

    return results


def _collect_module_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect statistics grouped by Python module."""
    module_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "files": [],
            "function_names": set(),
            "metrics": defaultdict(list),
        }
    )

    # Group reports by module
    for report in reports:
        # Determine module from file path
        module_parts: list[str] = []
        current_path = report.file_path.parent

        # Walk up looking for __init__.py files
        while current_path != current_path.parent:
            if (current_path / "__init__.py").exists():
                module_parts.insert(0, current_path.name)
                current_path = current_path.parent
            else:
                break

        module_name = ".".join(module_parts) if module_parts else "<root>"
        module_stats[module_name]["files"].append(report)

        # Collect unique function names
        for metric in report.metrics:
            if metric.function_name:
                module_stats[module_name]["function_names"].add(metric.function_name)

            if metric.metric_type.value in metrics_to_include:
                module_stats[module_name]["metrics"][metric.metric_type.value].append(metric.value)

    # Check if we should collect LOC metrics
    should_collect_loc = any(
        metric in metrics_to_include
        for metric in ["lines_of_code", "logical_lines_of_code", "source_lines_of_code"]
    )

    # Calculate statistics
    results = {}
    for module_name, data in module_stats.items():
        # Similar calculation as directory stats
        file_locs = []
        if should_collect_loc:
            for report in data["files"]:
                file_loc = next(
                    (
                        m.value
                        for m in report.metrics
                        if m.metric_type == MetricType.LINES_OF_CODE and m.function_name is None
                    ),
                    0,
                )
                if file_loc > 0:
                    file_locs.append(file_loc)

        results[module_name] = {
            "file_count": len(data["files"]),
            "function_count": len(data["function_names"]),
        }

        # Add LOC stats only if they were collected
        if should_collect_loc:
            results[module_name]["avg_file_loc"] = (
                int(statistics.mean(file_locs)) if file_locs else 0
            )
            results[module_name]["total_loc"] = sum(file_locs)

        # Add additional metrics
        for metric_name, values in data["metrics"].items():
            if values:
                results[module_name][f"avg_{metric_name}"] = statistics.mean(values)

    return results


def _collect_metric_stats(reports: list[Any], metric_name: str) -> dict[str, Any]:
    """Collect statistics for a specific metric."""
    values = []

    try:
        metric_type = MetricType(metric_name)
    except ValueError:
        return {"error": f"Unknown metric: {metric_name}"}

    for report in reports:
        for metric in report.metrics:
            if metric.metric_type == metric_type:
                values.append(metric.value)

    if not values:
        return {"count": 0, "avg": 0, "min": 0, "max": 0}

    return {
        "count": len(values),
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
    }


def _display_table(stats_data: dict[str, Any]) -> None:
    """Display statistics as a formatted table."""
    if isinstance(stats_data, dict) and "files" in stats_data:
        # Overall statistics
        click.echo("\n" + "=" * 60)
        click.echo("CODE METRICS STATISTICS")
        click.echo("=" * 60 + "\n")

        # File statistics
        click.echo("FILE STATISTICS:")
        click.echo(f"  Total files: {stats_data['files']['count']}")
        if "total_loc" in stats_data["files"]:
            click.echo(f"  Total LOC: {stats_data['files']['total_loc']:,}")
            click.echo(f"  Average LOC per file: {stats_data['files']['avg_loc']:.1f}")
            click.echo(f"  Min LOC: {stats_data['files']['min_loc']}")
            click.echo(f"  Max LOC: {stats_data['files']['max_loc']}")
            if stats_data["files"].get("std_dev", 0) > 0:
                click.echo(f"  Standard deviation: {stats_data['files']['std_dev']:.1f}")

        # Function statistics
        click.echo("\nFUNCTION STATISTICS:")
        click.echo(f"  Total functions: {stats_data['functions']['count']}")
        if stats_data["functions"]["count"] > 0:
            if "avg_complexity" in stats_data["functions"]:
                click.echo(f"  Average complexity: {stats_data['functions']['avg_complexity']:.1f}")
                click.echo(f"  Min complexity: {stats_data['functions']['min_complexity']:.1f}")
                click.echo(f"  Max complexity: {stats_data['functions']['max_complexity']:.1f}")
            elif "avg_loc" in stats_data["functions"]:
                # Fallback to LOC if available (for backward compatibility)
                click.echo(f"  Average LOC per function: {stats_data['functions']['avg_loc']:.1f}")
                click.echo(f"  Min LOC: {stats_data['functions']['min_loc']}")
                click.echo(f"  Max LOC: {stats_data['functions']['max_loc']}")

        # Additional metrics
        for key, value in stats_data.items():
            if key not in ["files", "functions"] and isinstance(value, dict):
                click.echo(f"\n{key.upper().replace('_', ' ')} STATISTICS:")
                click.echo(f"  Count: {value.get('count', 0)}")
                click.echo(f"  Average: {value.get('avg', 0):.2f}")
                click.echo(f"  Min: {value.get('min', 0):.2f}")
                click.echo(f"  Max: {value.get('max', 0):.2f}")
    else:
        # Directory or module statistics
        click.echo("\n" + "=" * 80)
        # Better detection: check if any key contains path separators or looks like a module
        is_directory = any(
            ("/" in str(k) or "\\" in str(k) or Path(str(k)).parts) for k in stats_data
        )
        click.echo("CODE METRICS BY " + ("DIRECTORY" if is_directory else "MODULE"))
        click.echo("=" * 80 + "\n")

        # Find all metric keys
        all_keys = set()
        for data in stats_data.values():
            all_keys.update(data.keys())

        # Create header
        headers = [
            "Location",
            "Files",
            "Functions",
        ]

        # Add LOC headers only if present in data
        if any("avg_file_loc" in data for data in stats_data.values()):
            headers.append("Avg File LOC")
        if any("total_loc" in data for data in stats_data.values()):
            headers.append("Total LOC")
        for key in sorted(all_keys):
            if key.startswith("avg_") and key not in [
                "avg_file_loc",
                "avg_function_loc",
            ]:
                headers.append(key.replace("avg_", "Avg ").replace("_", " ").title())

        # Print header
        click.echo(_format_table_row(headers))
        click.echo("-" * sum(len(h) + 3 for h in headers))

        # Print rows
        for location, data in sorted(stats_data.items()):
            row = [
                _truncate_path(location, 30),
                str(data.get("file_count", 0)),
                str(data.get("function_count", 0)),
            ]

            # Add LOC data only if present in headers
            if "Avg File LOC" in headers:
                row.append(f"{data.get('avg_file_loc', 0):.1f}")
            if "Total LOC" in headers:
                row.append(f"{data.get('total_loc', 0):,}")

            for key in sorted(all_keys):
                if key.startswith("avg_") and key not in [
                    "avg_file_loc",
                    "avg_function_loc",
                ]:
                    row.append(f"{data.get(key, 0):.2f}")

            click.echo(_format_table_row(row))


def _format_table_row(values: list[Any]) -> str:
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


def _truncate_path(path: str, max_length: int) -> str:
    """Truncate long paths for display."""
    if len(path) <= max_length:
        return path
    return "..." + path[-(max_length - 3) :]


def _display_json(stats_data: dict[str, Any]) -> None:
    """Display statistics as JSON."""
    import json

    click.echo(json.dumps(stats_data, indent=2))


def _display_csv(stats_data: dict[str, Any]) -> None:
    """Display statistics as CSV."""
    import csv
    import sys

    if isinstance(stats_data, dict) and "files" in stats_data:
        # Overall statistics - flatten structure
        writer = csv.writer(sys.stdout)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Files", stats_data["files"]["count"]])
        if "total_loc" in stats_data["files"]:
            writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
            writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])
        writer.writerow(["Total Functions", stats_data["functions"]["count"]])
        if "avg_complexity" in stats_data["functions"]:
            writer.writerow(
                [
                    "Average Function Complexity",
                    stats_data["functions"]["avg_complexity"],
                ]
            )
        elif "avg_loc" in stats_data["functions"]:
            writer.writerow(
                [
                    "Average LOC per Function",
                    stats_data["functions"]["avg_loc"],
                ]
            )
    else:
        # Directory/module statistics
        if not stats_data:
            return

        # Get all keys
        all_keys = set()
        for data in stats_data.values():
            all_keys.update(data.keys())

        # Write header
        writer = csv.writer(sys.stdout)
        headers = ["location"] + sorted(all_keys)
        writer.writerow(headers)

        # Write data
        for location, data in sorted(stats_data.items()):
            row = [location]
            for key in sorted(all_keys):
                row.append(data.get(key, 0))
            writer.writerow(row)


def _save_stats(stats_data: dict[str, Any], format: str, output_path: Path) -> None:
    """Save statistics to a file."""
    if format == "json":
        with open(output_path, "w") as f:
            json.dump(stats_data, f, indent=2)
    elif format == "csv":
        import csv

        with open(output_path, "w") as f:
            if isinstance(stats_data, dict) and "files" in stats_data:
                # Overall statistics
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Total Files", stats_data["files"]["count"]])
                if "total_loc" in stats_data["files"]:
                    writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
                    writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])
                writer.writerow(["Total Functions", stats_data["functions"]["count"]])
                if "avg_complexity" in stats_data["functions"]:
                    writer.writerow(
                        [
                            "Average Function Complexity",
                            stats_data["functions"]["avg_complexity"],
                        ]
                    )
            else:
                # Directory/module statistics
                if stats_data:
                    all_keys = set()
                    for data in stats_data.values():
                        all_keys.update(data.keys())

                    writer = csv.writer(f)
                    headers = ["location"] + sorted(all_keys)
                    writer.writerow(headers)

                    for location, data in sorted(stats_data.items()):
                        row = [location]
                        for key in sorted(all_keys):
                            row.append(data.get(key, 0))
                        writer.writerow(row)
    else:  # table format
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _display_table(stats_data)
        with open(output_path, "w") as f:
            f.write(buffer.getvalue())


def _generate_all_reports(reports: list[Any], metrics: list[str], output_dir: Path) -> None:
    """Generate all report formats from a single analysis."""
    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\nGenerating all reports in {output_dir}...")

    # Generate all three groupings
    overall_stats = _collect_overall_stats(reports, metrics)
    dir_stats = _collect_directory_stats(
        reports, metrics, Path("."), 1, "relative"
    )  # Default to relative style
    module_stats = _collect_module_stats(reports, metrics)

    # Save each grouping in each format
    formats_saved = 0

    # Overall statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_overall.{ext}"
        _save_stats(overall_stats, fmt, output_file)
        click.echo(f"  ✓ Overall statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    # Directory statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_by_directory.{ext}"
        _save_stats(dir_stats, fmt, output_file)
        click.echo(f"  ✓ Directory statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    # Module statistics
    for fmt, ext in [("json", "json"), ("csv", "csv"), ("table", "txt")]:
        output_file = output_dir / f"stats_by_module.{ext}"
        _save_stats(module_stats, fmt, output_file)
        click.echo(f"  ✓ Module statistics ({fmt.upper()}): {output_file}")
        formats_saved += 1

    click.echo(f"\n✅ Generated {formats_saved} report files from a single analysis!")
    click.echo(f"   Total files analyzed: {len(reports)}")
    click.echo(f"   Total functions found: {overall_stats['functions']['count']}")
    if "total_loc" in overall_stats["files"]:
        click.echo(f"   Total LOC: {overall_stats['files']['total_loc']:,.0f}")
