"""View the effective configuration and its source layers."""

from collections.abc import Callable
from functools import partial
from pathlib import Path

import click
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_layers import resolve_config

from .display_formats import display_json, display_raw, display_summary, display_yaml
from .table_display import display_table


def _report_validation(validate: bool, errors: list[ErrorDetails]) -> None:
    """Optionally emit validation diagnostics."""
    if not (validate and errors):
        return
    click.echo("\n⚠️  Configuration has validation errors:", err=True)
    for err in errors:
        loc = " -> ".join(map(str, err.get("loc", ())))
        click.echo(f"  - {loc}: {err.get('msg', 'Invalid value')}", err=True)


def _ensure_path_exists(
    _ctx: click.Context, _param: click.Parameter, value: Path | None
) -> Path | None:
    if value is not None and not value.exists():
        raise click.ClickException(
            f"Configuration file not found: {value}\n"
            "Run 'antipasta config generate' to create a configuration file."
        )
    return value


def _get_display_handler(
    fmt: str, config: AntipastaConfig, path: Path, is_valid: bool
) -> Callable[[], None]:
    handlers = {
        "summary": partial(display_summary, config, path, is_valid),
        "table": partial(display_table, config),
        "json": partial(display_json, config),
        "yaml": partial(display_yaml, config),
    }
    return handlers[fmt.lower()]


def _display_effective(
    path: Path | None, directory: Path | None, fmt: str, validate: bool, sources: bool
) -> None:
    """Resolve layers and display them without contaminating serialized stdout."""
    try:
        resolved = resolve_config(root=directory, config_path=path)
        config = resolved.config
        for warning in resolved.warnings:
            click.echo(f"Warning: {warning}", err=True)
        if sources:
            _display_sources(resolved.sources)
    except ValidationError as exc:
        _report_validation(validate, exc.errors())
        raise click.ClickException("Effective configuration is invalid") from exc
    label = path or Path("effective configuration")
    _get_display_handler(fmt, config, label, True)()


def _display_sources(sources: dict[str, str]) -> None:
    click.echo("Configuration sources:", err=True)
    for key, source in sorted(sources.items()):
        click.echo(f"  {key}: {source}", err=True)


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(path_type=Path, dir_okay=False, readable=True),
    help="Explicit project configuration file",
    callback=_ensure_path_exists,
)
@click.option(
    "--directory",
    "-d",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Analysis root for resolving project configuration (defaults to cwd)",
)
@click.option(
    "--format",
    "fmt",
    "-f",
    type=click.Choice(["summary", "table", "yaml", "json", "raw"], case_sensitive=False),
    default="yaml",
    show_default=True,
    help="Output format",
)
@click.option("--sources", is_flag=True, help="Show each key's source on stderr")
@click.option("--validate/--no-validate", default=True, show_default=True)
def view(
    path: Path | None, directory: Path | None, fmt: str, validate: bool, sources: bool
) -> None:
    """View the effective merged configuration, or an explicit file's raw YAML."""
    if fmt.lower() == "raw":
        if path is None or sources:
            raise click.UsageError(
                "--format raw requires --path and cannot be combined with --sources"
            )
        display_raw(path)
        return
    try:
        _display_effective(path, directory, fmt, validate, sources)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(f"Error loading configuration: {exc}") from exc
