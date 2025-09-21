"""Configuration generation command for antipasta."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from antipasta.core.config import AntipastaConfig


def validate_positive_int(value: str, min_val: int = 1, max_val: int | None = None) -> int:
    """Validate a positive integer within optional range."""
    try:
        num = int(value)
        if num < min_val:
            raise click.BadParameter(f"Value must be at least {min_val}")
        if max_val is not None and num > max_val:
            raise click.BadParameter(f"Value must be at most {max_val}")
        return num
    except ValueError as e:
        raise click.BadParameter("Must be a valid integer") from e


def validate_positive_float(
    value: str, min_val: float = 0.0, max_val: float | None = None
) -> float:
    """Validate a positive float within optional range."""
    try:
        num = float(value)
        if num < min_val:
            raise click.BadParameter(f"Value must be at least {min_val}")
        if max_val is not None and num > max_val:
            raise click.BadParameter(f"Value must be at most {max_val}")
        return num
    except ValueError as e:
        raise click.BadParameter("Must be a valid number") from e


def prompt_with_validation(
    prompt_text: str,
    default: Any,
    validator: Callable[[str], Any],
    help_text: str = "",
) -> Any:
    """Prompt with validation and re-prompt on invalid input."""
    if help_text:
        click.echo(f"  {help_text}")

    while True:
        try:
            value = click.prompt(prompt_text, default=default, show_default=True)
            return validator(str(value))
        except click.BadParameter as e:
            click.echo(f"  ❌ Invalid input: {e}", err=True)
            click.echo("  Please try again.", err=True)


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=".antipasta.yaml",
    help="Output file path",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Generate with defaults without prompting",
)
def generate_config(output: Path, non_interactive: bool) -> None:
    """Generate an antipasta configuration file.

    Creates a configuration file with sensible defaults. In interactive mode,
    prompts for customization of thresholds and settings.
    """
    if non_interactive:
        # Generate with defaults
        config = AntipastaConfig.generate_default()
        _save_config(config, output, force=True)
        return

    # Interactive mode
    click.echo("\nWelcome to antipasta configuration generator!")
    click.echo("=" * 50)
    click.echo("\nThis wizard will help you create a configuration file with")
    click.echo("code quality thresholds tailored to your project.")
    click.echo("\nFor each metric, you'll see the valid range and recommended value.")
    click.echo("Press Ctrl+C at any time to cancel.")

    # Start with defaults
    config_dict: dict[str, Any] = {}

    # Get basic complexity thresholds
    click.echo("\nLet's set up your code quality thresholds:")
    click.echo("-" * 40)

    max_cyclomatic = prompt_with_validation(
        "Maximum cyclomatic complexity per function",
        default=10,
        validator=lambda v: validate_positive_int(v, min_val=1, max_val=50),
        help_text="ℹ️  Range: 1-50 (lower is stricter). Recommended: 10",
    )

    max_cognitive = prompt_with_validation(
        "Maximum cognitive complexity per function",
        default=15,
        validator=lambda v: validate_positive_int(v, min_val=1, max_val=100),
        help_text="ℹ️  Range: 1-100 (lower is stricter). Recommended: 15",
    )

    min_maintainability = prompt_with_validation(
        "Minimum maintainability index",
        default=50,
        validator=lambda v: validate_positive_int(v, min_val=0, max_val=100),
        help_text="ℹ️  Range: 0-100 (higher is stricter). Recommended: 50",
    )

    # Ask about advanced metrics
    advanced = click.confirm(
        "\nWould you like to configure advanced Halstead metrics?",
        default=False,
    )

    defaults_dict = {
        "max_cyclomatic_complexity": max_cyclomatic,
        "max_cognitive_complexity": max_cognitive,
        "min_maintainability_index": min_maintainability,
    }

    if advanced:
        click.echo("\nAdvanced Halstead metrics:")
        click.echo("-" * 40)

        defaults_dict["max_halstead_volume"] = prompt_with_validation(
            "Maximum Halstead volume",
            default=1000,
            validator=lambda v: validate_positive_float(v, min_val=1, max_val=100000),
            help_text="ℹ️  Range: 1-100000. Measures program size. Recommended: 1000",
        )

        defaults_dict["max_halstead_difficulty"] = prompt_with_validation(
            "Maximum Halstead difficulty",
            default=10,
            validator=lambda v: validate_positive_float(v, min_val=0.1, max_val=100),
            help_text="ℹ️  Range: 0.1-100. Measures error proneness. Recommended: 10",
        )

        defaults_dict["max_halstead_effort"] = prompt_with_validation(
            "Maximum Halstead effort",
            default=10000,
            validator=lambda v: validate_positive_float(v, min_val=1, max_val=1000000),
            help_text="ℹ️  Range: 1-1000000. Measures implementation time. Recommended: 10000",
        )
    else:
        # Use defaults for advanced metrics
        defaults_dict["max_halstead_volume"] = 1000
        defaults_dict["max_halstead_difficulty"] = 10
        defaults_dict["max_halstead_effort"] = 10000

    config_dict["defaults"] = defaults_dict

    # Language configuration
    click.echo("\nWhich languages would you like to analyze?")
    click.echo("-" * 40)

    languages = []

    # Python is selected by default
    include_python = click.confirm("[x] Python", default=True)
    if include_python:
        languages.append(_create_python_config(defaults_dict))

    include_js = click.confirm("[ ] JavaScript/TypeScript", default=False)
    if include_js:
        languages.append(_create_javascript_config(defaults_dict))

    config_dict["languages"] = languages

    # Project settings
    click.echo("\nProject settings:")
    click.echo("-" * 40)

    use_gitignore = click.confirm(
        "Use .gitignore file for excluding files?",
        default=True,
    )
    config_dict["use_gitignore"] = use_gitignore

    # Ignore patterns
    click.echo("\nFile patterns to ignore during analysis:")
    click.echo("-" * 40)

    # Ask if user wants to use default test patterns
    use_test_defaults = click.confirm(
        "Include default test file patterns? (**/test_*.py, **/*_test.py, **/tests/**)",
        default=True,
    )

    ignore_patterns = []
    if use_test_defaults:
        ignore_patterns = ["**/test_*.py", "**/*_test.py", "**/tests/**"]
        click.echo("  ✓ Added default test patterns")

    # Collect additional patterns one at a time
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
            ignore_patterns.append(pattern.strip())
            click.echo(f"  ✓ Added: {pattern.strip()}")
        except (EOFError, click.Abort):
            # Handle end of input or interruption
            break

    if not ignore_patterns:
        click.echo("  ℹ️  No ignore patterns configured")
    else:
        click.echo(f"\n  Total patterns to ignore: {len(ignore_patterns)}")

    config_dict["ignore_patterns"] = ignore_patterns

    # Create the configuration object with error handling
    try:
        config = AntipastaConfig(**config_dict)
    except ValidationError as e:
        click.echo("\n❌ Configuration validation failed:", err=True)
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            click.echo(f"  - {loc}: {error['msg']}", err=True)
        click.echo("\nPlease run the command again with valid values.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error creating configuration: {e}", err=True)
        sys.exit(1)

    # Save configuration
    click.echo(f"\nConfiguration will be saved to: {output}")

    # Check if file exists
    if output.exists() and not click.confirm("File already exists. Overwrite?", default=False):
        click.echo("Aborted.")
        sys.exit(0)

    _save_config(config, output, force=False)


def _create_python_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create Python language configuration."""
    metrics = []

    # Cyclomatic complexity
    metrics.append(
        {
            "type": "cyclomatic_complexity",
            "threshold": defaults["max_cyclomatic_complexity"],
            "comparison": "<=",
        }
    )

    # Cognitive complexity
    metrics.append(
        {
            "type": "cognitive_complexity",
            "threshold": defaults["max_cognitive_complexity"],
            "comparison": "<=",
        }
    )

    # Maintainability index
    metrics.append(
        {
            "type": "maintainability_index",
            "threshold": defaults["min_maintainability_index"],
            "comparison": ">=",
        }
    )

    # Halstead metrics
    metrics.append(
        {
            "type": "halstead_volume",
            "threshold": defaults["max_halstead_volume"],
            "comparison": "<=",
        }
    )

    metrics.append(
        {
            "type": "halstead_difficulty",
            "threshold": defaults["max_halstead_difficulty"],
            "comparison": "<=",
        }
    )

    metrics.append(
        {
            "type": "halstead_effort",
            "threshold": defaults["max_halstead_effort"],
            "comparison": "<=",
        }
    )

    return {
        "name": "python",
        "extensions": [".py"],
        "metrics": metrics,
    }


