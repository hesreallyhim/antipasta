"""View configuration command."""

import json
import sys
from pathlib import Path

import click
import yaml
from pydantic import ValidationError

from antipasta.core.config import AntipastaConfig, ComparisonOperator


def format_comparison(op: ComparisonOperator | str) -> str:
    """Format comparison operator for display."""
    mapping = {
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
    return mapping.get(op, str(op))


def display_summary(config: AntipastaConfig, config_path: Path, is_valid: bool) -> None:
    """Display configuration in summary format."""
    click.echo(f"Configuration: {config_path}")
    click.echo(f"Status: {'✅ Valid' if is_valid else '❌ Invalid'}")
    click.echo()

    # Display thresholds
    click.echo("THRESHOLDS")
    click.echo("━" * 50)

    defaults = config.defaults.model_dump()
    threshold_names = {
        "max_cyclomatic_complexity": "Cyclomatic Complexity",
        "max_cognitive_complexity": "Cognitive Complexity",
        "min_maintainability_index": "Maintainability Index",
        "max_halstead_volume": "Halstead Volume",
        "max_halstead_difficulty": "Halstead Difficulty",
        "max_halstead_effort": "Halstead Effort",
    }

    for key, display_name in threshold_names.items():
        if key in defaults:
            value = defaults[key]
            op = "≥" if key.startswith("min_") else "≤"
            click.echo(f"{display_name:<25} {op} {value}")

    click.echo()

    # Display languages
    click.echo("LANGUAGES")
    click.echo("━" * 50)

    if config.languages:
        for lang in config.languages:
            extensions = ", ".join(lang.extensions)
            click.echo(f"{lang.name.capitalize()} ({extensions})")
            enabled_metrics = [m for m in lang.metrics if m.enabled]
            click.echo(f"  ✓ {len(enabled_metrics)} metrics configured")
            click.echo()
    else:
        click.echo("No languages configured")
        click.echo()

    # Display ignore patterns
    if config.ignore_patterns:
        click.echo(f"IGNORE PATTERNS ({len(config.ignore_patterns)})")
        click.echo("━" * 50)
        for pattern in config.ignore_patterns:
            click.echo(f"• {pattern}")
        click.echo()

    click.echo(f"Using .gitignore: {'Yes' if config.use_gitignore else 'No'}")


def display_table(config: AntipastaConfig) -> None:
    """Display configuration in table format."""
    # Create a simple table view
    click.echo("╔" + "═" * 60 + "╗")
    click.echo("║" + " ANTIPASTA CONFIGURATION ".center(60) + "║")
    click.echo("╠" + "═" * 60 + "╣")

    # Default thresholds section
    click.echo("║ DEFAULT THRESHOLDS".ljust(61) + "║")
    click.echo("╟" + "─" * 60 + "╢")

    defaults = config.defaults.model_dump()
    for key, value in defaults.items():
        display_key = key.replace("_", " ").title()
        op = ">=" if key.startswith("min_") else "<="
        line = f"  {display_key:<35} {op} {value:>10.1f}"
        click.echo("║" + line.ljust(60) + "║")

    # Languages section
    if config.languages:
        click.echo("╟" + "─" * 60 + "╢")
        click.echo("║ LANGUAGES".ljust(61) + "║")
        click.echo("╟" + "─" * 60 + "╢")

        for lang in config.languages:
            line = f"  {lang.name}: {len(lang.metrics)} metrics, {len(lang.extensions)} extensions"
            click.echo("║" + line.ljust(60) + "║")

    # Ignore patterns section
    if config.ignore_patterns:
        click.echo("╟" + "─" * 60 + "╢")
        click.echo(f"║ IGNORE PATTERNS ({len(config.ignore_patterns)})".ljust(61) + "║")
        click.echo("╟" + "─" * 60 + "╢")

        for pattern in config.ignore_patterns[:5]:  # Show first 5
            line = f"  {pattern}"
            if len(line) > 60:
                line = line[:57] + "..."
            click.echo("║" + line.ljust(60) + "║")

        if len(config.ignore_patterns) > 5:
            remaining = len(config.ignore_patterns) - 5
            line = f"  ... and {remaining} more"
            click.echo("║" + line.ljust(60) + "║")

    click.echo("╚" + "═" * 60 + "╝")


def display_raw(config_path: Path) -> None:
    """Display raw configuration file content."""
    with open(config_path) as f:
        content = f.read()
    click.echo(content)


def display_json(config: AntipastaConfig) -> None:
    """Display configuration in JSON format."""
    data = config.model_dump(exclude_none=True, mode="json")
    click.echo(json.dumps(data, indent=2))


def display_yaml(config: AntipastaConfig) -> None:
    """Display configuration in YAML format."""
    data = config.model_dump(exclude_none=True, mode="json")
    click.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(path_type=Path),
    default=".antipasta.yaml",
    help="Path to configuration file",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["summary", "table", "yaml", "json", "raw"]),
    default="summary",
    help="Output format",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate configuration (default: true)",
)
def view(path: Path, format: str, validate: bool) -> None:
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
        # Check if file exists
        if not path.exists():
            click.echo(f"❌ Configuration file not found: {path}", err=True)
            click.echo("Run 'antipasta config generate' to create a configuration file.", err=True)
            sys.exit(1)

        # For raw format, just display the file
        if format == "raw":
            display_raw(path)
            return

        # Load and optionally validate the configuration
        is_valid = True
        config = None
        validation_errors = []

        try:
            config = AntipastaConfig.from_yaml(path)
        except ValidationError as e:
            is_valid = False
            config = AntipastaConfig()  # Use defaults for display
            validation_errors = e.errors()
        except Exception as e:
            click.echo(f"❌ Error loading configuration: {e}", err=True)
            sys.exit(1)

        # Display in requested format
        if format == "summary":
            display_summary(config, path, is_valid)
            if not is_valid and validate:
                click.echo()
                click.echo("⚠️  Configuration has validation errors:", err=True)
                for error in validation_errors:
                    loc = " -> ".join(str(x) for x in error["loc"])
                    click.echo(f"  - {loc}: {error['msg']}", err=True)
        elif format == "table":
            display_table(config)
        elif format == "json":
            display_json(config)
        elif format == "yaml":
            display_yaml(config)

    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)
