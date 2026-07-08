"""Language configuration utilities for config generation."""

from typing import Any

import click


def collect_language_config(defaults_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect language configuration interactively.

    Args:
        defaults_dict: Dictionary containing threshold defaults.

    Returns:
        List of language configuration dictionaries.
    """
    click.echo("\nWhich languages would you like to analyze?")
    click.echo("-" * 40)

    languages = []

    # Python is selected by default
    if click.confirm("[x] Python", default=True):
        languages.append(create_python_config(defaults_dict))

    if click.confirm("[ ] JavaScript", default=False):
        languages.append(create_javascript_config(defaults_dict))

    if click.confirm("[ ] TypeScript", default=False):
        languages.append(create_typescript_config(defaults_dict))

    return languages


def create_python_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create Python language configuration."""
    metrics = [
        {
            "type": "cyclomatic_complexity",
            "threshold": defaults["max_cyclomatic_complexity"],
            "comparison": "<=",
        },
        {
            "type": "cognitive_complexity",
            "threshold": defaults["max_cognitive_complexity"],
            "comparison": "<=",
        },
        {
            "type": "maintainability_index",
            "threshold": defaults["min_maintainability_index"],
            "comparison": ">=",
        },
        {
            "type": "halstead_volume",
            "threshold": defaults["max_halstead_volume"],
            "comparison": "<=",
        },
        {
            "type": "halstead_difficulty",
            "threshold": defaults["max_halstead_difficulty"],
            "comparison": "<=",
        },
        {
            "type": "halstead_effort",
            "threshold": defaults["max_halstead_effort"],
            "comparison": "<=",
        },
    ]

    return {
        "name": "python",
        "extensions": [".py"],
        "metrics": metrics,
    }


def create_javascript_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create JavaScript language configuration."""

    return {
        "name": "javascript",
        "extensions": [".js", ".mjs", ".cjs", ".jsx"],
        "metrics": [_cyclomatic_metric(defaults)],
    }


def create_typescript_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create TypeScript language configuration."""
    return {
        "name": "typescript",
        "extensions": [".ts", ".tsx", ".mts", ".cts"],
        "metrics": [_cyclomatic_metric(defaults)],
    }


def _cyclomatic_metric(defaults: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "cyclomatic_complexity",
        "threshold": defaults["max_cyclomatic_complexity"],
        "comparison": "<=",
    }
