"""Project configuration collection utilities."""

from typing import Any

import click


def collect_project_settings() -> dict[str, Any]:
    """Collect project settings including gitignore and ignore patterns.

    Returns:
        Dictionary with project settings.
    """
    settings: dict[str, Any] = {}

    click.echo("\nProject settings:")
    click.echo("-" * 40)

    # Gitignore setting
    settings["use_gitignore"] = click.confirm(
        "Use .gitignore file for excluding files?",
        default=True,
    )

    # Collect ignore patterns
    settings["ignore_patterns"] = collect_ignore_patterns()

    return settings


def collect_ignore_patterns() -> list[str]:
    """Collect file patterns to ignore during analysis.

    Returns:
        List of ignore patterns.
    """
    click.echo("\nFile patterns to ignore during analysis:")
    click.echo("-" * 40)

    ignore_patterns = []

    # Ask about default test patterns
    if click.confirm(
        "Include default test file patterns? (**/test_*.py, **/*_test.py, **/tests/**)",
        default=True,
    ):
        ignore_patterns = ["**/test_*.py", "**/*_test.py", "**/tests/**"]
        click.echo("  ✓ Added default test patterns")

    # Collect additional patterns
    additional_patterns = collect_additional_patterns()
    ignore_patterns.extend(additional_patterns)

    if not ignore_patterns:
        click.echo("  ℹ️  No ignore patterns configured")
    else:
        click.echo(f"\n  Total patterns to ignore: {len(ignore_patterns)}")

    return ignore_patterns


def collect_additional_patterns() -> list[str]:
    """Collect additional ignore patterns from user input.

    Returns:
        List of additional patterns.
    """
    patterns = []

    click.echo(
        "\nEnter additional patterns to ignore (one per line, press Enter with no input to finish):"
    )

    while True:
        try:
            pattern = click.prompt(
                "Pattern (or press Enter to continue)",
                default="",
                show_default=False,
            )
            if not pattern:
                break
            patterns.append(pattern.strip())
            click.echo(f"  ✓ Added: {pattern.strip()}")
        except (EOFError, click.Abort):
            # Handle end of input or interruption
            break

    return patterns
