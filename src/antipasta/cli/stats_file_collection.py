"""File collection and validation utilities for stats command."""

from pathlib import Path

import click

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


def parse_metrics(metric_args: tuple[str, ...]) -> list[str]:
    """Parse metric arguments, expanding prefixes to full metric names.

    Args:
        metric_args: Tuple of metric arguments (prefixes or full names)

    Returns:
        List of full metric names to include
    """
    metrics_to_include: list[str] = []

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
        f"Warning: Unknown metric '{arg}'. Available prefixes: {', '.join(METRIC_PREFIXES.keys())}",
        err=True,
    )


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


def collect_and_validate_files(pattern: tuple[str, ...], directory: Path) -> list[Path] | None:
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
