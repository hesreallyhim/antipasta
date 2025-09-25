"""Configuration management commands."""

import click

from antipasta.cli.config.config_generate import generate
from antipasta.cli.config.config_validate import validate
from antipasta.cli.config.config_view import view


@click.group()
def config() -> None:
    """Manage antipasta configuration files.

    Commands for generating, validating, and viewing antipasta configurations.
    """


# Add subcommands
config.add_command(generate)
config.add_command(validate)
config.add_command(view)
