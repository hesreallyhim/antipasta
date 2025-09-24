"""Configuration generation command for antipasta - REFACTORED VERSION."""

from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any

import click
from pydantic import ValidationError

from antipasta.cli.validation_utils import get_metric_constraints
from antipasta.core.config import AntipastaConfig
from antipasta.core.metric_models import MetricThresholds


def validate_with_pydantic(metric_type: str, value: str) -> float:
    """Validate a metric value using Pydantic model.

    Args:
        metric_type: The metric type being validated
        value: String value to validate

    Returns:
        Validated numeric value

    Raises:
        click.BadParameter: If validation fails
    """
    try:
        num = float(value)
        # Use Pydantic validation
        MetricThresholds(**{metric_type: num})  # type: ignore[arg-type]
        return num
    except ValidationError as e:
        # Extract first error message
        if e.errors():
            err = e.errors()[0]
            err_type = err.get("type", "")
            ctx = err.get("ctx", {})

            if "greater_than_equal" in err_type:
                raise click.BadParameter(f"Value must be >= {ctx.get('ge', 0)}") from e
            if "less_than_equal" in err_type:
                raise click.BadParameter(f"Value must be <= {ctx.get('le', 'max')}") from e
            if err_type == "int_type":
                raise click.BadParameter("Must be an integer") from e

        raise click.BadParameter(str(e)) from e
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


def _show_welcome_message() -> None:
    """Display welcome message for interactive configuration."""
    click.echo("\nWelcome to antipasta configuration generator!")
    click.echo("=" * 50)
    click.echo("\nThis wizard will help you create a configuration file with")
    click.echo("code quality thresholds tailored to your project.")
    click.echo("\nFor each metric, you'll see the valid range and recommended value.")
    click.echo("Press Ctrl+C at any time to cancel.")


def _collect_basic_thresholds() -> dict[str, float]:
    """Collect basic complexity thresholds interactively.

    Returns:
        Dictionary containing cyclomatic, cognitive, and maintainability thresholds.
    """
    click.echo("\nLet's set up your code quality thresholds:")
    click.echo("-" * 40)

    thresholds = {}

    # Cyclomatic complexity
    cc_min, cc_max = get_metric_constraints("cyclomatic_complexity")
    thresholds["max_cyclomatic_complexity"] = prompt_with_validation(
        "Maximum cyclomatic complexity per function",
        default=10,
        validator=lambda v: validate_with_pydantic("cyclomatic_complexity", v),
        help_text=f"ℹ️  Range: {cc_min}-{cc_max} (lower is stricter). Recommended: 10",
    )

    # Cognitive complexity
    cog_min, cog_max = get_metric_constraints("cognitive_complexity")
    thresholds["max_cognitive_complexity"] = prompt_with_validation(
        "Maximum cognitive complexity per function",
        default=15,
        validator=lambda v: validate_with_pydantic("cognitive_complexity", v),
        help_text=f"ℹ️  Range: {cog_min}-{cog_max} (lower is stricter). Recommended: 15",
    )

    # Maintainability index
    mi_min, mi_max = get_metric_constraints("maintainability_index")
    thresholds["min_maintainability_index"] = prompt_with_validation(
        "Minimum maintainability index",
        default=50,
        validator=lambda v: validate_with_pydantic("maintainability_index", v),
        help_text=f"ℹ️  Range: {mi_min}-{mi_max} (higher is stricter). Recommended: 50",
    )

    return thresholds