def _create_javascript_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create JavaScript/TypeScript language configuration."""
    # For JS/TS, we only support cyclomatic and cognitive complexity currently
    metrics = []

    metrics.append(
        {
            "type": "cyclomatic_complexity",
            "threshold": defaults["max_cyclomatic_complexity"],
            "comparison": "<=",
        }
    )

    metrics.append(
        {
            "type": "cognitive_complexity",
            "threshold": defaults["max_cognitive_complexity"],
            "comparison": "<=",
        }
    )

    return {
        "name": "javascript",
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "metrics": metrics,
    }


def _save_config(config: AntipastaConfig, output: Path, force: bool = False) -> None:
    """Save configuration to file with helpful comments."""
    # Convert to dict for customization
    data = config.model_dump(exclude_none=True, mode="json")

    # Create YAML content with comments
    yaml_lines = []
    yaml_lines.append("# antipasta configuration file")
    yaml_lines.append("# Generated by: antipasta generate-config")
    yaml_lines.append("")
    yaml_lines.append("# Default thresholds for all languages")
    yaml_lines.append("defaults:")

    defaults = data.get("defaults", {})
    cyclo_max = defaults.get("max_cyclomatic_complexity", 10)
    cog_max = defaults.get("max_cognitive_complexity", 15)
    maint_min = defaults.get("min_maintainability_index", 50)
    yaml_lines.append(f"  max_cyclomatic_complexity: {cyclo_max}")
    yaml_lines.append(f"  max_cognitive_complexity: {cog_max}")
    yaml_lines.append(f"  min_maintainability_index: {maint_min}")
    yaml_lines.append("  # Halstead metrics (advanced)")
    yaml_lines.append(f"  max_halstead_volume: {defaults.get('max_halstead_volume', 1000)}")
    yaml_lines.append(f"  max_halstead_difficulty: {defaults.get('max_halstead_difficulty', 10)}")
    yaml_lines.append(f"  max_halstead_effort: {defaults.get('max_halstead_effort', 10000)}")

    yaml_lines.append("")
    yaml_lines.append("# Language-specific configurations")
    yaml_lines.append("languages:")

    for lang in data.get("languages", []):
        yaml_lines.append(f"  - name: {lang['name']}")
        if lang.get("extensions"):
            yaml_lines.append("    extensions:")
            for ext in lang["extensions"]:
                yaml_lines.append(f"      - {ext}")
        yaml_lines.append("    metrics:")
        for metric in lang.get("metrics", []):
            yaml_lines.append(f"      - type: {metric['type']}")
            yaml_lines.append(f"        threshold: {metric['threshold']}")
            yaml_lines.append(f"        comparison: \"{metric['comparison']}\"")
            if metric != lang["metrics"][-1]:  # Not the last metric
                yaml_lines.append("")

    yaml_lines.append("")
    yaml_lines.append("# Files and patterns to ignore during analysis")
    patterns = data.get("ignore_patterns", [])
    if patterns:
        yaml_lines.append("ignore_patterns:")
        for pattern in patterns:
            yaml_lines.append(f'  - "{pattern}"')
    else:
        yaml_lines.append("ignore_patterns: []")

    yaml_lines.append("")
    yaml_lines.append("# Whether to use .gitignore file for excluding files")
    yaml_lines.append(f"use_gitignore: {str(data.get('use_gitignore', True)).lower()}")

    # Write file
    try:
        with open(output, "w") as f:
            f.write("\n".join(yaml_lines) + "\n")

        click.echo(f"✅ Configuration saved to {output}")
        click.echo(f"\nRun 'antipasta validate-config {output}' to verify.")
        click.echo("Run 'antipasta metrics' to start analyzing your code!")

    except Exception as e:
        click.echo(f"❌ Error saving configuration: {e}", err=True)
        sys.exit(1)
