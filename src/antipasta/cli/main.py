"""Main CLI entry point for antipasta."""

import click

from antipasta import __version__
from antipasta.cli.metrics import metrics as metrics_cmd
from antipasta.cli.stats import stats as stats_cmd
from antipasta.cli.tui import tui as tui_cmd
from antipasta.cli.validate import validate_config as validate_config_cmd


@click.group()
@click.version_option(version=__version__, prog_name="antipasta")
def cli() -> None:
    """antipasta: A code quality enforcement tool that analyzes code complexity metrics."""
    pass


# Add commands
cli.add_command(metrics_cmd, name="metrics")
cli.add_command(stats_cmd, name="stats")
cli.add_command(tui_cmd, name="tui")
cli.add_command(validate_config_cmd, name="validate-config")


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    cli(argv)
