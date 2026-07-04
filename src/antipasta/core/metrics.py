"""Metric data models and types.

This module defines the core data structures for representing
code quality metrics and analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    # House-style metrics (adoption plan, Phase 1). Informational-first:
    # none carries a default threshold; gates are opt-in per config.
    MESSAGE_CHAIN_DEPTH = "message_chain_depth"
    FUNCTION_ARITY = "function_arity"
    BOOLEAN_FLAG_PARAMETERS = "boolean_flag_parameters"
    EXCEPTION_DISCIPLINE = "exception_discipline"
    GLOBAL_STATE_REACH = "global_state_reach"
    MARKER_DENSITY = "marker_density"
    COMMENT_DENSITY = "comment_density"
    FUNCTION_STATEMENTS = "function_statements"
    EXPRESSION_FLATNESS = "expression_flatness"
    PIPELINE_LINEARITY = "pipeline_linearity"
    # Class-scope metrics (adoption plan, Phase 2). Informational-first.
    LACK_OF_COHESION = "lack_of_cohesion"
    WEIGHTED_METHODS_PER_CLASS = "weighted_methods_per_class"
    COUPLING_BETWEEN_OBJECTS = "coupling_between_objects"
    DEPTH_OF_INHERITANCE_TREE = "depth_of_inheritance_tree"
    NUMBER_OF_CHILDREN = "number_of_children"
    SINGLE_RESPONSIBILITY_INDEX = "single_responsibility_index"
    # Project-scope metrics (derivation stage).
    DIRECTORY_CHILDREN = "directory_children"
    # Import-graph metrics (adoption plan, Phase 3). Informational-first.
    EFFERENT_COUPLING = "efferent_coupling"
    AFFERENT_COUPLING = "afferent_coupling"
    INSTABILITY = "instability"
    DEPENDENCY_CYCLES = "dependency_cycles"
    STABLE_DEPENDENCIES_VIOLATIONS = "stable_dependencies_violations"
    # Main-Sequence composites (adoption plan, Phase 4). Informational-first;
    # all three are labeled approximations (Python abstractness is inferred
    # from abstract-base/Protocol/abstractmethod markers).
    ABSTRACTNESS = "abstractness"
    DISTANCE_FROM_MAIN_SEQUENCE = "distance_from_main_sequence"
    DEPENDENCY_INVERSION = "dependency_inversion"
    # Narrative Index (adoption plan, Phase 4). Per-module counts;
    # informational-first.
    NARRATIVE_MIXED_FUNCTIONS = "narrative_mixed_functions"
    NARRATOR_BUDGET_EXCEEDED = "narrator_budget_exceeded"
    COMPUTER_BUDGET_EXCEEDED = "computer_budget_exceeded"
    STEP_DOWN_ORDERING = "step_down_ordering"
    LAYERING_VIOLATIONS = "layering_violations"
    NAME_CLARITY = "name_clarity"
    NAMING_ANTIPATTERNS = "naming_antipatterns"
    # Duplication (track A, pydry engine). Config-gated.
    DUPLICATION_RATIO = "duplication_ratio"
    CLONE_OCCURRENCES = "clone_occurrences"
    # Version-control mining (track B; opt-in command, never the default path).
    # Test-suite health, static smells (track D1). Rows appear only for
    # test functions in test-looking files.
    ASSERTIONS_PER_TEST = "assertions_per_test"
    MOCK_CALL_ASSERTIONS = "mock_call_assertions"
    BIG_LITERAL_ASSERTIONS = "big_literal_assertions"
    CODE_CHURN = "code_churn"
    CHANGE_COUPLING = "change_coupling"
    HOTSPOT = "hotspot"
    TEST_CHURN_RATIO = "test_churn_ratio"
    CO_CHURN_MULTIPLICITY = "co_churn_multiplicity"
    # Coverage-matrix analytics (track D2; artifact ingestion).
    SUITE_REDUNDANCY_INDEX = "suite_redundancy_index"
    BLAST_RADIUS = "blast_radius"


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

    @classmethod
    def from_dict(cls, file_path: Path, data: dict[str, Any]) -> MetricResult:
        """Rehydrate a serialized metric row against a concrete file path.

        The serialized form is path-independent (see to_dict), which is what
        lets content-addressed cache entries survive renames and clones.
        """
        return cls(
            file_path=file_path,
            metric_type=MetricType(data["type"]),
            value=float(data["value"]),
            details=data.get("details"),
            line_number=data.get("line_number"),
            function_name=data.get("function_name"),
        )


@dataclass
class FactRow:
    """A path-independent, judgment-free fact extracted from one file.

    Facts are the extraction half of the extract/derive split for
    whole-program metrics (see docs/design/structural-metrics-caching.md):
    raw material like unresolved import statements or class declarations,
    cached content-addressed alongside metric rows and consumed by derivers.
    Two hard rules keep them cacheable: the payload must be reproducible from
    the file's bytes alone (no location-derived data), and it carries no
    judgment (config never influences extraction).
    """

    kind: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the fact for JSON-friendly storage."""
        return {"kind": self.kind, "payload": self.payload}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactRow:
        """Rehydrate a serialized fact row."""
        return cls(kind=str(data["kind"]), payload=dict(data["payload"]))


@dataclass
class FileMetrics:
    """Collection of metrics for a single file."""

    file_path: Path
    language: str
    metrics: list[MetricResult]
    error: str | None = None
    facts: list[FactRow] = field(default_factory=list)

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
