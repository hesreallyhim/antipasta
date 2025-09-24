"""Statistics command for code metrics analysis."""

from collections import defaultdict
import json
from pathlib import Path
import statistics
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
        # Don't show include patterns if force analyzing
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
    analyzable_files = _count_analyzable_files(files_by_language)
    ignored_files = _count_ignored_files(files, files_by_language)

    _display_file_breakdown(files, files_by_language, ignored_files)

    return files_by_language, analyzable_files, ignored_files


def _count_analyzable_files(files_by_language: dict[Any, list[Path]]) -> int:
    """Count files that can be analyzed (currently only Python).

    Args:
        files_by_language: Files grouped by language

    Returns:
        Number of analyzable files
    """
    return sum(
        len(files) for lang, files in files_by_language.items()
        if lang.value == "python"
    )


def _count_ignored_files(
    all_files: list[Path], files_by_language: dict[Any, list[Path]]
) -> int:
    """Count files that were ignored.

    Args:
        all_files: All files found
        files_by_language: Files grouped by language

    Returns:
        Number of ignored files
    """
    total_grouped = sum(len(files) for files in files_by_language.values())
    return len(all_files) - total_grouped


def _display_file_breakdown(
    files: list[Path], files_by_language: dict[Any, list[Path]], ignored_files: int
) -> None:
    """Display the file breakdown information.

    Args:
        files: All files found
        files_by_language: Files grouped by language
        ignored_files: Number of ignored files
    """
    click.echo(f"Found {len(files)} files matching patterns")

    if ignored_files > 0:
        click.echo(f"  - {ignored_files} ignored (matching .gitignore or ignore patterns)")

    for lang, lang_files in files_by_language.items():
        status = _get_language_support_status(lang.value)
        click.echo(f"  - {len(lang_files)} {lang.value} files {status}")


def _get_language_support_status(language: str) -> str:
    """Get the support status display string for a language.

    Args:
        language: Language name

    Returns:
        Status display string
    """
    return "✓" if language == "python" else "✗ (not supported)"


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
        parsed_metrics = _parse_single_metric_arg(arg)
        if parsed_metrics:
            _add_unique_metrics(metrics_to_include, parsed_metrics)
        else:
            _warn_unknown_metric(arg)

    return metrics_to_include


def _parse_single_metric_arg(arg: str) -> list[str]:
    """Parse a single metric argument into metric values.

    Args:
        arg: Metric argument (prefix or full name)

    Returns:
        List of metric values, or empty list if unknown
    """
    # Check if it's a known prefix
    if arg in METRIC_PREFIXES:
        return [metric_type.value for metric_type in METRIC_PREFIXES[arg]]

    # Try to interpret as a full metric name
    try:
        metric_type = MetricType(arg)
        return [metric_type.value]
    except ValueError:
        return []


def _add_unique_metrics(target_list: list[str], new_metrics: list[str]) -> None:
    """Add metrics to target list if not already present.

    Args:
        target_list: List to add metrics to (modified in place)
        new_metrics: Metrics to add
    """
    for metric in new_metrics:
        if metric not in target_list:
            target_list.append(metric)


def _warn_unknown_metric(arg: str) -> None:
    """Display warning for unknown metric argument.

    Args:
        arg: Unknown metric argument
    """
    click.echo(
        f"Warning: Unknown metric '{arg}'. "
        f"Available prefixes: {', '.join(METRIC_PREFIXES.keys())}",
        err=True,
    )


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
    # Phase 1: File collection and validation
    files = _collect_and_validate_files(pattern, directory)
    if not files:
        return

    # Phase 2: Configuration and setup
    config, override, aggregator, detector = _setup_analysis_environment(
        include_pattern, exclude_pattern, no_gitignore, force_analyze, directory
    )

    # Phase 3: File analysis and filtering
    analyzable_files, reports = _analyze_files_with_validation(
        files, detector, aggregator
    )
    if not reports:
        return

    # Phase 4: Generate output
    _generate_output(
        reports, metric, format, output,
        by_directory, by_module, directory, depth, path_style
    )


