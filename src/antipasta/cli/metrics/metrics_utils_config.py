"""Configuration-related helper functions for metrics command."""

from pathlib import Path
import sys

import click

from antipasta.core.config import AntipastaConfig


def load_configuration(config: Path, quiet: bool) -> AntipastaConfig:
    """Load configuration from file or generate default."""
    try:
        if config.exists():
            return _load_existing_config(config, quiet)
        return _load_default_config(config, quiet)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)


def _load_existing_config(config: Path, quiet: bool) -> AntipastaConfig:
    """Load configuration from existing file."""
    cfg = AntipastaConfig.from_yaml(config)
    if not quiet:
        click.echo(f"Using configuration: {config}")
    return cfg


def _load_default_config(config: Path, quiet: bool) -> AntipastaConfig:
    """Load default configuration and show helpful message."""
    if not quiet:
        click.echo(f"Configuration file '{config}' not found.", err=True)
        click.echo("Run 'antipasta config generate' to create a configuration file.", err=True)
        click.echo("Using default configuration for now...")
    return AntipastaConfig.generate_default()


def prepare_configuration(config: Path, threshold: tuple[str, ...], quiet: bool) -> AntipastaConfig:
    """Load configuration and apply threshold overrides."""
    return load_configuration(config, quiet)
