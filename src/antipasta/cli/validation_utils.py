"""Utilities for extracting validation info from Pydantic schemas.

This module provides helper functions to extract constraint information
from Pydantic models and format them for CLI help text and error messages.
"""

from typing import Any

from antipasta.core.metric_models import MetricThresholds


def get_metric_constraints(metric_type: str) -> tuple[float | None, float | None]:
    """Get min/max constraints for a metric from Pydantic schema.

    Args:
        metric_type: The metric type to get constraints for

    Returns:
        Tuple of (min_value, max_value), either can be None
    """
    schema_properties = _get_metric_schema_properties()

    if not _is_valid_metric_type(metric_type, schema_properties):
        return (None, None)

    resolved_schema = _resolve_property_schema(schema_properties[metric_type])
    return _extract_range_constraints(resolved_schema)


def get_metric_help_text(metric_type: str) -> str:
    """Get help text for a metric including its valid range.

    Args:
        metric_type: The metric type to get help text for

    Returns:
        Help text string with description and valid range
    """
    schema_properties = _get_metric_schema_properties()

    if not _is_valid_metric_type(metric_type, schema_properties):
        return f"Metric: {metric_type}"

    resolved_schema = _resolve_property_schema(schema_properties[metric_type])
    description = _extract_description(resolved_schema)
    range_constraints = _extract_range_constraints(resolved_schema)

    return _format_help_text_with_range(description, range_constraints, metric_type)


def _get_metric_schema_properties() -> dict[str, Any]:
    """Extract properties from MetricThresholds schema."""
    schema: dict[str, dict[str, Any]] = MetricThresholds.model_json_schema()
    return schema.get("properties", {})


def _is_valid_metric_type(metric_type: str, schema_properties: dict[str, Any]) -> bool:
    """Check if metric type exists in schema properties."""
    return metric_type in schema_properties


def _resolve_property_schema(prop_schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve anyOf schemas to get the actual property schema.

    Handles Optional fields that use anyOf with null type.
    """
    if "anyOf" not in prop_schema:
        return prop_schema

    return _extract_non_null_schema_from_any_of(prop_schema["anyOf"])


def _extract_non_null_schema_from_any_of(any_of_schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Find and return the non-null schema from anyOf list."""
    for sub_schema in any_of_schemas:
        if sub_schema.get("type") != "null":
            return sub_schema

    # Fallback to first schema if no non-null found
    return any_of_schemas[0] if any_of_schemas else {}


def _extract_range_constraints(schema: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract minimum and maximum constraints from schema."""
    min_val = _get_minimum_constraint(schema)
    max_val = _get_maximum_constraint(schema)
    return (min_val, max_val)


def _get_minimum_constraint(schema: dict[str, Any]) -> float | None:
    """Extract minimum constraint, checking both inclusive and exclusive bounds."""
    min_val: float | None = schema.get("minimum")
    if min_val is not None:
        return min_val
    return schema.get("exclusiveMinimum")


def _get_maximum_constraint(schema: dict[str, Any]) -> float | None:
    """Extract maximum constraint, checking both inclusive and exclusive bounds."""
    max_val: float | None = schema.get("maximum")
    if max_val is not None:
        return max_val
    return schema.get("exclusiveMaximum")


def _extract_description(schema: dict[str, Any]) -> str:
    """Extract description from schema, removing any existing range information."""
    description = schema.get("description", "")

    if not description:
        return ""

    return _remove_existing_range_from_description(description)


def _remove_existing_range_from_description(description: str) -> str:
    """Remove existing range information from description text."""
    if "(" in description:
        return description.split("(")[0].strip()
    return description


def _format_help_text_with_range(
    description: str, range_constraints: tuple[float | None, float | None], metric_type: str
) -> str:
    """Format help text combining description and range constraints."""
    min_val, max_val = range_constraints

    if not _has_range_constraints(min_val, max_val):
        return description or f"Metric: {metric_type}"

    range_text = _format_range_text(min_val, max_val)

    if description:
        return f"{description} (valid: {range_text})"

    return f"Valid range: {range_text}"


def _has_range_constraints(min_val: float | None, max_val: float | None) -> bool:
    """Check if any range constraints are present."""
    return min_val is not None or max_val is not None


def _format_range_text(min_val: float | None, max_val: float | None) -> str:
    """Format range constraints into human-readable text."""
    range_parts = []

    if min_val is not None:
        range_parts.append(f">= {min_val}")
    if max_val is not None:
        range_parts.append(f"<= {max_val}")

    return " and ".join(range_parts)


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
    if "must be" in error_msg:
        # Range errors are already clear
        return error_msg
    return f"Validation error: {error_msg}"
