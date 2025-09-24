"""Configuration override helper functions for metrics command."""

import sys

import click

from antipasta.cli.validation_utils import format_validation_error_for_cli, get_metric_help_text
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride


def handle_threshold_parsing_error(error: ValueError, threshold_str: str) -> None:
    """Handle threshold parsing errors with helpful messages."""
    click.echo(f"❌ Error: {format_validation_error_for_cli(error)}", err=True)

    # If it's a range error, show the valid range
    if "=" in threshold_str:
        metric_type = threshold_str.split("=")[0].strip()
        help_text = get_metric_help_text(metric_type)
        if help_text and metric_type in help_text:
            click.echo(f"   ℹ️  {help_text}", err=True)


def create_and_configure_override(
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
    force_analyze: bool,
) -> ConfigOverride:
    """Create configuration override object and parse threshold overrides."""
    override = ConfigOverride(
        include_patterns=list(include_pattern),
        exclude_patterns=list(exclude_pattern),
        disable_gitignore=no_gitignore,
        force_analyze=force_analyze,
    )

    parse_threshold_overrides_into_override(override, threshold)
    return override


def parse_threshold_overrides_into_override(
    override: ConfigOverride, threshold: tuple[str, ...]
) -> None:
    """Parse threshold override strings and add them to the override object."""
    for threshold_str in threshold:
        try:
            override.parse_threshold_string(threshold_str)
        except ValueError as e:
            handle_threshold_parsing_error(e, threshold_str)
            sys.exit(1)


def apply_overrides_to_configuration(
    cfg: AntipastaConfig,
    override: ConfigOverride,
    quiet: bool,
    force_analyze: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
) -> AntipastaConfig:
    """Apply configuration overrides and display status messages."""
    if not override.has_overrides():
        return cfg

    cfg = cfg.apply_overrides(override)
    display_override_status_messages(
        quiet, force_analyze, include_pattern, exclude_pattern, threshold, no_gitignore
    )
    return cfg


def display_override_status_messages(
    quiet: bool,
    force_analyze: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
) -> None:
    """Display status messages about applied configuration overrides."""
    if quiet:
        return

    messages = _collect_override_messages(
        force_analyze, include_pattern, exclude_pattern, threshold, no_gitignore
    )

    for message in messages:
        click.echo(message)


def _collect_override_messages(
    force_analyze: bool,
    include_pattern: tuple[str, ...],
    exclude_pattern: tuple[str, ...],
    threshold: tuple[str, ...],
    no_gitignore: bool,
) -> list[str]:
    """Collect all override status messages to display."""
    messages = []

    if force_analyze:
        messages.append("Force analyzing all files (ignoring exclusions)...")
    elif include_pattern:
        messages.append(f"Including patterns: {', '.join(include_pattern)}")

    if exclude_pattern:
        messages.append(f"Additional exclusions: {', '.join(exclude_pattern)}")

    if threshold:
        messages.append(f"Threshold overrides: {', '.join(threshold)}")

    if no_gitignore:
        messages.append("Ignoring .gitignore patterns")

    return messages
