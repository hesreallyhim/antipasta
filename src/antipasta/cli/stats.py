"""Statistics command for code metrics analysis."""

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.detector import LanguageDetector
from antipasta.core.metrics import MetricType

from .stats_utils import (
    calculate_file_loc_statistics,
    calculate_function_complexity_statistics,
    calculate_metric_statistics,
    calculate_relative_depth,
    collect_function_complexities_from_reports,
    collect_function_names_from_reports,
    collect_metrics_from_reports,
    determine_statistics_grouping_type,
    extract_file_loc_from_report,
    find_common_base_directory,
    format_display_path,
    remove_duplicate_files,
    should_collect_loc_metrics,
    truncate_path_for_display,
)

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


def collect_files_from_patterns(patterns: tuple[str, ...], directory: Path) -> list[Path]:
    """Collect files matching the given patterns from the directory.

    Args:
        patterns: Tuple of glob patterns to match
        directory: Base directory to search in

    Returns:
        List of file paths matching the patterns
    """
    files: list[Path] = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))
    return files


def get_default_patterns() -> tuple[str, ...]:
    """Get default file patterns when none are specified.

    Returns:
        Tuple of default glob patterns
    """
    return ("**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx")


def validate_files_found(files: list[Path]) -> bool:
    """Validate that files were found and display error if not.

    Args:
        files: List of collected files

    Returns:
        True if files were found, False otherwise
    """
    if not files:
        click.echo("No files found matching the specified patterns.", err=True)
        return False
    return True


