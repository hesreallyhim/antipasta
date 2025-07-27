"""Main CLI entry point for code-cop."""


import click

from code_cop import __version__
from code_cop.cli.metrics import metrics as metrics_cmd
from code_cop.cli.stats import stats as stats_cmd
from code_cop.cli.validate import validate_config as validate_config_cmd


@click.group()
@click.version_option(version=__version__, prog_name="code-cop")
def cli() -> None:
    """code-cop: A code quality enforcement tool that analyzes code complexity metrics."""
    pass


# Add commands
cli.add_command(metrics_cmd, name="metrics")
cli.add_command(stats_cmd, name="stats")
cli.add_command(validate_config_cmd, name="validate-config")


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    cli(argv)
