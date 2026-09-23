"""Validate explicit configuration files or the active configuration layers."""

from pathlib import Path

import click
from pydantic import ValidationError

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_layers import (
    config_from_layer,
    read_layer,
    resolve_config,
    validate_config_file,
)


def _summary(config: AntipastaConfig) -> None:
    click.echo("\nConfiguration summary:")
    if config.preset is not None:
        click.echo(f"  Preset: {config.preset.value} ({config.profile})")
    elif config.profile != "standard":
        click.echo(f"  Profile: {config.profile}")
    click.echo(f"  Languages: {len(config.languages)}")
    for lang in config.languages:
        click.echo(f"    - {lang.name}: {len(lang.metrics)} metrics")
    click.echo(f"  Ignore patterns: {len(config.ignore_patterns)}")


def _validate_layers(config_file: Path | None, directory: Path | None) -> None:
    if config_file is not None:
        warnings = validate_config_file(config_file)
        config = config_from_layer(read_layer(config_file))
        click.echo(f"✅ Configuration file is valid: {config_file}")
    else:
        resolved = resolve_config(root=directory)
        warnings = resolved.warnings
        config = resolved.config
        click.echo("✅ Configuration layers are valid")
        for path in (resolved.paths.user, resolved.paths.project):
            status = "loaded" if path.exists() else "absent (optional)"
            click.echo(f"  {path}: {status}")
    for warning in warnings:
        click.echo(f"Warning: {warning}", err=True)
    _summary(config)


@click.command()
@click.argument(
    "config_file", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=False
)
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Analysis root for resolving project configuration (defaults to cwd)",
)
def validate(config_file: Path | None, directory: Path | None) -> None:
    """Validate CONFIG_FILE, or both active user and project layers when omitted."""
    try:
        _validate_layers(config_file, directory)
    except ValidationError as exc:
        click.echo(
            f"❌ Configuration validation failed: {config_file or 'active layers'}", err=True
        )
        click.echo("\nValidation errors:", err=True)
        for error in exc.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            click.echo(f"  - {loc}: {error['msg']}", err=True)
        raise click.exceptions.Exit(1) from exc
    except Exception as exc:
        raise click.ClickException(f"❌ Error loading configuration: {exc}") from exc
