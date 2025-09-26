"""View configuration command main entry point."""

from collections.abc import Callable
from functools import partial
from pathlib import Path
import sys

import click
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from antipasta.core.config import AntipastaConfig

from .display_formats import display_json, display_raw, display_summary, display_yaml
from .table_display import display_table


def _load_config_or_defaults(path: Path) -> tuple[AntipastaConfig, bool, list[ErrorDetails]]:
    """Return (config, is_valid, errors)."""
    try:
        cfg = AntipastaConfig.from_yaml(path)
        return cfg, True, []
    except ValidationError as e:
        return AntipastaConfig(), False, e.errors()
    except Exception as e:
        raise click.ClickException(f"Error loading configuration: {e}") from e


def _report_validation(validate: bool, is_valid: bool, errors: list[ErrorDetails]) -> None:
    """Optionally emit validation diagnostics."""
    if not (validate and not is_valid):
        return
    click.echo("\n⚠️  Configuration has validation errors:", err=True)
    for err in errors:
        loc = " -> ".join(map(str, err.get("loc", ())))
        click.echo(f"  - {loc}: {err.get('msg', 'Invalid value')}", err=True)


def _ensure_path_exists(_ctx: click.Context, _param: click.Parameter, value: Path) -> Path:
    if not Path(value).exists():
        raise click.ClickException(
            f"Configuration file not found: {value}\n"
            "Run 'antipasta config generate' to create a configuration file."
        )
    return value


def _get_display_handler(
    fmt: str, config: AntipastaConfig, path: Path, is_valid: bool
) -> Callable[[], None]:
    """Get the appropriate display handler for the format."""
    handlers = {
        "summary": partial(display_summary, config, path, is_valid),
        "table": partial(display_table, config),
        "json": partial(display_json, config),
        "yaml": partial(display_yaml, config),
    }
    if fmt.lower() not in handlers:
        raise click.ClickException(f"Unknown format: {fmt}")
    return handlers[fmt.lower()]


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(path_type=Path, dir_okay=False, readable=True),
    default=Path(".antipasta.yaml"),
    show_default=True,
    help="Path to configuration file",
    callback=_ensure_path_exists,
)
@click.option(
    "--format",
    "fmt",
    "-f",
    type=click.Choice(["summary", "table", "yaml", "json", "raw"], case_sensitive=False),
    default="summary",
    show_default=True,
    help="Output format",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    show_default=True,
    help="Validate configuration (default: true)",
)
def view(path: Path, fmt: str, validate: bool) -> None:
    """View antipasta configuration.

    Displays the current configuration in various formats.

    Examples:

    \b
    # View configuration summary
    antipasta config view

    \b
    # View raw YAML content
    antipasta config view --format raw

    \b
    # View as JSON
    antipasta config view --format json

    \b
    # View specific config file
    antipasta config view --path custom-config.yaml
    """
    try:
        if fmt.lower() == "raw":
            display_raw(path)
            return

        config, is_valid, errors = _load_config_or_defaults(path)
        handler = _get_display_handler(fmt, config, path, is_valid)
        handler()
        _report_validation(validate, is_valid, errors)

    except click.ClickException as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)
