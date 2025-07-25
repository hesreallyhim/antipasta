"""Main CLI entry point for code-cop."""

import sys
from typing import Optional

import click

from code_cop import __version__


@click.group()
@click.version_option(version=__version__, prog_name="code-cop")
def cli() -> None:
    """code-cop: A code quality enforcement tool that analyzes code complexity metrics."""
    pass


@cli.command()
def metrics() -> None:
    """Analyze code metrics for specified files."""
    click.echo("Metrics command not yet implemented")
    sys.exit(1)


@cli.command()
def validate_config() -> None:
    """Validate a code-cop configuration file."""
    click.echo("Validate config command not yet implemented")
    sys.exit(1)


def main(argv: Optional[list[str]] = None) -> None:
    """Main entry point for the CLI."""
    cli(argv)