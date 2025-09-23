"""Utilities for extracting validation info from Pydantic schemas.

This module provides helper functions to extract constraint information
from Pydantic models and format them for CLI help text and error messages.
"""

from typing import Optional, Tuple

from antipasta.core.metric_models import MetricThresholds


def get_metric_constraints(metric_type: str) -> Tuple[Optional[float], Optional[float]]:
    """Get min/max constraints for a metric from Pydantic schema.

    Args:
        metric_type: The metric type to get constraints for

    Returns:
        Tuple of (min_value, max_value), either can be None
    """
    schema = MetricThresholds.model_json_schema()
    properties = schema.get('properties', {})

    if metric_type in properties:
        prop_schema = properties[metric_type]

        # Handle anyOf schemas (used for Optional fields)
        if 'anyOf' in prop_schema:
            # Find the non-null schema
            for sub_schema in prop_schema['anyOf']:
                if sub_schema.get('type') != 'null':
                    prop_schema = sub_schema
                    break

        min_val = prop_schema.get('minimum')
        max_val = prop_schema.get('maximum')

        # Also check for exclusive bounds
        if min_val is None:
            min_val = prop_schema.get('exclusiveMinimum')
        if max_val is None:
            max_val = prop_schema.get('exclusiveMaximum')

        return (min_val, max_val)

    return (None, None)


def get_metric_help_text(metric_type: str) -> str:
    """Get help text for a metric including its valid range.

    Args:
        metric_type: The metric type to get help text for

    Returns:
        Help text string with description and valid range
    """
    schema = MetricThresholds.model_json_schema()
    properties = schema.get('properties', {})

    if metric_type in properties:
        prop_schema = properties[metric_type]

        # Handle anyOf schemas
        if 'anyOf' in prop_schema:
            for sub_schema in prop_schema['anyOf']:
                if sub_schema.get('type') != 'null':
                    prop_schema = sub_schema
                    break

        description = prop_schema.get('description', '')

        # Extract range from schema
        min_val, max_val = get_metric_constraints(metric_type)

        range_parts = []
        if min_val is not None:
            range_parts.append(f">= {min_val}")
        if max_val is not None:
            range_parts.append(f"<= {max_val}")

        if range_parts:
            range_text = " and ".join(range_parts)
            if description:
                # Extract just the description part without existing range
                if '(' in description:
                    description = description.split('(')[0].strip()
                return f"{description} (valid: {range_text})"
            else:
                return f"Valid range: {range_text}"

        return description if description else f"Metric: {metric_type}"

    return f"Metric: {metric_type}"


def format_validation_error_for_cli(e: Exception) -> str:
    """Format validation errors for CLI display.

    Args:
        e: The exception to format

    Returns:
        User-friendly error message
    """
    error_msg = str(e)

    # Make error messages more user-friendly
    if "Invalid metric type" in error_msg:
        # The error already lists valid types
        return error_msg
    elif "must be" in error_msg:
        # Range errors are already clear
        return error_msg
    else:
        return f"Validation error: {error_msg}"