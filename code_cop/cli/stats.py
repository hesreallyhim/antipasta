"""Statistics command for code metrics analysis."""

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

from code_cop.core.aggregator import MetricAggregator
from code_cop.core.config import CodeCopConfig
from code_cop.core.metrics import MetricType


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
    "--metric",
    "-m",
    multiple=True,
    help="Additional metrics to include (e.g., cyclomatic_complexity, cognitive_complexity)",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json", "csv"]),
    default="table",
    help="Output format",
)
def stats(
    pattern: tuple[str, ...],
    directory: Path,
    by_directory: bool,
    by_module: bool,
    metric: tuple[str, ...],
    format: str,
) -> None:
    """Collect and display code metrics statistics.

    Examples:
        # Average LOC for all Python files
        code-cop stats -p "**/*.py"

        # Stats by directory for specific folders
        code-cop stats -p "src/**/*.py" -p "tests/**/*.py" --by-directory

        # Include complexity metrics
        code-cop stats -p "**/*.py" -m cyclomatic_complexity -m cognitive_complexity

        # Export as CSV
        code-cop stats -p "**/*.py" --format csv > metrics.csv
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
    config = CodeCopConfig.generate_default()

    # Create aggregator and detector to preview what will be analyzed
    aggregator = MetricAggregator(config)

    # Group files by language to see what will actually be analyzed
    from code_cop.core.detector import LanguageDetector
    detector = LanguageDetector(ignore_patterns=config.ignore_patterns)
    if config.use_gitignore:
        gitignore_path = Path(".gitignore")
        if gitignore_path.exists():
            detector.add_gitignore(gitignore_path)

    files_by_language = detector.group_by_language(files)

    # Count analyzable files (currently only Python is supported)
    analyzable_files = sum(len(f) for lang, f in files_by_language.items() if lang.value == "python")
    ignored_files = len(files) - sum(len(f) for f in files_by_language.values())

    # Show file breakdown
    click.echo(f"Found {len(files)} files matching patterns")
    if ignored_files > 0:
        click.echo(f"  - {ignored_files} ignored (matching .gitignore or ignore patterns)")
    for lang, lang_files in files_by_language.items():
        status = "✓" if lang.value == "python" else "✗ (not supported)"
        click.echo(f"  - {len(lang_files)} {lang.value} files {status}")

    if analyzable_files == 0:
        click.echo("\nNo analyzable files found (only Python is currently supported).", err=True)
        return

    # Analyze files
    click.echo(f"\nAnalyzing {analyzable_files} Python files...")
    reports = aggregator.analyze_files(files)

    # Collect statistics
    if by_directory:
        stats_data = _collect_directory_stats(reports, metric)
    elif by_module:
        stats_data = _collect_module_stats(reports, metric)
    else:
        stats_data = _collect_overall_stats(reports, metric)

    # Display results
    if format == "json":
        _display_json(stats_data)
    elif format == "csv":
        _display_csv(stats_data)
    else:
        _display_table(stats_data)


def _collect_overall_stats(reports: list[Any], metrics_to_include: tuple[str, ...]) -> dict[str, Any]:
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

    # Collect LOC per file
    file_locs = []
    function_names = set()  # Track unique function names
    function_complexities = []  # Use complexity as proxy for function size

    for report in reports:
        # File LOC
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

    # Calculate file statistics
    if file_locs:
        stats["files"]["total_loc"] = sum(file_locs)
        stats["files"]["avg_loc"] = statistics.mean(file_locs)
        stats["files"]["min_loc"] = min(file_locs)
        stats["files"]["max_loc"] = max(file_locs)
        if len(file_locs) > 1:
            stats["files"]["std_dev"] = statistics.stdev(file_locs)

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


def _collect_directory_stats(reports: list[Any], metrics_to_include: tuple[str, ...]) -> dict[str, Any]:
    """Collect statistics grouped by directory."""
    dir_stats: dict[Any, dict[str, Any]] = defaultdict(lambda: {"files": [], "function_names": set(), "metrics": defaultdict(list)})

    # Group reports by directory
    for report in reports:
        dir_path = report.file_path.parent
        dir_stats[dir_path]["files"].append(report)

        # Collect unique function names
        for metric in report.metrics:
            if metric.function_name:
                dir_stats[dir_path]["function_names"].add(metric.function_name)

            # Collect additional metrics
            if metric.metric_type.value in metrics_to_include:
                dir_stats[dir_path]["metrics"][metric.metric_type.value].append(metric.value)

    # Calculate statistics for each directory
    results = {}
    for dir_path, data in dir_stats.items():
        # File LOCs in this directory
        file_locs = []
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

        results[str(dir_path)] = {
            "file_count": len(data["files"]),
            "function_count": len(data["function_names"]),
            "avg_file_loc": statistics.mean(file_locs) if file_locs else 0,
            "total_loc": sum(file_locs),
        }

        # Add additional metrics
        for metric_name, values in data["metrics"].items():
            if values:
                results[str(dir_path)][f"avg_{metric_name}"] = statistics.mean(values)

    return results


def _collect_module_stats(reports: list[Any], metrics_to_include: tuple[str, ...]) -> dict[str, Any]:
    """Collect statistics grouped by Python module."""
    module_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"files": [], "function_names": set(), "metrics": defaultdict(list)})

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

    # Calculate statistics
    results = {}
    for module_name, data in module_stats.items():
        # Similar calculation as directory stats
        file_locs = []
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
            "avg_file_loc": statistics.mean(file_locs) if file_locs else 0,
            "total_loc": sum(file_locs),
        }

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
        click.echo(f"  Total LOC: {stats_data['files']['total_loc']:,}")
        click.echo(f"  Average LOC per file: {stats_data['files']['avg_loc']:.1f}")
        click.echo(f"  Min LOC: {stats_data['files']['min_loc']}")
        click.echo(f"  Max LOC: {stats_data['files']['max_loc']}")
        if stats_data["files"]["std_dev"] > 0:
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
        click.echo(
            "CODE METRICS BY "
            + ("DIRECTORY" if "/" in str(list(stats_data.keys())[0]) else "MODULE")
        )
        click.echo("=" * 80 + "\n")

        # Find all metric keys
        all_keys = set()
        for data in stats_data.values():
            all_keys.update(data.keys())

        # Create header
        headers = ["Location", "Files", "Functions", "Avg File LOC", "Total LOC"]
        for key in sorted(all_keys):
            if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
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
                f"{data.get('avg_file_loc', 0):.1f}",
                f"{data.get('total_loc', 0):,}",
            ]

            for key in sorted(all_keys):
                if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
                    row.append(f"{data.get(key, 0):.2f}")

            click.echo(_format_table_row(row))


def _format_table_row(values: list[Any]) -> str:
    """Format a row for table display."""
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
        writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
        writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])
        writer.writerow(["Total Functions", stats_data["functions"]["count"]])
        if "avg_complexity" in stats_data["functions"]:
            writer.writerow(["Average Function Complexity", stats_data["functions"]["avg_complexity"]])
        elif "avg_loc" in stats_data["functions"]:
            writer.writerow(["Average LOC per Function", stats_data["functions"]["avg_loc"]])
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
