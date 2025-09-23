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

from antipasta.core.config import AntipastaConfig, ComparisonOperator

# ---------- Pure formatting helpers ----------

_COMPARISON_SYMBOLS = {
    ComparisonOperator.LE: "≤",
    ComparisonOperator.LT: "<",
    ComparisonOperator.GE: "≥",
    ComparisonOperator.GT: ">",
    ComparisonOperator.EQ: "=",
    ComparisonOperator.NE: "≠",
    "<=": "≤",
    "<": "<",
    ">=": "≥",
    ">": ">",
    "==": "=",
    "!=": "≠",
}


def format_comparison(op: ComparisonOperator | str) -> str:
    """Format comparison operator for display."""
    return _COMPARISON_SYMBOLS.get(op, str(op))


# ---------- Display helpers ----------

def display_summary(config: AntipastaConfig, config_path: Path, is_valid: bool) -> None:
    """Display configuration in summary format."""
    click.echo(f"Configuration: {config_path}")
    click.echo(f"Status: {'✅ Valid' if is_valid else '❌ Invalid'}")
    click.echo()

    # Thresholds
    click.echo("THRESHOLDS")
    click.echo("━" * 50)
    defaults = config.defaults.model_dump()
    names = {
        "max_cyclomatic_complexity": "Cyclomatic Complexity",
        "max_cognitive_complexity": "Cognitive Complexity",
        "min_maintainability_index": "Maintainability Index",
        "max_halstead_volume": "Halstead Volume",
        "max_halstead_difficulty": "Halstead Difficulty",
        "max_halstead_effort": "Halstead Effort",
    }
    for key, display_name in names.items():
        if key in defaults:
            value = defaults[key]
            op = "≥" if key.startswith("min_") else "≤"
            click.echo(f"{display_name:<25} {op} {value}")
    click.echo()

    # Languages
    click.echo("LANGUAGES")
    click.echo("━" * 50)
    if config.languages:
        for lang in config.languages:
            extensions = ", ".join(lang.extensions)
            click.echo(f"{lang.name.capitalize()} ({extensions})")
            enabled = sum(1 for m in lang.metrics if m.enabled)
            click.echo(f"  ✓ {enabled} metrics configured")
            click.echo()
    else:
        click.echo("No languages configured")
        click.echo()

    # Ignore patterns
    if config.ignore_patterns:
        click.echo(f"IGNORE PATTERNS ({len(config.ignore_patterns)})")
        click.echo("━" * 50)
        for pattern in config.ignore_patterns:
            click.echo(f"• {pattern}")
        click.echo()

    click.echo(f"Using .gitignore: {'Yes' if config.use_gitignore else 'No'}")


def display_table(config: AntipastaConfig) -> None:
    """Display configuration in table format."""
    click.echo("╔" + "═" * 60 + "╗")
    click.echo("║" + " ANTIPASTA CONFIGURATION ".center(60) + "║")
    click.echo("╠" + "═" * 60 + "╣")

    # Default thresholds
    click.echo("║ DEFAULT THRESHOLDS".ljust(61) + "║")
    click.echo("╟" + "─" * 60 + "╢")
    defaults = config.defaults.model_dump()
    for key, value in defaults.items():
        display_key = key.replace("_", " ").title()
        op = ">=" if key.startswith("min_") else "<="
        line = f"  {display_key:<35} {op} {value:>10.1f}"
        click.echo("║" + line.ljust(60) + "║")

    # Languages
    if config.languages:
        click.echo("╟" + "─" * 60 + "╢")
        click.echo("║ LANGUAGES".ljust(61) + "║")
        click.echo("╟" + "─" * 60 + "╢")
        for lang in config.languages:
            line = f"  {lang.name}: {len(lang.metrics)} metrics, {len(lang.extensions)} extensions"
            click.echo("║" + line.ljust(60) + "║")

    # Ignore patterns
    if config.ignore_patterns:
        click.echo("╟" + "─" * 60 + "╢")
        click.echo(f"║ IGNORE PATTERNS ({len(config.ignore_patterns)})".ljust(61) + "║")
        click.echo("╟" + "─" * 60 + "╢")
        for pattern in config.ignore_patterns[:5]:
            line = f"  {pattern}"
            click.echo("║" + (line if len(line) <= 60 else line[:57] + "...").ljust(60) + "║")
        if len(config.ignore_patterns) > 5:
            remaining = len(config.ignore_patterns) - 5
            click.echo("║" + f"  ... and {remaining} more".ljust(60) + "║")

    click.echo("╚" + "═" * 60 + "╝")


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


# ---------- Load/validation helpers ----------

def _load_config_or_defaults(path: Path) -> tuple[AntipastaConfig, bool, list[ErrorDetails]]:
    """Return (config, is_valid, errors)."""
    try:
        cfg = AntipastaConfig.from_yaml(path)
        return cfg, True, []
    except ValidationError as e:
        # Use defaults for display, but preserve errors for optional reporting
        return AntipastaConfig(), False, e.errors()
    except Exception as e:  # unexpected I/O/parse errors
        raise click.ClickException(f"Error loading configuration: {e}") from e


def _report_validation(validate: bool, is_valid: bool, errors: list[ErrorDetails]) -> None:
    """Optionally emit validation diagnostics."""
    if not (validate and not is_valid):
        return
    click.echo()
    click.echo("⚠️  Configuration has validation errors:", err=True)
    for err in errors:
        loc = " -> ".join(map(str, err.get("loc", ())))
        msg = err.get("msg", "Invalid value")
        click.echo(f"  - {loc}: {msg}", err=True)


def _ensure_path_exists(_ctx: click.Context, _param: click.Parameter, value: Path) -> Path:
    if not Path(value).exists():
        # ClickException -> exit code 1, preserves your message
        raise click.ClickException(
            f"Configuration file not found: {value}\n"
            "Run 'antipasta config generate' to create a configuration file."
        )
    return value


# ---------- CLI entrypoint ----------

@click.command()
@click.option(
    "--path", "-p",
    type=click.Path(path_type=Path, dir_okay=False, readable=True),
    default=Path(".antipasta.yaml"),
    show_default=True,
    help="Path to configuration file",
    callback=_ensure_path_exists,   # <-- ensures exit_code=1 + your message
)
@click.option(
    "--format", "fmt", "-f",
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

        dispatch: dict[str, Callable[[], None]] = {
            "summary": partial(display_summary, config, path, is_valid),
            "table": partial(display_table, config),
            "json": partial(display_json, config),
            "yaml": partial(display_yaml, config),
        }
        handler = dispatch.get(fmt.lower())
        if not handler:
            raise click.ClickException(f"Unknown format: {fmt}")
        handler()

        _report_validation(validate, is_valid, errors)

    except click.ClickException as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)