def _collect_halstead_thresholds() -> dict[str, float]:
    """Collect advanced Halstead metrics thresholds.

    Returns:
        Dictionary containing Halstead volume, difficulty, and effort thresholds.
    """
    click.echo("\nAdvanced Halstead metrics:")
    click.echo("-" * 40)

    thresholds = {}

    # Halstead volume
    hv_min, hv_max = get_metric_constraints("halstead_volume")
    thresholds["max_halstead_volume"] = prompt_with_validation(
        "Maximum Halstead volume",
        default=1000,
        validator=lambda v: validate_with_pydantic("halstead_volume", v),
        help_text=f"ℹ️  Range: {hv_min}-{hv_max}. Measures program size. Recommended: 1000",
    )

    # Halstead difficulty
    hd_min, hd_max = get_metric_constraints("halstead_difficulty")
    thresholds["max_halstead_difficulty"] = prompt_with_validation(
        "Maximum Halstead difficulty",
        default=10,
        validator=lambda v: validate_with_pydantic("halstead_difficulty", v),
        help_text=f"ℹ️  Range: {hd_min}-{hd_max}. Measures error proneness. Recommended: 10",
    )

    # Halstead effort
    he_min, he_max = get_metric_constraints("halstead_effort")
    he_help = f"ℹ️  Range: {he_min}-{he_max}. Measures implementation time. Recommended: 10000"
    thresholds["max_halstead_effort"] = prompt_with_validation(
        "Maximum Halstead effort",
        default=10000,
        validator=lambda v: validate_with_pydantic("halstead_effort", v),
        help_text=he_help,
    )

    return thresholds


def _get_default_halstead_thresholds() -> dict[str, float]:
    """Get default Halstead thresholds.

    Returns:
        Dictionary with default Halstead thresholds.
    """
    return {
        "max_halstead_volume": 1000,
        "max_halstead_difficulty": 10,
        "max_halstead_effort": 10000,
    }


def _collect_language_config(defaults_dict: dict[str, Any]) -> list[dict[str, Any]]:
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
        languages.append(_create_python_config(defaults_dict))

    # JavaScript/TypeScript support coming soon
    click.echo("[ ] JavaScript/TypeScript (coming soon)")

    return languages


def _collect_project_settings() -> dict[str, Any]:
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
    settings["ignore_patterns"] = _collect_ignore_patterns()

    return settings


def _collect_ignore_patterns() -> list[str]:
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
    additional_patterns = _collect_additional_patterns()
    ignore_patterns.extend(additional_patterns)

    if not ignore_patterns:
        click.echo("  ℹ️  No ignore patterns configured")
    else:
        click.echo(f"\n  Total patterns to ignore: {len(ignore_patterns)}")

    return ignore_patterns


def _collect_additional_patterns() -> list[str]:
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


def _build_interactive_config() -> dict[str, Any]:
    """Build configuration dictionary through interactive prompts.

    Returns:
        Dictionary containing all configuration data.
    """
    config_dict: dict[str, Any] = {}

    # Collect basic thresholds
    defaults_dict = _collect_basic_thresholds()

    # Ask about advanced metrics
    if click.confirm("\nWould you like to configure advanced Halstead metrics?", default=False):
        defaults_dict.update(_collect_halstead_thresholds())
    else:
        # Use defaults for advanced metrics
        defaults_dict.update(_get_default_halstead_thresholds())

    config_dict["defaults"] = defaults_dict

    # Collect language configuration
    config_dict["languages"] = _collect_language_config(defaults_dict)

    # Collect project settings
    project_settings = _collect_project_settings()
    config_dict.update(project_settings)

    return config_dict


def _create_validated_config(config_dict: dict[str, Any]) -> AntipastaConfig:
    """Create and validate configuration object.

    Args:
        config_dict: Configuration dictionary.

    Returns:
        Validated AntipastaConfig object.

    Raises:
        SystemExit: If validation fails.
    """
    try:
        return AntipastaConfig(**config_dict)
    except ValidationError as e:
        _handle_validation_error(e)
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error creating configuration: {e}", err=True)
        sys.exit(1)


def _handle_validation_error(error: ValidationError) -> None:
    """Handle and display validation errors.

    Args:
        error: ValidationError from Pydantic.
    """
    click.echo("\n❌ Configuration validation failed:", err=True)
    for err in error.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        click.echo(f"  - {loc}: {err['msg']}", err=True)
    click.echo("\nPlease run the command again with valid values.", err=True)