def _collect_and_validate_files(pattern: tuple[str, ...], directory: Path) -> list[Path] | None:
    """Collect files and validate they exist.

    Args:
        pattern: File patterns to search for
        directory: Base directory to search in

    Returns:
        List of files if found, None if validation fails
    """
    patterns_to_use = pattern or get_default_patterns()
    files = collect_files_from_patterns(patterns_to_use, directory)

    if not validate_files_found(files):
        return None

    return files


def _setup_analysis_environment(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
    directory: Path,
) -> tuple[AntipastaConfig, ConfigOverride, MetricAggregator, LanguageDetector]:
    """Set up the analysis environment with configuration and tools.

    Args:
        include_pattern: Include patterns from command line
        exclude_pattern: Exclude patterns from command line
        no_gitignore: Whether to disable gitignore
        force_analyze: Whether to force analyze all files
        directory: Base directory

    Returns:
        Tuple of (config, override, aggregator, detector)
    """
    config, override = setup_configuration_with_overrides(
        include_pattern, exclude_pattern, no_gitignore, force_analyze
    )

    aggregator = MetricAggregator(config)
    detector = setup_language_detector(config, override, directory)

    return config, override, aggregator, detector


def _analyze_files_with_validation(
    files: list[Path],
    detector: LanguageDetector,
    aggregator: MetricAggregator,
) -> tuple[int, list[Any] | None]:
    """Analyze files and validate results.

    Args:
        files: Files to analyze
        detector: Language detector
        aggregator: Metric aggregator

    Returns:
        Tuple of (analyzable_files_count, reports) or (0, None) if validation fails
    """
    files_by_language, analyzable_files, ignored_files = analyze_and_display_file_breakdown(
        files, detector
    )

    if not validate_analyzable_files(analyzable_files):
        return 0, None

    reports = perform_analysis_with_feedback(aggregator, files, analyzable_files)
    return analyzable_files, reports


