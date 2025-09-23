"""Configuration override system for command-line customization.

This module provides functionality to override configuration settings
via command-line flags, allowing temporary modifications without
editing configuration files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    threshold_overrides: dict[str, float] = field(default_factory=dict)
    disable_gitignore: bool = False
    force_analyze: bool = False

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
        """Override a metric threshold.

        Args:
            metric_type: Type of metric (e.g., 'cyclomatic_complexity')
            value: New threshold value
        """
        # Validate metric type
        try:
            MetricType(metric_type)
        except ValueError:
            raise ValueError(f"Invalid metric type: {metric_type}")

        if value < 0:
            raise ValueError(f"Threshold must be non-negative: {value}")

        self.threshold_overrides[metric_type] = value

    def parse_threshold_string(self, threshold_str: str) -> None:
        """Parse a threshold override string in format 'metric_type=value'.

        Args:
            threshold_str: String like 'cyclomatic_complexity=15'

        Raises:
            ValueError: If string format is invalid
        """
        if '=' not in threshold_str:
            raise ValueError(f"Invalid threshold format: {threshold_str}. Expected 'metric_type=value'")

        metric_type, value_str = threshold_str.split('=', 1)
        metric_type = metric_type.strip()

        try:
            value = float(value_str.strip())
        except ValueError:
            raise ValueError(f"Invalid threshold value: {value_str}. Must be a number")

        self.set_threshold(metric_type, value)

    def has_overrides(self) -> bool:
        """Check if any overrides are configured.

        Returns:
            True if any overrides are set
        """
        return bool(
            self.include_patterns or
            self.exclude_patterns or
            self.threshold_overrides or
            self.disable_gitignore or
            self.force_analyze
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
        spec = pathspec.PathSpec.from_lines('gitwildmatch', self.include_patterns)
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

        # Apply gitignore override
        if self.disable_gitignore:
            merged['use_gitignore'] = False

        # Apply ignore pattern overrides
        if 'ignore_patterns' in merged:
            merged['ignore_patterns'] = self.get_effective_ignore_patterns(
                merged['ignore_patterns']
            )

        # Apply threshold overrides
        if self.threshold_overrides:
            # Update defaults
            if 'defaults' in merged:
                for metric_type, value in self.threshold_overrides.items():
                    # Map metric types to default field names
                    field_map = {
                        'cyclomatic_complexity': 'max_cyclomatic_complexity',
                        'cognitive_complexity': 'max_cognitive_complexity',
                        'maintainability_index': 'min_maintainability_index',
                        'halstead_volume': 'max_halstead_volume',
                        'halstead_difficulty': 'max_halstead_difficulty',
                        'halstead_effort': 'max_halstead_effort',
                    }

                    if metric_type in field_map:
                        merged['defaults'][field_map[metric_type]] = value

            # Update language-specific metrics
            if 'languages' in merged:
                for lang_config in merged['languages']:
                    if 'metrics' in lang_config:
                        for metric_config in lang_config['metrics']:
                            metric_type = metric_config.get('type')
                            if metric_type in self.threshold_overrides:
                                metric_config['threshold'] = self.threshold_overrides[metric_type]

        return merged