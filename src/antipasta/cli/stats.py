"""Statistics command for code metrics analysis."""

import json
from pathlib import Path
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.detector import LanguageDetector
from antipasta.core.metrics import MetricType

from .stats_collection import (
    collect_directory_stats,
    collect_metric_stats,
    collect_module_stats,
    collect_overall_stats,
)
from .stats_display import (
    display_csv,
    display_json,
    display_table,
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
        return collect_directory_stats(reports, metrics_to_include, directory, depth, path_style)
    if by_module:
        return collect_module_stats(reports, metrics_to_include)
    return collect_overall_stats(reports, metrics_to_include)


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
        _display_stats_to_stdout(stats_data, format)


def _display_stats_to_stdout(stats_data: dict[str, Any], format: str) -> None:
    """Display statistics to stdout based on format.

    Args:
        stats_data: Statistics data to display
        format: Output format (json, csv, or table)
    """
    display_functions = {
        "json": display_json,
        "csv": display_csv,
        "table": display_table,
    }

    display_func = display_functions.get(format, display_table)
    display_func(stats_data)


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




def _save_stats(stats_data: dict[str, Any], format: str, output_path: Path) -> None:
    """Save statistics to a file in the specified format."""
    import contextlib
    import io

    if format == "json":
        with open(output_path, "w") as f:
            json.dump(stats_data, f, indent=2)
    elif format == "csv":
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            display_csv(stats_data)
        with open(output_path, "w") as f:
            f.write(buffer.getvalue())
    else:  # table format
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            display_table(stats_data)
        with open(output_path, "w") as f:
            f.write(buffer.getvalue())


def _generate_all_reports(reports: list[Any], metrics: list[str], output_dir: Path) -> None:
    """Generate all report formats from a single analysis."""
    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\nGenerating all reports in {output_dir}...")

    # Generate all three groupings
    overall_stats = collect_overall_stats(reports, metrics)
    dir_stats = collect_directory_stats(
        reports, metrics, Path("."), 1, "relative"
    )  # Default to relative style
    module_stats = collect_module_stats(reports, metrics)

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