def _generate_output(
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
    metrics_to_include = get_metrics_to_include(metric)

    if format == "all":
        _generate_all_reports(reports, metrics_to_include, output or Path("."))
    else:
        stats_data = collect_statistics_based_on_grouping(
            reports, metrics_to_include, by_directory, by_module, directory, depth, path_style
        )
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
    # Process directories from deepest to shallowest
    sorted_dirs = sorted(dir_stats.keys(), key=lambda p: len(p.parts), reverse=True)

    for dir_path in sorted_dirs:
        _propagate_stats_to_parents(dir_stats, dir_path)

    # Include direct files in all_files for each directory
    _finalize_all_files(dir_stats)


def _propagate_stats_to_parents(
    dir_stats: dict[Path, dict[str, Any]], dir_path: Path
) -> None:
    """Propagate statistics from a directory to all its parent directories.

    Args:
        dir_stats: Directory statistics dictionary
        dir_path: Current directory path to propagate from
    """
    current = dir_path
    while current != current.parent:
        parent = current.parent
        _ensure_parent_exists(dir_stats, parent)
        _aggregate_child_to_parent(dir_stats, parent, dir_path)
        current = parent


def _ensure_parent_exists(dir_stats: dict[Path, dict[str, Any]], parent: Path) -> None:
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


def _aggregate_child_to_parent(
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


def _finalize_all_files(dir_stats: dict[Path, dict[str, Any]]) -> None:
    """Add direct files to all_files list for each directory.

    Args:
        dir_stats: Directory statistics dictionary
    """
    for data in dir_stats.values():
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
        if not _should_include_directory(data, dir_path, common_base, effective_depth):
            continue

        rel_path, _ = calculate_relative_depth(dir_path, common_base)
        display_path = _create_display_path(rel_path, common_base, path_style)
        unique_files = remove_duplicate_files(data["all_files"])

        # Build base result entry
        result_entry = _build_base_directory_result(data, unique_files)

        # Add LOC statistics if needed
        if should_collect_loc:
            _add_loc_statistics_to_result(result_entry, data["all_files"])

        # Add additional metrics
        _add_metric_statistics_to_result(result_entry, data["metrics"], unique_files)

        results[display_path] = result_entry

    return results


def _should_include_directory(
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
    if dir_depth >= effective_depth:
        return False

    return True


def _build_base_directory_result(data: dict[str, Any], unique_files: list[Any]) -> dict[str, Any]:
    """Build base result entry with file and function counts.

    Args:
        data: Directory data
        unique_files: List of unique files

    Returns:
        Base result dictionary
    """
    return {
        "file_count": len(unique_files),
        "function_count": len(data["function_names"]),
    }


def _add_loc_statistics_to_result(result_entry: dict[str, Any], all_files: list[Any]) -> None:
    """Add LOC statistics to result entry.

    Args:
        result_entry: Result entry to modify
        all_files: List of all files to analyze
    """
    file_locs = _extract_file_locs_from_reports(all_files)

    result_entry["avg_file_loc"] = (
        int(statistics.mean(file_locs)) if file_locs else 0
    )
    result_entry["total_loc"] = sum(file_locs)


def _extract_file_locs_from_reports(reports: list[Any]) -> list[int]:
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


def _add_metric_statistics_to_result(
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
        result_entry = _build_base_module_result(data)

        if should_collect_loc:
            _add_module_loc_statistics(result_entry, data["files"])

        _add_module_metric_statistics(result_entry, data["metrics"])

        results[module_name] = result_entry

    return results


def _build_base_module_result(data: dict[str, Any]) -> dict[str, Any]:
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


def _add_module_loc_statistics(result_entry: dict[str, Any], files: list[Any]) -> None:
    """Add LOC statistics to module result entry.

    Args:
        result_entry: Result entry to modify
        files: List of files in the module
    """
    file_locs = _extract_file_locs_from_reports(files)

    result_entry["avg_file_loc"] = (
        int(statistics.mean(file_locs)) if file_locs else 0
    )
    result_entry["total_loc"] = sum(file_locs)


def _add_module_metric_statistics(result_entry: dict[str, Any], metrics: dict[str, list[Any]]) -> None:
    """Add metric statistics to module result entry.

    Args:
        result_entry: Result entry to modify
        metrics: Metrics data for the module
    """
    for metric_name, values in metrics.items():
        if values:
            result_entry[f"avg_{metric_name}"] = statistics.mean(values)


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
    _display_statistics_header()
    _display_file_statistics(stats_data.get("files", {}))
    _display_function_statistics(stats_data.get("functions", {}))
    _display_additional_metrics(stats_data)


def _display_statistics_header() -> None:
    """Display the statistics header."""
    click.echo("\n" + "=" * 60)
    click.echo("CODE METRICS STATISTICS")
    click.echo("=" * 60 + "\n")


def _display_file_statistics(file_stats: dict[str, Any]) -> None:
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


def _display_function_statistics(func_stats: dict[str, Any]) -> None:
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
        _display_complexity_metrics(func_stats)
    elif "avg_loc" in func_stats:
        _display_function_loc_metrics(func_stats)


def _display_complexity_metrics(func_stats: dict[str, Any]) -> None:
    """Display function complexity metrics.

    Args:
        func_stats: Function statistics with complexity data
    """
    click.echo(f"  Average complexity: {func_stats['avg_complexity']:.1f}")
    click.echo(f"  Min complexity: {func_stats['min_complexity']:.1f}")
    click.echo(f"  Max complexity: {func_stats['max_complexity']:.1f}")


def _display_function_loc_metrics(func_stats: dict[str, Any]) -> None:
    """Display function LOC metrics (backward compatibility).

    Args:
        func_stats: Function statistics with LOC data
    """
    click.echo(f"  Average LOC per function: {func_stats['avg_loc']:.1f}")
    click.echo(f"  Min LOC: {func_stats['min_loc']}")
    click.echo(f"  Max LOC: {func_stats['max_loc']}")


def _display_additional_metrics(stats_data: dict[str, Any]) -> None:
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


def _display_grouped_statistics(stats_data: dict[str, Any]) -> None:
    """Display directory or module grouped statistics in table format.

    Args:
        stats_data: Grouped statistics data
    """
    _display_grouped_statistics_header(stats_data)
    headers = _build_grouped_statistics_headers(stats_data)
    _display_table_headers(headers)
    _display_grouped_statistics_rows(stats_data, headers)


def _display_grouped_statistics_header(stats_data: dict[str, Any]) -> None:
    """Display header section for grouped statistics."""
    click.echo("\n" + "=" * 80)
    grouping_type = determine_statistics_grouping_type(stats_data)
    click.echo(f"CODE METRICS BY {grouping_type}")
    click.echo("=" * 80 + "\n")


def _build_grouped_statistics_headers(stats_data: dict[str, Any]) -> list[str]:
    """Build header row for grouped statistics table.

    Args:
        stats_data: Grouped statistics data

    Returns:
        List of header column names
    """
    all_keys = _collect_all_statistic_keys(stats_data)
    headers = ["Location", "Files", "Functions"]

    _add_loc_headers_if_present(headers, stats_data)
    _add_metric_headers(headers, all_keys)

    return headers


def _add_loc_headers_if_present(headers: list[str], stats_data: dict[str, Any]) -> None:
    """Add LOC-related headers if present in the data."""
    if any("avg_file_loc" in data for data in stats_data.values()):
        headers.append("Avg File LOC")
    if any("total_loc" in data for data in stats_data.values()):
        headers.append("Total LOC")


def _add_metric_headers(headers: list[str], all_keys: set[str]) -> None:
    """Add metric headers for average values."""
    for key in sorted(all_keys):
        if _is_displayable_average_metric(key):
            formatted_header = _format_metric_header(key)
            headers.append(formatted_header)


def _is_displayable_average_metric(key: str) -> bool:
    """Check if a metric key should be displayed as a column header."""
    return key.startswith("avg_") and key not in ["avg_file_loc", "avg_function_loc"]


def _format_metric_header(key: str) -> str:
    """Format a metric key into a readable header."""
    return key.replace("avg_", "Avg ").replace("_", " ").title()


def _display_table_headers(headers: list[str]) -> None:
    """Display table headers and separator line."""
    click.echo(_format_table_row(headers))
    click.echo("-" * sum(len(h) + 3 for h in headers))


def _display_grouped_statistics_rows(stats_data: dict[str, Any], headers: list[str]) -> None:
    """Display data rows for grouped statistics.

    Args:
        stats_data: Statistics data to display
        headers: Table headers for column ordering
    """
    for location, data in sorted(stats_data.items()):
        row = _build_grouped_statistics_row(location, data, headers)
        click.echo(_format_table_row(row))


def _build_grouped_statistics_row(location: str, data: dict[str, Any], headers: list[str]) -> list[str]:
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

    _add_loc_data_to_row(row, data, headers)
    _add_metric_data_to_row(row, data, headers)

    return row


def _add_loc_data_to_row(row: list[str], data: dict[str, Any], headers: list[str]) -> None:
    """Add LOC data to row if present in headers."""
    if "Avg File LOC" in headers:
        row.append(f"{data.get('avg_file_loc', 0):.1f}")
    if "Total LOC" in headers:
        row.append(f"{data.get('total_loc', 0):,}")


def _add_metric_data_to_row(row: list[str], data: dict[str, Any], headers: list[str]) -> None:
    """Add metric data to row for displayable average metrics."""
    all_keys = set(data.keys())
    for key in sorted(all_keys):
        if _is_displayable_average_metric(key):
            row.append(f"{data.get(key, 0):.2f}")


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
    """Display statistics as CSV to stdout."""
    import csv
    import sys

    writer = csv.writer(sys.stdout)

    if _is_overall_statistics(stats_data):
        _display_overall_statistics_csv(writer, stats_data)
    else:
        _display_grouped_statistics_csv(writer, stats_data)


def _display_overall_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display overall statistics as CSV."""
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Files", stats_data["files"]["count"]])

    _display_file_loc_metrics_csv(writer, stats_data)
    writer.writerow(["Total Functions", stats_data["functions"]["count"]])
    _display_function_complexity_metrics_csv(writer, stats_data)


def _display_file_loc_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display file LOC metrics in CSV format."""
    if "total_loc" in stats_data["files"]:
        writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
        writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])


def _display_function_complexity_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
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


def _display_grouped_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Display directory/module statistics as CSV."""
    if not stats_data:
        return

    all_keys = _collect_all_statistic_keys(stats_data)
    headers = ["location"] + sorted(all_keys)
    writer.writerow(headers)

    _write_grouped_data_rows_csv(writer, stats_data, all_keys)


def _save_stats(stats_data: dict[str, Any], format: str, output_path: Path) -> None:
    """Save statistics to a file in the specified format."""
    if format == "json":
        _save_stats_as_json(stats_data, output_path)
    elif format == "csv":
        _save_stats_as_csv(stats_data, output_path)
    else:  # table format
        _save_stats_as_table(stats_data, output_path)


def _save_stats_as_json(stats_data: dict[str, Any], output_path: Path) -> None:
    """Save statistics data as JSON format."""
    with open(output_path, "w") as f:
        json.dump(stats_data, f, indent=2)


def _save_stats_as_csv(stats_data: dict[str, Any], output_path: Path) -> None:
    """Save statistics data as CSV format."""
    import csv

    with open(output_path, "w") as f:
        if _is_overall_statistics(stats_data):
            _write_overall_statistics_csv(csv.writer(f), stats_data)
        else:
            _write_grouped_statistics_csv(csv.writer(f), stats_data)


def _save_stats_as_table(stats_data: dict[str, Any], output_path: Path) -> None:
    """Save statistics data as formatted table."""
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        _display_table(stats_data)
    with open(output_path, "w") as f:
        f.write(buffer.getvalue())


def _is_overall_statistics(stats_data: dict[str, Any]) -> bool:
    """Check if statistics data represents overall statistics."""
    return isinstance(stats_data, dict) and "files" in stats_data


def _write_overall_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Write overall statistics to CSV writer."""
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Files", stats_data["files"]["count"]])

    _write_file_loc_metrics_csv(writer, stats_data)
    _write_function_metrics_csv(writer, stats_data)


def _write_file_loc_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Write file LOC metrics to CSV writer."""
    if "total_loc" in stats_data["files"]:
        writer.writerow(["Total LOC", stats_data["files"]["total_loc"]])
        writer.writerow(["Average LOC per File", stats_data["files"]["avg_loc"]])


def _write_function_metrics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Write function metrics to CSV writer."""
    writer.writerow(["Total Functions", stats_data["functions"]["count"]])

    if "avg_complexity" in stats_data["functions"]:
        writer.writerow([
            "Average Function Complexity",
            stats_data["functions"]["avg_complexity"],
        ])


def _write_grouped_statistics_csv(writer: Any, stats_data: dict[str, Any]) -> None:
    """Write grouped statistics (directory/module) to CSV writer."""
    if not stats_data:
        return

    all_keys = _collect_all_statistic_keys(stats_data)
    headers = ["location"] + sorted(all_keys)
    writer.writerow(headers)

    _write_grouped_data_rows_csv(writer, stats_data, all_keys)


def _collect_all_statistic_keys(stats_data: dict[str, Any]) -> set[str]:
    """Collect all unique keys from grouped statistics data."""
    all_keys = set()
    for data in stats_data.values():
        all_keys.update(data.keys())
    return all_keys


def _write_grouped_data_rows_csv(writer: Any, stats_data: dict[str, Any], all_keys: set[str]) -> None:
    """Write data rows for grouped statistics to CSV writer."""
    for location, data in sorted(stats_data.items()):
        row = [location]
        for key in sorted(all_keys):
            row.append(data.get(key, 0))
        writer.writerow(row)


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
