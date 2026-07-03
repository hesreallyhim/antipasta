"""Baseline payload assembly for the HTML report's "vs baseline" mode.

Converts a :class:`~antipasta.core.snapshot_diff_types.SnapshotDiff` into the
JSON-serializable ``baseline`` object embedded in the report data.  The
renderer uses it for delta tile coloring, the regressions table, and the meta
line naming the baseline.
"""

from __future__ import annotations

from typing import Any

from antipasta.core.snapshot_diff import FunctionDelta, SnapshotDiff


def build_baseline_payload(
    snapshot_diff: SnapshotDiff, old: dict[str, Any], *, label: str
) -> dict[str, Any]:
    """Build the ``baseline`` object embedded in the HTML report data.

    Args:
        snapshot_diff: Diff of the baseline against the current snapshot.
        old: The baseline snapshot (for its generation metadata).
        label: Display name for the baseline (typically the file name).
    """
    return {
        "label": label,
        "generated_at": old.get("generated_at"),
        "tool_version": old.get("tool_version"),
        "files_added": list(snapshot_diff.files_added),
        "files_removed": list(snapshot_diff.files_removed),
        "file_deltas": {
            fd.path: {md.metric: md.delta for md in fd.metric_deltas}
            for fd in snapshot_diff.file_deltas
        },
        "regressions": [_function_row(fd) for fd in snapshot_diff.regressions],
        "improvements": [_function_row(fd) for fd in snapshot_diff.improvements],
        "violations_added": len(snapshot_diff.violation_changes.added),
        "violations_removed": len(snapshot_diff.violation_changes.removed),
    }


def _function_row(fn: FunctionDelta) -> dict[str, Any]:
    """One regressions/improvements table row."""
    return {
        "path": fn.path,
        "name": fn.name,
        "line": fn.line,
        "old_score": fn.old_score,
        "new_score": fn.new_score,
        "score_delta": fn.score_delta,
        "new_violation": fn.new_violation,
        "deltas": {
            md.metric: {"old": md.old_value, "new": md.new_value, "delta": md.delta}
            for md in fn.metric_deltas
        },
    }