def setup_configuration_with_overrides(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> tuple[AntipastaConfig, ConfigOverride]:
    """Set up configuration with command-line overrides.

    Args:
        include_pattern: Include patterns from command line
        exclude_pattern: Exclude patterns from command line
        no_gitignore: Whether to disable gitignore
        force_analyze: Whether to force analyze all files

    Returns:
        Tuple of (config, override)
    """
    config = AntipastaConfig.generate_default()

    override = ConfigOverride(
        include_patterns=list(include_pattern),
        exclude_patterns=list(exclude_pattern),
        disable_gitignore=no_gitignore,
        force_analyze=force_analyze,
    )

    if override.has_overrides():
        config = config.apply_overrides(override)
        display_override_messages(include_pattern, exclude_pattern, no_gitignore, force_analyze)

    return config, override


def display_override_messages(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> None:
    """Display messages about configuration overrides.

    Args:
        include_pattern: Include patterns from command line
        exclude_pattern: Exclude patterns from command line
        no_gitignore: Whether gitignore is disabled
        force_analyze: Whether force analyze is enabled
    """
    if force_analyze:
        click.echo("Force analyzing all files (ignoring exclusions)...")
    elif include_pattern:
        click.echo(f"Including patterns: {', '.join(include_pattern)}")
    if exclude_pattern:
        click.echo(f"Additional exclusions: {', '.join(exclude_pattern)}")
    if no_gitignore:
        click.echo("Ignoring .gitignore patterns")


def setup_language_detector(
    config: AntipastaConfig, override: ConfigOverride, directory: Path
) -> "LanguageDetector":
    """Set up language detector with configuration.

    Args:
        config: Antipasta configuration
        override: Configuration overrides
        directory: Base directory

    Returns:
        Configured language detector
    """
    from antipasta.core.detector import LanguageDetector

    detector = LanguageDetector(
        ignore_patterns=config.ignore_patterns,
        include_patterns=override.include_patterns if override else [],
        base_dir=directory,
    )

    if config.use_gitignore:
        gitignore_path = directory / ".gitignore"
        if gitignore_path.exists():
            detector.add_gitignore(gitignore_path)

    return detector


def analyze_and_display_file_breakdown(
    files: list[Path], detector: "LanguageDetector"
) -> tuple[dict[Any, list[Path]], int, int]:
    """Analyze files and display breakdown by language.

    Args:
        files: List of all files found
        detector: Language detector

    Returns:
        Tuple of (files_by_language, analyzable_files_count, ignored_files_count)
    """
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

    return files_by_language, analyzable_files, ignored_files


def validate_analyzable_files(analyzable_files: int) -> bool:
    """Validate that there are analyzable files and display error if not.

    Args:
        analyzable_files: Number of analyzable files

    Returns:
        True if there are analyzable files, False otherwise
    """
    if analyzable_files == 0:
        click.echo(
            "\nNo analyzable files found (only Python is currently supported).",
            err=True,
        )
        return False
    return True


def perform_analysis_with_feedback(
    aggregator: MetricAggregator, files: list[Path], analyzable_files: int
) -> list[Any]:
    """Perform file analysis with user feedback.

    Args:
        aggregator: Metric aggregator
        files: List of files to analyze
        analyzable_files: Number of analyzable files

    Returns:
        List of analysis reports
    """
    click.echo(f"\nAnalyzing {analyzable_files} Python files...")
    return aggregator.analyze_files(files)


def get_metrics_to_include(metric: tuple[str, ...]) -> list[str]:
    """Get the list of metrics to include, applying defaults if needed.

    Args:
        metric: Metric arguments from command line

    Returns:
        List of metric names to include
    """
    metrics_to_include = parse_metrics(metric)

    # If no metrics specified, default to LOC metrics
    if not metric:  # If user didn't provide ANY -m flags
        metrics_to_include = [m.value for m in METRIC_PREFIXES["loc"]]

    return metrics_to_include


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
        return _collect_directory_stats(reports, metrics_to_include, directory, depth, path_style)
    if by_module:
        return _collect_module_stats(reports, metrics_to_include)
    return _collect_overall_stats(reports, metrics_to_include)


def handle_output_and_display(stats_data: dict[str, Any], format: str, output: Path | None) -> None:
    """Handle output and display of statistics based on format and output options.

    Args:
        stats_data: Statistics data to output
        format: Output format
        output: Output file path (optional)
    """
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
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
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
    # Use default patterns if none specified
    patterns_to_use = pattern if pattern else get_default_patterns()

    # Collect and validate files
    files = collect_files_from_patterns(patterns_to_use, directory)
    if not validate_files_found(files):
        return

    # Set up configuration with overrides
    config, override = setup_configuration_with_overrides(
        include_pattern, exclude_pattern, no_gitignore, force_analyze
    )

    # Set up language detection and file analysis
    aggregator = MetricAggregator(config)
    detector = setup_language_detector(config, override, directory)

    # Analyze files and display breakdown
    files_by_language, analyzable_files, ignored_files = analyze_and_display_file_breakdown(
        files, detector
    )

    if not validate_analyzable_files(analyzable_files):
        return

    # Perform analysis
    reports = perform_analysis_with_feedback(aggregator, files, analyzable_files)

    # Get metrics to include
    metrics_to_include = get_metrics_to_include(metric)

    # Handle 'all' format - generate all reports
    if format == "all":
        _generate_all_reports(reports, metrics_to_include, output or Path("."))
    else:
        # Collect statistics based on grouping method
        stats_data = collect_statistics_based_on_grouping(
            reports, metrics_to_include, by_directory, by_module, directory, depth, path_style
        )

        # Handle output and display
        handle_output_and_display(stats_data, format, output)


def _collect_overall_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect overall statistics across all files."""
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
        stats[metric_name] = _collect_metric_stats(reports, metric_name)

    return stats


def _build_directory_tree_structure(
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


def _aggregate_directory_tree_upward(dir_stats: dict[Path, dict[str, Any]]) -> None:
    """Aggregate directory statistics up the tree hierarchy.

    Args:
        dir_stats: Directory statistics to aggregate (modified in-place)
    """
    all_dirs = sorted(dir_stats.keys(), key=lambda p: len(p.parts), reverse=True)
    for dir_path in all_dirs:
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


def _build_directory_results(
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
        # Skip if no files in this directory
        if not data["all_files"]:
            continue

        # Calculate relative path and depth
        rel_path, dir_depth = calculate_relative_depth(dir_path, common_base)
        if rel_path is None:  # Directory not under common_base
            continue

        # Skip directories deeper than requested depth
        if dir_depth >= effective_depth:
            continue

        # Calculate LOC statistics if needed
        file_locs = []
        if should_collect_loc:
            for report in data["all_files"]:
                file_loc = extract_file_loc_from_report(report)
                if file_loc > 0:
                    file_locs.append(file_loc)

        # Create display path
        display_path = _create_display_path(rel_path, common_base, path_style)

        # Remove duplicate files
        unique_files = remove_duplicate_files(data["all_files"])

        # Build result entry
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
                # Remove duplicates from aggregated metrics
                unique_values = values[: len(unique_files)]
                results[display_path][f"avg_{metric_name}"] = statistics.mean(unique_values)

    return results


def _create_display_path(rel_path: Path, common_base: Path, path_style: str) -> str:
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


def _collect_directory_stats(
    reports: list[Any], metrics_to_include: list[str], base_dir: Path, depth: int, path_style: str
) -> dict[str, Any]:
    """Collect statistics grouped by directory with hierarchical aggregation.

    Args:
        reports: List of metric reports
        metrics_to_include: Additional metrics to include
        base_dir: Base directory for relative paths
        depth: Maximum depth of directories to display (1 = top-level only)
        path_style: Path display style
    """
    if not reports:
        return {}

    # Handle unlimited depth with safety boundary
    effective_depth = MAX_DEPTH if depth == 0 else depth

    # Build directory tree structure
    dir_stats = _build_directory_tree_structure(reports, metrics_to_include)

    # Aggregate statistics up the directory tree
    _aggregate_directory_tree_upward(dir_stats)

    # Find common base directory
    common_base = find_common_base_directory(reports, base_dir)

    # Build and return final results
    return _build_directory_results(
        dir_stats, metrics_to_include, common_base, effective_depth, path_style
    )


def _determine_module_name(report: Any) -> str:
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


def _group_reports_by_module(
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
        module_name = _determine_module_name(report)
        module_stats[module_name]["files"].append(report)

        # Collect metrics
        for metric in report.metrics:
            if metric.function_name:
                module_stats[module_name]["function_names"].add(metric.function_name)
            if metric.metric_type.value in metrics_to_include:
                module_stats[module_name]["metrics"][metric.metric_type.value].append(metric.value)

    return module_stats


def _calculate_module_statistics(
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
        # Calculate LOC statistics if needed
        file_locs = []
        if should_collect_loc:
            for report in data["files"]:
                file_loc = extract_file_loc_from_report(report)
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


def _collect_module_stats(reports: list[Any], metrics_to_include: list[str]) -> dict[str, Any]:
    """Collect statistics grouped by Python module."""
    module_stats = _group_reports_by_module(reports, metrics_to_include)
    return _calculate_module_statistics(module_stats, metrics_to_include)


def _collect_metric_stats(reports: list[Any], metric_name: str) -> dict[str, Any]:
    """Collect statistics for a specific metric."""
    try:
        MetricType(metric_name)  # Validate metric name
    except ValueError:
        return {"error": f"Unknown metric: {metric_name}"}

    values = collect_metrics_from_reports(reports, metric_name)
    return calculate_metric_statistics(values)


def _display_overall_statistics(stats_data: dict[str, Any]) -> None:
    """Display overall statistics in table format.

    Args:
        stats_data: Overall statistics data
    """
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


def _display_grouped_statistics(stats_data: dict[str, Any]) -> None:
    """Display directory or module grouped statistics in table format.

    Args:
        stats_data: Grouped statistics data
    """
    click.echo("\n" + "=" * 80)
    grouping_type = determine_statistics_grouping_type(stats_data)
    click.echo(f"CODE METRICS BY {grouping_type}")
    click.echo("=" * 80 + "\n")

    # Find all metric keys
    all_keys = set()
    for data in stats_data.values():
        all_keys.update(data.keys())

    # Create header
    headers = ["Location", "Files", "Functions"]

    # Add LOC headers only if present in data
    if any("avg_file_loc" in data for data in stats_data.values()):
        headers.append("Avg File LOC")
    if any("total_loc" in data for data in stats_data.values()):
        headers.append("Total LOC")
    for key in sorted(all_keys):
        if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
            headers.append(key.replace("avg_", "Avg ").replace("_", " ").title())

    # Print header
    click.echo(_format_table_row(headers))
    click.echo("-" * sum(len(h) + 3 for h in headers))

    # Print rows
    for location, data in sorted(stats_data.items()):
        row = [
            truncate_path_for_display(location, 30),
            str(data.get("file_count", 0)),
            str(data.get("function_count", 0)),
        ]

        # Add LOC data only if present in headers
        if "Avg File LOC" in headers:
            row.append(f"{data.get('avg_file_loc', 0):.1f}")
        if "Total LOC" in headers:
            row.append(f"{data.get('total_loc', 0):,}")

        for key in sorted(all_keys):
            if key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]:
                row.append(f"{data.get(key, 0):.2f}")

        click.echo(_format_table_row(row))


def _display_table(stats_data: dict[str, Any]) -> None:
    """Display statistics as a formatted table."""
    if isinstance(stats_data, dict) and "files" in stats_data:
        _display_overall_statistics(stats_data)
    else:
        _display_grouped_statistics(stats_data)


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
