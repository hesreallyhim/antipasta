"""Metric data models and types.

This module defines the core data structures for representing
code quality metrics and analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class MetricType(StrEnum):
    """Types of code metrics supported."""

    CYCLOMATIC_COMPLEXITY = "cyclomatic_complexity"
    MAINTAINABILITY_INDEX = "maintainability_index"
    HALSTEAD_VOLUME = "halstead_volume"
    HALSTEAD_DIFFICULTY = "halstead_difficulty"
    HALSTEAD_EFFORT = "halstead_effort"
    HALSTEAD_TIME = "halstead_time"
    HALSTEAD_BUGS = "halstead_bugs"
    COGNITIVE_COMPLEXITY = "cognitive_complexity"
    LINES_OF_CODE = "lines_of_code"
    LOGICAL_LINES_OF_CODE = "logical_lines_of_code"
    SOURCE_LINES_OF_CODE = "source_lines_of_code"
    COMMENT_LINES = "comment_lines"
    BLANK_LINES = "blank_lines"


@dataclass
class MetricResult:
    """Result of a metric calculation."""

    file_path: Path
    metric_type: MetricType
    value: float
    details: dict[str, Any] | None = None
    line_number: int | None = None
    function_name: str | None = None

    def __post_init__(self) -> None:
        """Ensure file_path is a Path object."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the metric result for JSON-friendly output."""
        return {
            "type": self.metric_type.value,
            "value": self.value,
            "details": self.details,
            "line_number": self.line_number,
            "function_name": self.function_name,
        }


@dataclass
class FileMetrics:
    """Collection of metrics for a single file."""

    file_path: Path
    language: str
    metrics: list[MetricResult]
    error: str | None = None

    def __post_init__(self) -> None:
        """Ensure file_path is a Path object."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)

    def get_metric(self, metric_type: MetricType) -> MetricResult | None:
        """Get a specific metric result."""
        for metric in self.metrics:
            if metric.metric_type == metric_type:
                return metric
        return None

    def get_metrics_by_type(self, metric_type: MetricType) -> list[MetricResult]:
        """Get all metrics of a specific type (useful for function-level metrics)."""
        return [m for m in self.metrics if m.metric_type == metric_type]
