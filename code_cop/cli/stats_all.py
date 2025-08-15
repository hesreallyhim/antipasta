"""Generate all statistics reports from a single analysis."""

import json
from pathlib import Path

import click

from code_cop.cli.stats import (
    _collect_directory_stats,
    _collect_module_stats,
    _collect_overall_stats,
    _display_table,
)
from code_cop.core.aggregator import MetricAggregator
from code_cop.core.config import CodeCopConfig
from code_cop.core.detector import LanguageDetector


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
    "--metric",
    "-m",
    multiple=True,
    help="Additional metrics to include (e.g., cyclomatic_complexity, cognitive_complexity)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Directory to save output files",
)
@click.option(
    "--prefix",
    default="code_metrics",
    help="Prefix for output filenames",
)
def stats_all(
    pattern: tuple[str, ...],
    directory: Path,
    metric: tuple[str, ...],
    output_dir: Path,
    prefix: str,
) -> None:
    """Analyze code metrics once and generate all report formats.

    This command performs the analysis once and generates:
    - Overall statistics (text, JSON, CSV)
    - Statistics by directory (text, JSON, CSV)
    - Statistics by module (text, JSON, CSV)

    Example:
        code-cop stats-all -p "**/*.py" -o reports/ --prefix myproject
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

    # Analyze files ONCE
    click.echo(f"\nAnalyzing {analyzable_files} Python files...")
    reports = aggregator.analyze_files(files)

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate all statistics formats
    click.echo(f"\nGenerating reports in {output_dir}...")

    # 1. Overall statistics
    overall_stats = _collect_overall_stats(reports, metric)

    # Save overall stats as JSON
    overall_json_path = output_dir / f"{prefix}_overall.json"
    with open(overall_json_path, "w") as f:
        json.dump(overall_stats, f, indent=2)
    click.echo(f"  ✓ Overall statistics (JSON): {overall_json_path}")

    # Save overall stats as text
    overall_text_path = output_dir / f"{prefix}_overall.txt"
    with open(overall_text_path, "w") as f:
        # Redirect click output to file
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _display_table(overall_stats)
        f.write(buffer.getvalue())
    click.echo(f"  ✓ Overall statistics (text): {overall_text_path}")

    # 2. Directory statistics
    dir_stats = _collect_directory_stats(reports, metric)

    # Save directory stats as JSON
    dir_json_path = output_dir / f"{prefix}_by_directory.json"
    with open(dir_json_path, "w") as f:
        json.dump(dir_stats, f, indent=2)
    click.echo(f"  ✓ Directory statistics (JSON): {dir_json_path}")

    # Save directory stats as CSV
    dir_csv_path = output_dir / f"{prefix}_by_directory.csv"
    with open(dir_csv_path, "w") as f:
        import csv
        if dir_stats:
            # Get all keys
            all_keys = set()
            for data in dir_stats.values():
                all_keys.update(data.keys())

            # Write header
            writer = csv.writer(f)
            headers = ["location"] + sorted(all_keys)
            writer.writerow(headers)

            # Write data
            for location, data in sorted(dir_stats.items()):
                row = [location]
                for key in sorted(all_keys):
                    row.append(data.get(key, 0))
                writer.writerow(row)
    click.echo(f"  ✓ Directory statistics (CSV): {dir_csv_path}")

    # 3. Module statistics
    module_stats = _collect_module_stats(reports, metric)

    # Save module stats as JSON
    module_json_path = output_dir / f"{prefix}_by_module.json"
    with open(module_json_path, "w") as f:
        json.dump(module_stats, f, indent=2)
    click.echo(f"  ✓ Module statistics (JSON): {module_json_path}")

    # Save module stats as CSV
    module_csv_path = output_dir / f"{prefix}_by_module.csv"
    with open(module_csv_path, "w") as f:
        import csv
        if module_stats:
            # Get all keys
            all_keys = set()
            for data in module_stats.values():
                all_keys.update(data.keys())

            # Write header
            writer = csv.writer(f)
            headers = ["location"] + sorted(all_keys)
            writer.writerow(headers)

            # Write data
            for location, data in sorted(module_stats.items()):
                row = [location]
                for key in sorted(all_keys):
                    row.append(data.get(key, 0))
                writer.writerow(row)
    click.echo(f"  ✓ Module statistics (CSV): {module_csv_path}")

    # Summary
    click.echo(f"\n✅ Generated {6} report files from a single analysis!")
    click.echo(f"   Analysis performed on {len(reports)} files")
    click.echo(f"   Total functions found: {overall_stats['functions']['count']}")
    click.echo(f"   Total LOC: {overall_stats['files']['total_loc']:,.0f}")