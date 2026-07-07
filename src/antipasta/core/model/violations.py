"""Violation detection and reporting models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import operator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from antipasta.core.model.config import ComparisonOperator, MetricConfig

if TYPE_CHECKING:
    from antipasta.core.model.metrics import MetricResult, MetricType


@dataclass
class Violation:
    """Represents a metric violation."""

    file_path: Path
    metric_type: MetricType
    value: float
    threshold: float
    comparison: ComparisonOperator
    line_number: int | None = None
    function_name: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        """Ensure file_path is a Path object and generate message."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)

        if self.message is None:
            self.message = self._generate_message()

    def _generate_message(self) -> str:
        """Generate a human-readable violation message."""
        location = self._format_location()
        metric_name = self._format_metric_name()

        return (
            f"{location}: {metric_name} is {self.value:.2f} "
            f"(threshold: {self.comparison.value} {self.threshold})"
        )

    def _format_location(self) -> str:
        """Format the location string with file, line, and function info."""
        location = str(self.file_path)
        if self.line_number:
            location += f":{self.line_number}"
        if self.function_name:
            location += f" ({self.function_name})"
        return location

    def _format_metric_name(self) -> str:
        """Format the metric type for display."""
        return self.metric_type.value.replace("_", " ").title()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the violation information for JSON-friendly output."""
        return {
            "type": self.metric_type.value,
            "message": self.message,
            "line_number": self.line_number,
            "function": self.function_name,
            "value": self.value,
            "threshold": self.threshold,
            "comparison": self.comparison.value,
        }


@dataclass
class FileReport:
    """Report for a single file's metrics and violations."""

    file_path: Path
    language: str
    metrics: list[MetricResult]
    violations: list[Violation]
    error: str | None = None

    def __post_init__(self) -> None:
        """Ensure file_path is a Path object."""
        if isinstance(self.file_path, str):
            self.file_path = Path(self.file_path)

    @property
    def has_violations(self) -> bool:
        """Check if this file has any violations."""
        return len(self.violations) > 0

    @property
    def violation_count(self) -> int:
        """Get the number of violations."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for JSON-friendly output."""
        data = self._build_base_dict()
        self._add_error_if_present(data)
        return data

    def _build_base_dict(self) -> dict[str, Any]:
        """Build the base dictionary for serialization."""
        return {
            "file": str(self.file_path),
            "language": self.language,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "violations": [violation.to_dict() for violation in self.violations],
        }

    def _add_error_if_present(self, data: dict[str, Any]) -> None:
        """Add error to dictionary if present."""
        if self.error is not None:
            data["error"] = self.error

    def violation_messages(self) -> list[str]:
        """Return formatted violation messages for display."""
        return [f"❌ {violation.message}" for violation in self.violations]


@dataclass
class ProjectReport:
    """Report for a project- or directory-scoped derivation.

    The subject is a path-like string ("." for the whole project, or a
    directory path) rather than a file: these reports carry findings whose
    home is the structure, not any single file (dependency cycles, module
    tree shape). Violations reuse the Violation model with the subject as
    the path.
    """

    subject: str
    metrics: list[MetricResult]
    violations: list[Violation]

    @property
    def has_violations(self) -> bool:
        """Check if this subject has any violations."""
        return len(self.violations) > 0

    @property
    def violation_count(self) -> int:
        """Get the number of violations."""
        return len(self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for JSON-friendly output."""
        return {
            "subject": self.subject,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "violations": [violation.to_dict() for violation in self.violations],
        }

    def violation_messages(self) -> list[str]:
        """Return formatted violation messages for display."""
        return [f"❌ {violation.message}" for violation in self.violations]


# Dictionary dispatch for comparison operations to reduce cyclomatic complexity
_VIOLATION_CHECKS: dict[ComparisonOperator, Callable[[float, float], bool]] = {
    ComparisonOperator.LT: operator.ge,  # value should be < threshold
    ComparisonOperator.LE: operator.gt,  # value should be <= threshold
    ComparisonOperator.GT: operator.le,  # value should be > threshold
    ComparisonOperator.GE: operator.lt,  # value should be >= threshold
    ComparisonOperator.EQ: operator.ne,  # value should be == threshold
    ComparisonOperator.NE: operator.eq,  # value should be != threshold
}


def check_metric_violation(metric: MetricResult, config: MetricConfig) -> Violation | None:
    """Check if a metric violates its configured threshold.

    Args:
        metric: The metric result to check
        config: The metric configuration with threshold

    Returns:
        Violation if threshold is violated, None otherwise
    """
    if not config.enabled:
        return None

    # Use dictionary dispatch to avoid if-elif ladder
    check_fn = _VIOLATION_CHECKS.get(config.comparison)
    if not check_fn:
        return None

    violated = check_fn(metric.value, config.threshold)

    if not violated:
        return None

    return Violation(
        file_path=metric.file_path,
        metric_type=metric.metric_type,
        value=metric.value,
        threshold=config.threshold,
        comparison=config.comparison,
        line_number=metric.line_number,
        function_name=metric.function_name,
    )


def summarize_reports(reports: list[FileReport]) -> dict[str, Any]:
    """Suite-level summary over file reports (pure; shared by engine and
    snapshot so the store layer never reaches up into orchestration)."""
    from collections import defaultdict

    violations_by_type: dict[str, int] = defaultdict(int)
    files_by_language: dict[str, int] = defaultdict(int)
    total_violations = 0
    for report in reports:
        files_by_language[report.language] += 1
        total_violations += report.violation_count
        for violation in report.violations:
            violations_by_type[violation.metric_type.value] += 1
    return {
        "total_files": len(reports),
        "files_with_violations": sum(1 for r in reports if r.has_violations),
        "total_violations": total_violations,
        "violations_by_type": dict(violations_by_type),
        "files_by_language": dict(files_by_language),
        "success": total_violations == 0,
    }
