"""Configuration management for stats command."""

from pathlib import Path
from typing import Any

import click

from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.detector import LanguageDetector


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
) -> LanguageDetector:
    """Set up language detector with configuration.

    Args:
        config: Antipasta configuration
        override: Configuration overrides
        directory: Base directory

    Returns:
        Configured language detector
    """
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


def setup_analysis_environment(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
    directory: Path,
) -> tuple[AntipastaConfig, ConfigOverride, Any, LanguageDetector]:
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
    from antipasta.core.aggregator import MetricAggregator

    config, override = setup_configuration_with_overrides(
        include_pattern, exclude_pattern, no_gitignore, force_analyze
    )

    aggregator = MetricAggregator(config)
    detector = setup_language_detector(config, override, directory)

    return config, override, aggregator, detector
