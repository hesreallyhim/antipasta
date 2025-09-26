"""Various display formats for antipasta configuration."""

import json
from pathlib import Path

import click
import yaml

from antipasta.core.config import AntipastaConfig

# Threshold display names
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
