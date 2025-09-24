"""Configuration override system for command-line customization.

This module provides functionality to override configuration settings
via command-line flags, allowing temporary modifications without
editing configuration files.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from antipasta.core.metric_models import MetricThresholds
from antipasta.core.metrics import MetricType


@dataclass
class ConfigOverride:
    """Stores configuration overrides from command-line flags.

    Attributes:
        include_patterns: Patterns to force-include (overrides ignore patterns)
        exclude_patterns: Additional patterns to exclude
        threshold_overrides: Metric threshold overrides (metric_type -> threshold)
        disable_gitignore: Whether to disable .gitignore usage
        force_analyze: Whether to ignore all exclusions
    """

    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    disable_gitignore: bool = False
    force_analyze: bool = False

    # Use Pydantic model internally for validation
    _threshold_model: MetricThresholds = field(
        default_factory=MetricThresholds, init=False, repr=False
    )

    @property
    def threshold_overrides(self) -> dict[str, float]:
        """Get threshold overrides as a dict (for compatibility)."""
        return {k: v for k, v in self._threshold_model.model_dump().items() if v is not None}

    def add_include_pattern(self, pattern: str) -> None:
        """Add a pattern to force-include.

        Args:
            pattern: Glob pattern to include
        """
        if pattern not in self.include_patterns:
            self.include_patterns.append(pattern)

    def add_exclude_pattern(self, pattern: str) -> None:
        """Add an additional exclusion pattern.

        Args:
            pattern: Glob pattern to exclude
        """
        if pattern not in self.exclude_patterns:
            self.exclude_patterns.append(pattern)

    def set_threshold(self, metric_type: str, value: float) -> None:
        """Override a metric threshold with Pydantic validation.

        Args:
            metric_type: Type of metric (e.g., 'cyclomatic_complexity')
            value: New threshold value (auto-validated by Pydantic)

        Raises:
            ValueError: If metric type invalid or value out of range
        """
        # First check if metric type is valid
        try:
            MetricType(metric_type)
        except ValueError:
            valid_metrics = [m.value for m in MetricType]
            raise ValueError(
                f"Invalid metric type: '{metric_type}'. "
                f"Valid types: {', '.join(sorted(valid_metrics))}"
            ) from None

        # Use Pydantic for validation
        try:
            # This triggers Pydantic validation automatically
            setattr(self._threshold_model, metric_type, value)
        except ValidationError as e:
            # Convert Pydantic error to user-friendly message
            raise ValueError(self._format_validation_error(metric_type, value, e)) from None

    def _format_validation_error(
        self, metric_type: str, value: float, error: ValidationError
    ) -> str:
        """Convert Pydantic ValidationError to user-friendly message."""
        for err in error.errors():
            if metric_type in str(err.get("loc", ())):
                return self._format_specific_error(metric_type, value, err)

        # Fallback
        return f"Invalid value for {metric_type}: {value}"

    def _format_specific_error(self, metric_type: str, value: float, err: ErrorDetails) -> str:
        """Format a specific validation error based on its type."""
        err_type = err.get("type", "")
        ctx: dict[str, Any] = err.get("ctx", {}) or {}

        # Map error types to formatter functions
        error_formatters: dict[str, Callable[[], str]] = {
            "greater_than_equal": lambda: (
                f"{metric_type} must be >= {ctx.get('ge', 0)}, got {value}"
            ),
            "less_than_equal": lambda: (
                f"{metric_type} must be <= {ctx.get('le', 'max')}, got {value}"
            ),
            "greater_than": lambda: (f"{metric_type} must be > {ctx.get('gt', 0)}, got {value}"),
            "less_than": lambda: (f"{metric_type} must be < {ctx.get('lt', 'max')}, got {value}"),
            "int_type": lambda: f"{metric_type} must be an integer, got {value}",
            "int_parsing": lambda: f"{metric_type} must be a valid integer",
        }

        # Find matching formatter
        for error_key, formatter in error_formatters.items():
            if error_key in err_type or err_type == error_key:
                return formatter()

        # Default message
        return f"Invalid value for {metric_type}: {err.get('msg', 'validation failed')}"

    def parse_threshold_string(self, threshold_str: str) -> None:
        """Parse a threshold override string in format 'metric_type=value'.

        Args:
            threshold_str: String like 'cyclomatic_complexity=15' or 'cyc=15'

        Raises:
            ValueError: If string format is invalid
        """
        if "=" not in threshold_str:
            raise ValueError(
                f"Invalid threshold format: {threshold_str}. Expected 'metric_type=value'"
            )

        metric_type, value_str = threshold_str.split("=", 1)
        metric_type = metric_type.strip()

        # Support three-letter prefixes for convenience
        prefix_map = {
            "cyc": "cyclomatic_complexity",
            "cog": "cognitive_complexity",
            "mai": "maintainability_index",
            "vol": "halstead_volume",
            "dif": "halstead_difficulty",
            "eff": "halstead_effort",
        }

        # Check if it's a prefix and expand it
        metric_type = prefix_map.get(metric_type, metric_type)

        try:
            value = float(value_str.strip())
        except ValueError:
            raise ValueError(f"Invalid threshold value: {value_str}. Must be a number") from None

        self.set_threshold(metric_type, value)

    def has_overrides(self) -> bool:
        """Check if any overrides are configured.

        Returns:
            True if any overrides are set
        """
        return bool(
            self.include_patterns
            or self.exclude_patterns
            or any(v is not None for v in self._threshold_model.model_dump().values())
            or self.disable_gitignore
            or self.force_analyze
        )

    def get_effective_ignore_patterns(self, base_patterns: list[str]) -> list[str]:
        """Get effective ignore patterns after applying overrides.

        When force_analyze is True, returns empty list.
        Otherwise, combines base patterns with exclude overrides.

        Args:
            base_patterns: Original ignore patterns from config

        Returns:
            List of patterns to ignore
        """
        if self.force_analyze:
            return []

        # Start with base patterns
        effective_patterns = base_patterns.copy()

        # Add additional exclude patterns
        for pattern in self.exclude_patterns:
            if pattern not in effective_patterns:
                effective_patterns.append(pattern)

        return effective_patterns

    def should_force_include(self, file_path: str) -> bool:
        """Check if a file should be force-included.

        Args:
            file_path: Path to check

        Returns:
            True if file matches an include pattern or force_analyze is True
        """
        if self.force_analyze:
            return True

        if not self.include_patterns:
            return False

        # Import here to avoid circular dependency
        import pathspec

        # Create pathspec from include patterns
        spec = pathspec.PathSpec.from_lines("gitwildmatch", self.include_patterns)
        return spec.match_file(file_path)

    def merge_with_config_dict(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Merge overrides with a configuration dictionary.

        Args:
            config_dict: Original configuration as dict

        Returns:
            Modified configuration dictionary
        """
        # Deep copy to avoid modifying original
        import copy

        merged = copy.deepcopy(config_dict)

        self._apply_gitignore_override(merged)
        self._apply_ignore_pattern_overrides(merged)
        self._apply_threshold_overrides(merged)

        return merged

    def _apply_gitignore_override(self, config: dict[str, Any]) -> None:
        """Apply gitignore override to configuration."""
        if self.disable_gitignore:
            config["use_gitignore"] = False

    def _apply_ignore_pattern_overrides(self, config: dict[str, Any]) -> None:
        """Apply ignore pattern overrides to configuration."""
        if "ignore_patterns" in config:
            config["ignore_patterns"] = self.get_effective_ignore_patterns(
                config["ignore_patterns"]
            )

    def _apply_threshold_overrides(self, config: dict[str, Any]) -> None:
        """Apply threshold overrides to configuration."""
        if not self.threshold_overrides:
            return

        self._apply_default_threshold_overrides(config)
        self._apply_language_threshold_overrides(config)

    def _apply_default_threshold_overrides(self, config: dict[str, Any]) -> None:
        """Apply threshold overrides to default configuration."""
        if "defaults" not in config:
            return

        # Map metric types to default field names
        field_map = self._get_metric_field_map()

        for metric_type, value in self.threshold_overrides.items():
            if metric_type in field_map:
                config["defaults"][field_map[metric_type]] = value

    def _apply_language_threshold_overrides(self, config: dict[str, Any]) -> None:
        """Apply threshold overrides to language-specific configuration."""
        if "languages" not in config:
            return

        for lang_config in config["languages"]:
            self._update_language_metrics(lang_config)

    def _update_language_metrics(self, lang_config: dict[str, Any]) -> None:
        """Update metrics in a language configuration."""
        if "metrics" not in lang_config:
            return

        for metric_config in lang_config["metrics"]:
            metric_type = metric_config.get("type")
            if metric_type in self.threshold_overrides:
                metric_config["threshold"] = self.threshold_overrides[metric_type]

    def _get_metric_field_map(self) -> dict[str, str]:
        """Get mapping from metric types to configuration field names."""
        return {
            "cyclomatic_complexity": "max_cyclomatic_complexity",
            "cognitive_complexity": "max_cognitive_complexity",
            "maintainability_index": "min_maintainability_index",
            "halstead_volume": "max_halstead_volume",
            "halstead_difficulty": "max_halstead_difficulty",
            "halstead_effort": "max_halstead_effort",
        }
