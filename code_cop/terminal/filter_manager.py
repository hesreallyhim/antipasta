"""Filter management for terminal dashboard."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from code_cop.core.models import MetricResult, ViolationType


class FilterType(Enum):
    """Types of filters available."""

    COMPLEXITY = "complexity"
    MAINTAINABILITY = "maintainability"
    FILE_PATTERN = "file_pattern"
    VIOLATION_TYPE = "violation_type"
    METRIC_TYPE = "metric_type"


@dataclass
class Filter:
    """Represents a single filter."""

    type: FilterType
    value: Any
    comparison: str = "="  # =, <, >, <=, >=, contains, matches
    enabled: bool = True


@dataclass
class FilterPreset:
    """A saved filter configuration."""

    name: str
    description: str
    filters: List[Filter] = field(default_factory=list)


class FilterManager:
    """Manages filtering of metrics data."""

    def __init__(self):
        """Initialize the filter manager."""
        self.filters: List[Filter] = []
        self.presets: Dict[str, FilterPreset] = self._init_presets()

    def _init_presets(self) -> Dict[str, FilterPreset]:
        """Initialize default filter presets.

        Returns:
            Dictionary of preset names to FilterPreset objects
        """
        return {
            "high_complexity": FilterPreset(
                name="High Complexity",
                description="Show only high complexity files",
                filters=[
                    Filter(
                        type=FilterType.COMPLEXITY,
                        value=10,
                        comparison=">",
                    )
                ],
            ),
            "low_maintainability": FilterPreset(
                name="Low Maintainability",
                description="Show files with poor maintainability",
                filters=[
                    Filter(
                        type=FilterType.MAINTAINABILITY,
                        value=50,
                        comparison="<",
                    )
                ],
            ),
            "violations_only": FilterPreset(
                name="Violations Only",
                description="Show only files with violations",
                filters=[
                    Filter(
                        type=FilterType.VIOLATION_TYPE,
                        value="any",
                        comparison="exists",
                    )
                ],
            ),
            "critical_issues": FilterPreset(
                name="Critical Issues",
                description="Show files with critical complexity or maintainability issues",
                filters=[
                    Filter(
                        type=FilterType.COMPLEXITY,
                        value=15,
                        comparison=">",
                    ),
                    Filter(
                        type=FilterType.MAINTAINABILITY,
                        value=30,
                        comparison="<",
                    ),
                ],
            ),
        }

    def add_filter(self, filter: Filter) -> None:
        """Add a new filter.

        Args:
            filter: Filter to add
        """
        self.filters.append(filter)

    def remove_filter(self, filter: Filter) -> None:
        """Remove a filter.

        Args:
            filter: Filter to remove
        """
        if filter in self.filters:
            self.filters.remove(filter)

    def clear_filters(self) -> None:
        """Clear all active filters."""
        self.filters.clear()

    def apply_preset(self, preset_name: str) -> bool:
        """Apply a filter preset.

        Args:
            preset_name: Name of the preset to apply

        Returns:
            True if preset was applied, False if not found
        """
        if preset_name in self.presets:
            preset = self.presets[preset_name]
            self.filters = preset.filters.copy()
            return True
        return False

    def save_preset(self, name: str, description: str) -> None:
        """Save current filters as a preset.

        Args:
            name: Preset name
            description: Preset description
        """
        self.presets[name] = FilterPreset(
            name=name,
            description=description,
            filters=self.filters.copy(),
        )

    def filter_results(self, results: List[MetricResult]) -> List[MetricResult]:
        """Apply filters to metric results.

        Args:
            results: List of metric results

        Returns:
            Filtered list of results
        """
        if not self.filters:
            return results

        filtered = []
        for result in results:
            if self._matches_filters(result):
                filtered.append(result)

        return filtered

    def _matches_filters(self, result: MetricResult) -> bool:
        """Check if a result matches all active filters.

        Args:
            result: Metric result to check

        Returns:
            True if result matches all filters
        """
        for filter in self.filters:
            if not filter.enabled:
                continue

            if not self._matches_single_filter(result, filter):
                return False

        return True

    def _matches_single_filter(self, result: MetricResult, filter: Filter) -> bool:
        """Check if a result matches a single filter.

        Args:
            result: Metric result to check
            filter: Filter to apply

        Returns:
            True if result matches filter
        """
        # Get the value to compare based on filter type
        if filter.type == FilterType.COMPLEXITY:
            value = result.metrics.get("cyclomatic_complexity", 0)
        elif filter.type == FilterType.MAINTAINABILITY:
            value = result.metrics.get("maintainability_index", 100)
        elif filter.type == FilterType.FILE_PATTERN:
            value = result.file_path
        elif filter.type == FilterType.VIOLATION_TYPE:
            value = [v.type for v in result.violations]
        elif filter.type == FilterType.METRIC_TYPE:
            value = list(result.metrics.keys())
        else:
            return True

        # Apply comparison
        return self._compare_values(value, filter.value, filter.comparison)

    def _compare_values(self, actual: Any, expected: Any, comparison: str) -> bool:
        """Compare values based on comparison operator.

        Args:
            actual: Actual value
            expected: Expected value
            comparison: Comparison operator

        Returns:
            True if comparison passes
        """
        try:
            if comparison == "=":
                return actual == expected
            elif comparison == "<":
                return actual < expected
            elif comparison == ">":
                return actual > expected
            elif comparison == "<=":
                return actual <= expected
            elif comparison == ">=":
                return actual >= expected
            elif comparison == "contains":
                return expected in str(actual)
            elif comparison == "matches":
                import re
                return bool(re.match(expected, str(actual)))
            elif comparison == "exists":
                if isinstance(actual, list):
                    return len(actual) > 0
                return actual is not None
        except Exception:
            return False

        return True

    def get_active_filter_summary(self) -> str:
        """Get a summary of active filters.

        Returns:
            Human-readable filter summary
        """
        if not self.filters:
            return "No filters active"

        summaries = []
        for filter in self.filters:
            if not filter.enabled:
                continue

            type_name = filter.type.value.replace("_", " ").title()
            summary = f"{type_name} {filter.comparison} {filter.value}"
            summaries.append(summary)

        return " AND ".join(summaries)

    def get_filter_stats(self, original: List[MetricResult], filtered: List[MetricResult]) -> Dict[str, int]:
        """Get statistics about filter results.

        Args:
            original: Original results
            filtered: Filtered results

        Returns:
            Dictionary of statistics
        """
        return {
            "total": len(original),
            "shown": len(filtered),
            "hidden": len(original) - len(filtered),
            "filter_count": len([f for f in self.filters if f.enabled]),
        }