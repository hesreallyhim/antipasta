"""Main entry point for configuration generation command."""

from pathlib import Path
from typing import Any

import click

from antipasta.core.config import AntipastaConfig

from .file_operations import (
    confirm_file_overwrite,
    create_validated_config,
    save_config,
)
from .interactive_prompts import (
    collect_basic_thresholds,
    collect_halstead_thresholds,
    get_default_halstead_thresholds,
    should_configure_advanced_metrics,
    show_welcome_message,
)
from .language_config import collect_language_config
from .project_config import collect_project_settings


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
        save_config(config, output)
        return

    # Interactive mode
    show_welcome_message()

    # Build configuration interactively
    config_dict = build_interactive_config()

    # Create and save configuration
    finalize_and_save_config(config_dict, output)


def build_interactive_config() -> dict[str, Any]:
    """Build configuration dictionary through interactive prompts.

    Returns:
        Dictionary containing all configuration data.
    """
    config_dict: dict[str, Any] = {}

    # Collect basic thresholds
    defaults_dict = collect_basic_thresholds()

    # Ask about advanced metrics
    if should_configure_advanced_metrics():
        defaults_dict.update(collect_halstead_thresholds())
    else:
        # Use defaults for advanced metrics
        defaults_dict.update(get_default_halstead_thresholds())

    config_dict["defaults"] = defaults_dict

    # Collect language configuration
    config_dict["languages"] = collect_language_config(defaults_dict)

    # Collect project settings
    project_settings = collect_project_settings()
    config_dict.update(project_settings)

    return config_dict


def finalize_and_save_config(config_dict: dict[str, Any], output: Path) -> None:
    """Create configuration object and save to file.

    Args:
        config_dict: Configuration dictionary.
        output: Output file path.
    """
    # Create configuration with validation
    config = create_validated_config(config_dict)

    # Handle file overwrite confirmation
    if not confirm_file_overwrite(output):
        return

    # Save the configuration
    save_config(config, output)
