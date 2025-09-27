"""Metrics analysis command."""

from pathlib import Path

import click

from .metrics_utils_analysis import (
    determine_files_to_analyze,
    execute_analysis,
    exit_with_appropriate_code,
)
from .metrics_utils_config import prepare_configuration
from .metrics_utils_output import output_results
from .metrics_utils_override import (
    apply_overrides_to_configuration,
    create_and_configure_override,
)


@click.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    default=".antipasta.yaml",
    help="Path to configuration file",
)
@click.option(
    "--files",
    "-f",
    multiple=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    help="Files to analyze (can be specified multiple times)",
)
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Directory to analyze recursively",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Only show violations, suppress other output",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--include-pattern",
    "-i",
    multiple=True,
    help=(
        "Force include files matching pattern (overrides ignore patterns, "
        "can be specified multiple times"
    ),
)
@click.option(
    "--exclude-pattern",
    "-e",
    multiple=True,
    help="Add additional exclusion patterns (can be specified multiple times)",
)
@click.option(
    "--threshold",
    "-t",
    multiple=True,
    help=(
        "Override metric thresholds "
        "(format: metric_type=value, e.g., cyclomatic_complexity=15 or cyc=15). "
        "Prefixes: cyc=cyclomatic, cog=cognitive, mai=maintainability, "
        "vol=volume, dif=difficulty, eff=effort"
    ),
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
def metrics(
    config: Path,
    files: tuple[Path, ...],
    directory: Path | None,
    quiet: bool,
    format: str,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> None:
    """Analyze code metrics for specified files.

    Exits with code 0 if all metrics pass, 2 if violations found.

    For an interactive terminal UI, use 'antipasta tui' instead.
    """
    configuration = prepare_configuration(config, threshold, quiet)
    override = create_and_configure_override(
        include_pattern, exclude_pattern, threshold, no_gitignore, force_analyze
    )
    final_config = apply_overrides_to_configuration(
        configuration,
        override,
        quiet,
        force_analyze,
        include_pattern,
        exclude_pattern,
        threshold,
        no_gitignore,
    )

    target_files = determine_files_to_analyze(files, directory, final_config, override, quiet)
    analysis_results = execute_analysis(target_files, final_config, quiet)
    output_results(analysis_results, format, quiet)
    exit_with_appropriate_code(analysis_results["summary"])