def _confirm_file_overwrite(output: Path) -> bool:
    """Confirm file overwrite if file exists.

    Args:
        output: Output file path.

    Returns:
        True if should proceed, False otherwise.
    """
    click.echo(f"\nConfiguration will be saved to: {output}")

    if output.exists() and not click.confirm("File already exists. Overwrite?", default=False):
        click.echo("Aborted.")
        return False

    return True


def _finalize_and_save_config(config_dict: dict[str, Any], output: Path) -> None:
    """Create configuration object and save to file.

    Args:
        config_dict: Configuration dictionary.
        output: Output file path.
    """
    # Create configuration with validation
    config = _create_validated_config(config_dict)

    # Handle file overwrite confirmation
    if not _confirm_file_overwrite(output):
        return

    # Save the configuration
    _save_config(config, output, force=False)


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
def generate(output: Path, non_interactive: bool) -> None:
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
    _show_welcome_message()

    # Build configuration interactively
    config_dict = _build_interactive_config()

    # Create and save configuration
    _finalize_and_save_config(config_dict, output)


def _create_python_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create Python language configuration."""
    metrics = []

    # Build metrics list using a more modular approach
    metric_configs = [
        ("cyclomatic_complexity", "max_cyclomatic_complexity", "<="),
        ("cognitive_complexity", "max_cognitive_complexity", "<="),
        ("maintainability_index", "min_maintainability_index", ">="),
        ("halstead_volume", "max_halstead_volume", "<="),
        ("halstead_difficulty", "max_halstead_difficulty", "<="),
        ("halstead_effort", "max_halstead_effort", "<="),
    ]

    for metric_type, threshold_key, comparison in metric_configs:
        metrics.append({
            "type": metric_type,
            "threshold": defaults[threshold_key],
            "comparison": comparison,
        })

    return {
        "name": "python",
        "extensions": [".py"],
        "metrics": metrics,
    }


def _create_javascript_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Create JavaScript/TypeScript language configuration.

    Note: This function is ready for when JavaScript/TypeScript support is added.
    Currently not used but kept for future implementation.
    """
    # For JS/TS, we only support cyclomatic and cognitive complexity currently
    metrics: list[dict[str, str]] = []

    metrics.extend((
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
    ))

    return {
        "name": "javascript",
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "metrics": metrics,
    }


def _save_config(config: AntipastaConfig, output: Path, force: bool = False) -> None:
    """Save configuration to file with helpful comments.

    Args:
        config: Configuration object to save.
        output: Output file path.
        force: Whether to force overwrite without confirmation.
    """
    # Convert to dict for customization
    data = config.model_dump(exclude_none=True, mode="json")

    # Generate YAML content
    yaml_content = _generate_yaml_content(data)

    # Write file and show success message
    _write_config_file(output, yaml_content)


def _generate_yaml_content(data: dict[str, Any]) -> str:
    """Generate YAML content with comments from configuration data.

    Args:
        data: Configuration data dictionary.

    Returns:
        YAML content as string.
    """
    yaml_lines: list[str] = []

    # Add header comments
    _add_header_comments(yaml_lines)

    # Add defaults section
    _add_defaults_section(yaml_lines, data.get("defaults", {}))

    # Add languages section
    _add_languages_section(yaml_lines, data.get("languages", []))

    # Add ignore patterns section
    _add_ignore_patterns_section(yaml_lines, data.get("ignore_patterns", []))

    # Add gitignore setting
    _add_gitignore_setting(yaml_lines, data.get("use_gitignore", True))

    return "\n".join(yaml_lines) + "\n"


def _add_header_comments(lines: list[str]) -> None:
    """Add header comments to YAML lines.

    Args:
        lines: List to append lines to.
    """
    lines.extend([
        "# antipasta configuration file",
        "# Generated by: antipasta config generate",
        "",
    ])


