"""Statistics command for code metrics analysis."""

from pathlib import Path

import click

from .collection.analysis import analyze_files_with_validation
from .collection.file_collection import collect_and_validate_files
from .config import setup_analysis_environment
from .output import generate_output


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
    files = collect_and_validate_files(pattern, directory)
    if not files:
        return

    # Phase 2: Configuration and setup
    config, override, aggregator, detector = setup_analysis_environment(
        include_pattern, exclude_pattern, no_gitignore, force_analyze, directory
    )

    # Phase 3: File analysis and filtering
    analyzable_files, reports = analyze_files_with_validation(files, detector, aggregator)
    if not reports:
        return

    # Phase 4: Generate output
    generate_output(
        reports, metric, format, output, by_directory, by_module, directory, depth, path_style
    )
