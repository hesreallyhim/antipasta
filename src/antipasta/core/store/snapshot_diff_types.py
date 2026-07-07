"""Typed result structures for snapshot diffing.

These are the pure data carriers returned by
:func:`antipasta.core.store.snapshot_diff.diff`.  They hold *facts* about the drift
between two snapshots; presentation (terminal summary, HTML payload) lives
with the consumers.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Metric deltas with absolute value at or below this are treated as noise.
DEFAULT_EPSILON = 0.01

#: Metrics where larger values are better (regression = negative delta).
MIN_DIRECTION_METRICS = frozenset({"maintainability_index"})


@dataclass(frozen=True)
class MetricDelta:
    """One metric's change between baseline and current."""

    metric: str
    old_value: float
    new_value: float
    delta: float  # new_value - old_value

    @property
    def regressed(self) -> bool:
        """Whether the change is in the "worse" direction for this metric."""
        if self.metric in MIN_DIRECTION_METRICS:
            return self.delta < 0
        return self.delta > 0


@dataclass(frozen=True)
class FileDelta:
    """Changes observed within a file present in both snapshots."""

    path: str
    metric_deltas: list[MetricDelta]
    functions_added: list[str]
    functions_removed: list[str]


@dataclass(frozen=True)
class FunctionDelta:
    """Complexity-score change for a function present in both snapshots."""

    path: str
    name: str
    line: int | None  # line number in the *new* snapshot
    old_score: float
    new_score: float
    score_delta: float  # positive = worse
    metric_deltas: list[MetricDelta]
    new_violation: bool  # function violates a threshold now but did not before


@dataclass(frozen=True)
class ViolationRecord:
    """Identity of one threshold violation (line numbers ignored on purpose)."""

    path: str
    metric: str
    function: str | None
    message: str


@dataclass(frozen=True)
class ViolationChanges:
    """Violations that appeared in / disappeared from the current snapshot."""

    added: list[ViolationRecord]
    removed: list[ViolationRecord]


@dataclass(frozen=True)
class SnapshotDiff:
    """Full structural diff between two snapshots (old = baseline)."""

    files_added: list[str]
    files_removed: list[str]
    file_deltas: list[FileDelta]
    function_deltas: list[FunctionDelta]
    violation_changes: ViolationChanges
    warnings: list[str]

    @property
    def regressions(self) -> list[FunctionDelta]:
        """Functions that got worse, new violations first, worst delta first."""
        worse = [fd for fd in self.function_deltas if fd.score_delta > 0 or fd.new_violation]
        return sorted(worse, key=lambda fd: (not fd.new_violation, -fd.score_delta, fd.path))

    @property
    def improvements(self) -> list[FunctionDelta]:
        """Functions that got better, most improved first."""
        better = [fd for fd in self.function_deltas if fd.score_delta < 0 and not fd.new_violation]
        return sorted(better, key=lambda fd: (fd.score_delta, fd.path))

    @property
    def is_empty(self) -> bool:
        """True when the two snapshots show no measurable drift."""
        return not (
            self.files_added
            or self.files_removed
            or self.file_deltas
            or self.function_deltas
            or self.violation_changes.added
            or self.violation_changes.removed
        )