def _add_defaults_section(lines: list[str], defaults: dict[str, Any]) -> None:
    """Add defaults section to YAML lines.

    Args:
        lines: List to append lines to.
        defaults: Defaults dictionary.
    """
    lines.extend([
        "# Default thresholds for all languages",
        "defaults:",
    ])

    # Basic metrics
    lines.extend(f"  max_cyclomatic_complexity: {defaults.get('max_cyclomatic_complexity', 10)}")
    lines.extend(f"  max_cognitive_complexity: {defaults.get('max_cognitive_complexity', 15)}")
    lines.extend(f"  min_maintainability_index: {defaults.get('min_maintainability_index', 50)}")

    # Halstead metrics
    lines.extend("  # Halstead metrics (advanced)")
    lines.extend(f"  max_halstead_volume: {defaults.get('max_halstead_volume', 1000)}")
    lines.extend(f"  max_halstead_difficulty: {defaults.get('max_halstead_difficulty', 10)}")
    lines.extend(f"  max_halstead_effort: {defaults.get('max_halstead_effort', 10000)}")


def _add_languages_section(lines: list[str], languages: list[dict[str, Any]]) -> None:
    """Add languages section to YAML lines.

    Args:
        lines: List to append lines to.
        languages: List of language configurations.
    """
    lines.extend([
        "",
        "# Language-specific configurations",
        "languages:",
    ])

    for lang in languages:
        _add_language_entry(lines, lang)


def _add_language_entry(lines: list[str], lang: dict[str, Any]) -> None:
    """Add a single language entry to YAML lines.

    Args:
        lines: List to append lines to.
        lang: Language configuration dictionary.
    """
    lines.append(f"  - name: {lang['name']}")

    # Add extensions if present
    if lang.get("extensions"):
        lines.append("    extensions:")
        for ext in lang["extensions"]:
            lines.append(f"      - {ext}")

    # Add metrics
    lines.append("    metrics:")
    metrics = lang.get("metrics", [])
    for i, metric in enumerate(metrics):
        lines.extend((
            f"      - type: {metric['type']}",
            f"        threshold: {metric['threshold']}",
            f'        comparison: "{metric["comparison"]}"',
        ))
        # Add spacing between metrics except for the last one
        if i < len(metrics) - 1:
            lines.append("")


def _add_ignore_patterns_section(lines: list[str], patterns: list[str]) -> None:
    """Add ignore patterns section to YAML lines.

    Args:
        lines: List to append lines to.
        patterns: List of ignore patterns.
    """
    lines.extend([
        "",
        "# Files and patterns to ignore during analysis",
    ])

    if patterns:
        lines.append("ignore_patterns:")
        for pattern in patterns:
            lines.append(f'  - "{pattern}"')
    else:
        lines.append("ignore_patterns: []")


def _add_gitignore_setting(lines: list[str], use_gitignore: bool) -> None:
    """Add gitignore setting to YAML lines.

    Args:
        lines: List to append lines to.
        use_gitignore: Whether to use .gitignore.
    """
    lines.extend([
        "",
        "# Whether to use .gitignore file for excluding files",
        f"use_gitignore: {str(use_gitignore).lower()}",
    ])


def _write_config_file(output: Path, content: str) -> None:
    """Write configuration content to file.

    Args:
        output: Output file path.
        content: YAML content to write.

    Raises:
        SystemExit: If file writing fails.
    """
    try:
        Path(output).write_text(content)

        click.echo(f"✅ Configuration saved to {output}")
        click.echo(f"\nRun 'antipasta config validate {output}' to verify.")
        click.echo("Run 'antipasta metrics' to start analyzing your code!")

    except Exception as e:
        click.echo(f"❌ Error saving configuration: {e}", err=True)
        sys.exit(1)
