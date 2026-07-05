"""Plain-text rendering of a snapshot diff for the terminal.

Turns a :class:`~antipasta.core.store.snapshot_diff_types.SnapshotDiff` into the
delta summary printed by ``antipasta report --baseline``.  Pure formatting —
where the text goes (stdout vs stderr) is the command's decision.
"""

from __future__ import annotations

from antipasta.core.store.snapshot_diff import (
    DEFAULT_EPSILON,
    FileDelta,
    FunctionDelta,
    SnapshotDiff,
    ViolationRecord,
)


def format_diff_summary(
    snapshot_diff: SnapshotDiff, *, baseline_label: str, epsilon: float = DEFAULT_EPSILON
) -> str:
    """Format the full delta summary, worst regressions first."""
    header = f"=== Baseline diff vs {baseline_label} ==="
    if snapshot_diff.is_empty:
        return f"{header}\nNo differences above epsilon ({epsilon:g})."

    sections = [
        _format_file_churn(snapshot_diff),
        _format_violations("New violations", snapshot_diff.violation_changes.added),
        _format_violations("Resolved violations", snapshot_diff.violation_changes.removed),
        _format_functions(
            "Regressed functions (worst first, * = new violation)",
            snapshot_diff.regressions,
        ),
        _format_functions("Improved functions", snapshot_diff.improvements),
        _format_file_deltas(snapshot_diff.file_deltas, epsilon),
    ]
    return "\n".join([header, *(section for section in sections if section)])


def _fmt(value: float) -> str:
    """Compact numeric formatting (integers without trailing zeros)."""
    return f"{value:g}"


def _fmt_delta(value: float) -> str:
    """Signed compact numeric formatting."""
    return f"{value:+g}"


def _format_file_churn(snapshot_diff: SnapshotDiff) -> str:
    """The added/removed/changed file counts and the add/remove lists."""
    lines = [
        f"Files: {len(snapshot_diff.files_added)} added, "
        f"{len(snapshot_diff.files_removed)} removed, "
        f"{len(snapshot_diff.file_deltas)} changed"
    ]
    lines.extend(f"  + {path}" for path in snapshot_diff.files_added)
    lines.extend(f"  - {path}" for path in snapshot_diff.files_removed)
    return "\n".join(lines)


def _format_violations(title: str, records: list[ViolationRecord]) -> str:
    """One section of violation messages ('' when there are none)."""
    if not records:
        return ""
    lines = [f"{title} ({len(records)}):"]
    lines.extend(f"  {record.message}" for record in records)
    return "\n".join(lines)


def _format_functions(title: str, deltas: list[FunctionDelta]) -> str:
    """One section of per-function score changes ('' when there are none)."""
    if not deltas:
        return ""
    lines = [f"{title}:"]
    for fn in deltas:
        marker = "*" if fn.new_violation else " "
        location = fn.path if fn.line is None else f"{fn.path}:{fn.line}"
        details = ", ".join(
            f"{md.metric} {_fmt(md.old_value)}→{_fmt(md.new_value)}" for md in fn.metric_deltas
        )
        suffix = f"  ({details})" if details else ""
        lines.append(f"  {marker} {_fmt_delta(fn.score_delta)}  {fn.name}  {location}{suffix}")
    return "\n".join(lines)


def _format_file_deltas(file_deltas: list[FileDelta], epsilon: float) -> str:
    """One section of per-file metric deltas and function churn."""
    if not file_deltas:
        return ""
    lines = [f"File metric deltas (|Δ| > {epsilon:g}):"]
    for fd in file_deltas:
        parts = [
            f"{md.metric} {_fmt(md.old_value)}→{_fmt(md.new_value)} ({_fmt_delta(md.delta)})"
            for md in fd.metric_deltas
        ]
        parts.extend(f"function added: {name}" for name in fd.functions_added)
        parts.extend(f"function removed: {name}" for name in fd.functions_removed)
        lines.append(f"  {fd.path}: {', '.join(parts)}")
    return "\n".join(lines)
