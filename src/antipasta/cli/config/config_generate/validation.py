"""Validation utilities for configuration generation."""

from collections.abc import Callable
from typing import Any

import click
from pydantic import ValidationError

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
