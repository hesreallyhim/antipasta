"""Interactive prompts for collecting threshold configurations."""

import click

from antipasta.cli.validation_utils import get_metric_constraints

from .validation import prompt_with_validation, validate_with_pydantic


def show_welcome_message() -> None:
    """Display welcome message for interactive configuration."""
    click.echo("\nWelcome to antipasta configuration generator!")
    click.echo("=" * 50)
    click.echo("\nThis wizard will help you create a configuration file with")
    click.echo("code quality thresholds tailored to your project.")
    click.echo("\nFor each metric, you'll see the valid range and recommended value.")
    click.echo("Press Ctrl+C at any time to cancel.")


def collect_basic_thresholds() -> dict[str, float]:
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


def collect_halstead_thresholds() -> dict[str, float]:
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


def get_default_halstead_thresholds() -> dict[str, float]:
    """Get default Halstead thresholds.

    Returns:
        Dictionary with default Halstead thresholds.
    """
    return {
        "max_halstead_volume": 1000,
        "max_halstead_difficulty": 10,
        "max_halstead_effort": 10000,
    }


def should_configure_advanced_metrics() -> bool:
    """Ask if user wants to configure advanced metrics.

    Returns:
        True if user wants to configure advanced metrics, False otherwise.
    """
    return click.confirm("\nWould you like to configure advanced Halstead metrics?", default=False)
