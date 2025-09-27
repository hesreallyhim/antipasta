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

    # JavaScript/TypeScript support coming soon
    click.echo("[ ] JavaScript/TypeScript (coming soon)")

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
    """Create JavaScript/TypeScript language configuration.

    Note: This function is ready for when JavaScript/TypeScript support is added.
    Currently not used but kept for future implementation.
    """
    # For JS/TS, we only support cyclomatic and cognitive complexity currently
    metrics: list[dict[str, Any]] = []

    metrics.extend(
        (
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
        )
    )

    return {
        "name": "javascript",
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "metrics": metrics,
    }
