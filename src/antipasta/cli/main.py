"""Main CLI entry point for antipasta."""

from typing import Any

import click

from antipasta import __version__
from antipasta.cli.config import config as config_group

# For backward compatibility
from antipasta.cli.config.config_generate import generate as generate_cmd
from antipasta.cli.config.config_validate import validate as validate_cmd
from antipasta.cli.metrics import metrics as metrics_cmd
from antipasta.cli.stats import stats as stats_cmd


@click.group()
@click.version_option(version=__version__, prog_name="antipasta")
def cli() -> None:
    """antipasta: A code quality enforcement tool that analyzes code complexity metrics."""


# Add main commands
cli.add_command(config_group, name="config")
cli.add_command(metrics_cmd, name="metrics")
cli.add_command(stats_cmd, name="stats")


# Backward compatibility aliases (hidden from help)
# These will show deprecation warnings when used
def create_deprecated_command(new_cmd_path: str, old_function: click.Command) -> click.Command:
    """Create a deprecated command wrapper."""

    @click.command(hidden=True)  # Hidden from help text
    @click.pass_context
    def deprecated_wrapper(ctx: click.Context, /, **kwargs: Any) -> None:
        click.echo(
            f"⚠️  Warning: This command is deprecated. "
            f"Please use 'antipasta {new_cmd_path}' instead.",
            err=True,
        )
        ctx.invoke(old_function, **kwargs)

    # Copy over options and arguments from original command
    deprecated_wrapper.params = old_function.params.copy()
    return deprecated_wrapper


# Create deprecated aliases
generate_config_deprecated = create_deprecated_command("config generate", generate_cmd)
validate_config_deprecated = create_deprecated_command("config validate", validate_cmd)

cli.add_command(generate_config_deprecated, name="generate-config")
cli.add_command(validate_config_deprecated, name="validate-config")


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    cli(argv)
