"""Display resolved configuration and cache locations."""

from pathlib import Path

import click

from antipasta.core.model.config_layers import resolve_paths


@click.command(name="path")
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Analysis root (defaults to cwd)",
)
def path_command(directory: Path | None) -> None:
    """Print the user config, project config, cache, and snapshot locations."""
    paths = resolve_paths(root=directory)
    click.echo(f"User config: {paths.user}")
    click.echo(f"Project config: {paths.project}")
    click.echo(f"Cache: {paths.cache}")
    click.echo(f"Snapshot: {paths.snapshot}")
