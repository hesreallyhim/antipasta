"""View configuration command."""

from collections.abc import Callable
from functools import partial
import json
from pathlib import Path
import sys

import click
from pydantic import ValidationError
from pydantic_core import ErrorDetails
import yaml

from antipasta.core.config import AntipastaConfig

# Table formatting constants
_TABLE_WIDTH = 60
_THRESHOLD_NAMES = {
    "max_cyclomatic_complexity": "Cyclomatic Complexity",
    "max_cognitive_complexity": "Cognitive Complexity",
    "min_maintainability_index": "Maintainability Index",
    "max_halstead_volume": "Halstead Volume",
    "max_halstead_difficulty": "Halstead Difficulty",
    "max_halstead_effort": "Halstead Effort",
}


def _display_header(config_path: Path, is_valid: bool) -> None:
    """Display configuration header with path and validation status."""
    click.echo(f"Configuration: {config_path}")
    click.echo(f"Status: {'✅ Valid' if is_valid else '❌ Invalid'}")
    click.echo()


def _get_threshold_operator(key: str) -> str:
    """Get the comparison operator for a threshold key."""
    return "≥" if key.startswith("min_") else "≤"

def _display_thresholds(config: AntipastaConfig) -> None:
    """Display threshold settings."""
    click.echo("THRESHOLDS")
    click.echo("━" * 50)

    defaults = config.defaults.model_dump()
    for key, display_name in _THRESHOLD_NAMES.items():
        if key not in defaults:
            continue
        op = _get_threshold_operator(key)
        click.echo(f"{display_name:<25} {op} {defaults[key]}")

    click.echo()


def _display_languages(config: AntipastaConfig) -> None:
    """Display language configurations."""
    click.echo("LANGUAGES")
    click.echo("━" * 50)
    if not config.languages:
        click.echo("No languages configured")
        click.echo()
        return
    for lang in config.languages:
        extensions = ", ".join(lang.extensions)
        click.echo(f"{lang.name.capitalize()} ({extensions})")
        enabled = sum(1 for m in lang.metrics if m.enabled)
        click.echo(f"  ✓ {enabled} metrics configured")
        click.echo()


def _display_ignore_patterns(config: AntipastaConfig) -> None:
    """Display ignore patterns if configured."""
    if not config.ignore_patterns:
        return
    click.echo(f"IGNORE PATTERNS ({len(config.ignore_patterns)})")
    click.echo("━" * 50)
    for pattern in config.ignore_patterns:
        click.echo(f"• {pattern}")
    click.echo()


def display_summary(config: AntipastaConfig, config_path: Path, is_valid: bool) -> None:
    """Display configuration in summary format."""
    _display_header(config_path, is_valid)
    _display_thresholds(config)
    _display_languages(config)
    _display_ignore_patterns(config)
    click.echo(f"Using .gitignore: {'Yes' if config.use_gitignore else 'No'}")


def _create_box_renderer(width: int) -> Callable[[str, str], str]:
    """Create a box rendering function with fixed width."""
    def box(border: str, text: str = "") -> str:
        if text:
            return "║" + text.ljust(width) + "║"
        return border[0] + border[1] * width + border[2]
    return box


def _render_table_header(box: Callable[[str, str], str], width: int) -> None:
    """Render the table header section."""
    click.echo(box("╔═╗", ""))
    click.echo(box("", " ANTIPASTA CONFIGURATION ".center(width)))
    click.echo(box("╠═╣", ""))


def _render_thresholds_section(box: Callable[[str, str], str], config: AntipastaConfig) -> None:
    """Render the thresholds section of the table."""
    click.echo(box("", " DEFAULT THRESHOLDS"))
    click.echo(box("╟─╢", ""))

    for key, value in config.defaults.model_dump().items():
        display_key = key.replace("_", " ").title()
        op = ">=" if key.startswith("min_") else "<="
        click.echo(box("", f"  {display_key:<35} {op} {value:>10.1f}"))


def _render_languages_section(box: Callable[[str, str], str], languages: list) -> None:
    """Render the languages section if languages are configured."""
    if not languages:
        return

    click.echo(box("╟─╢", ""))
    click.echo(box("", " LANGUAGES"))
    click.echo(box("╟─╢", ""))

    for lang in languages:
        text = f"  {lang.name}: {len(lang.metrics)} metrics, {len(lang.extensions)} extensions"
        click.echo(box("", text))


def _truncate_text(text: str, max_width: int) -> str:
    """Truncate text if it exceeds max width."""
    if len(text) <= max_width:
        return text
    return text[:max_width - 3] + "..."


def _render_ignore_patterns_section(box: Callable[[str, str], str], patterns: list, width: int) -> None:
    """Render the ignore patterns section if patterns are configured."""
    if not patterns:
        return

    click.echo(box("╟─╢", ""))
    click.echo(box("", f" IGNORE PATTERNS ({len(patterns)})"))
    click.echo(box("╟─╢", ""))

    # Display first 5 patterns
    display_limit = 5
    for pattern in patterns[:display_limit]:
        text = _truncate_text(f"  {pattern}", width)
        click.echo(box("", text))

    # Show count of remaining patterns
    remaining = len(patterns) - display_limit
    if remaining > 0:
        click.echo(box("", f"  ... and {remaining} more"))


def display_table(config: AntipastaConfig) -> None:
    """Display configuration in table format."""
    width = _TABLE_WIDTH
    box = _create_box_renderer(width)

    _render_table_header(box, width)
    _render_thresholds_section(box, config)
    _render_languages_section(box, config.languages)
    _render_ignore_patterns_section(box, config.ignore_patterns, width)

    click.echo(box("╚═╝", ""))


def display_raw(config_path: Path) -> None:
    """Display raw configuration file content."""
    click.echo(Path(config_path).read_text(encoding="utf-8"))


def display_json(config: AntipastaConfig) -> None:
    """Display configuration in JSON format."""
    data = config.model_dump(exclude_none=True, mode="json")
    click.echo(json.dumps(data, indent=2))


def display_yaml(config: AntipastaConfig) -> None:
    """Display configuration in YAML format."""
    data = config.model_dump(exclude_none=True, mode="json")
    click.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))


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
