"""File analysis utilities for stats command."""

from pathlib import Path
from typing import Any

import click

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.detector import LanguageDetector

from .file_collection import validate_analyzable_files


def analyze_and_display_file_breakdown(
    files: list[Path], detector: LanguageDetector
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
    return sum(len(files) for lang, files in files_by_language.items() if lang.value == "python")


def _count_ignored_files(all_files: list[Path], files_by_language: dict[Any, list[Path]]) -> int:
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


def analyze_files_with_validation(
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
