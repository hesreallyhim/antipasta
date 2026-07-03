"""Pure diff logic between two report snapshots.

``diff`` compares a baseline ("old") snapshot against a current ("new") one —
both in the ``schema_version`` 1 layout produced by
:mod:`antipasta.core.snapshot` — and returns a typed
:class:`~antipasta.core.snapshot_diff_types.SnapshotDiff`.

Design constraints:

* **Pure**: no I/O.  Schema drift (a differing ``schema_version``) is recorded
  in ``SnapshotDiff.warnings``; the CLI decides where to print it.
* **Tolerant**: every snapshot key is read with defaults, non-numeric metric
  values are skipped, and entries missing a ``path`` are ignored, so a
  best-effort diff is produced even across schema drift.
* **Direction-aware**: for metrics where higher is better (maintainability
  index) a *negative* delta is the regression.
"""

from __future__ import annotations

from typing import Any

from antipasta.core.snapshot_diff_types import (
    DEFAULT_EPSILON,
    FileDelta,
    FunctionDelta,
    MetricDelta,
    SnapshotDiff,
    ViolationChanges,
    ViolationRecord,
)

__all__ = [
    "DEFAULT_EPSILON",
    "FileDelta",
    "FunctionDelta",
    "MetricDelta",
    "SnapshotDiff",
    "ViolationChanges",
    "ViolationRecord",
    "diff",
]

#: Metrics feeding the per-function complexity score (mirrors the report UI).
_SCORE_METRICS = ("cyclomatic_complexity", "cognitive_complexity")


def diff(
    old: dict[str, Any], new: dict[str, Any], *, epsilon: float = DEFAULT_EPSILON
) -> SnapshotDiff:
    """Diff two snapshots; ``old`` is the baseline, ``new`` the current run."""
    old_files = _index_files(old)
    new_files = _index_files(new)

    file_deltas: list[FileDelta] = []
    function_deltas: list[FunctionDelta] = []
    for path in sorted(old_files.keys() & new_files.keys()):
        file_delta, fn_deltas = _diff_file(path, old_files[path], new_files[path], epsilon)
        if file_delta is not None:
            file_deltas.append(file_delta)
        function_deltas.extend(fn_deltas)
    function_deltas.sort(key=lambda fd: (-fd.score_delta, fd.path, fd.name))

    return SnapshotDiff(
        files_added=sorted(new_files.keys() - old_files.keys()),
        files_removed=sorted(old_files.keys() - new_files.keys()),
        file_deltas=file_deltas,
        function_deltas=function_deltas,
        violation_changes=_diff_violations(old_files, new_files),
        warnings=_schema_warnings(old, new),
    )


def _schema_warnings(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Warn (once) when the two snapshots use different schema versions."""
    old_schema = old.get("schema_version")
    new_schema = new.get("schema_version")
    if old_schema == new_schema:
        return []
    return [
        f"baseline snapshot has schema_version {old_schema!r} but the current "
        f"snapshot has {new_schema!r}; diffing the fields that match"
    ]


def _index_files(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index a snapshot's file entries by path, skipping malformed entries."""
    files = snapshot.get("files") or []
    return {
        entry["path"]: entry
        for entry in files
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }


def _numeric_metrics(entry: dict[str, Any]) -> dict[str, float]:
    """Extract the numeric metric values from a file or function entry."""
    metrics = entry.get("metrics") or {}
    return {
        key: float(value)
        for key, value in metrics.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }


def _diff_metrics(
    old_entry: dict[str, Any], new_entry: dict[str, Any], epsilon: float
) -> list[MetricDelta]:
    """Deltas for metrics present (and numeric) in both entries, above epsilon."""
    old_metrics = _numeric_metrics(old_entry)
    new_metrics = _numeric_metrics(new_entry)
    deltas = [
        MetricDelta(
            metric=key,
            old_value=old_metrics[key],
            new_value=new_metrics[key],
            delta=new_metrics[key] - old_metrics[key],
        )
        for key in sorted(old_metrics.keys() & new_metrics.keys())
    ]
    return [d for d in deltas if abs(d.delta) > epsilon]


def _index_functions(entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index a file entry's functions by name, skipping malformed rows."""
    functions = entry.get("functions") or []
    return {
        fn["name"]: fn
        for fn in functions
        if isinstance(fn, dict) and isinstance(fn.get("name"), str)
    }


def _complexity_score(fn: dict[str, Any]) -> float | None:
    """``max(cyclomatic, cognitive)`` — the report's function ranking score."""
    metrics = _numeric_metrics(fn)
    values = [metrics[key] for key in _SCORE_METRICS if key in metrics]
    return max(values) if values else None


def _bare_name(name: str) -> str:
    """Strip any ``Class::`` qualification from a function name."""
    return name.rsplit("::", 1)[-1]


def _violating_functions(entry: dict[str, Any]) -> set[str]:
    """Bare names of functions with at least one violation in this file entry."""
    return {
        _bare_name(violation["function"])
        for violation in entry.get("violations") or []
        if isinstance(violation, dict) and isinstance(violation.get("function"), str)
    }


def _diff_file(
    path: str,
    old_entry: dict[str, Any],
    new_entry: dict[str, Any],
    epsilon: float,
) -> tuple[FileDelta | None, list[FunctionDelta]]:
    """Diff one file present in both snapshots.

    Returns the file-level delta (or ``None`` when nothing changed) and the
    per-function deltas for functions present on both sides.
    """
    metric_deltas = _diff_metrics(old_entry, new_entry, epsilon)
    old_functions = _index_functions(old_entry)
    new_functions = _index_functions(new_entry)
    functions_added = sorted(new_functions.keys() - old_functions.keys())
    functions_removed = sorted(old_functions.keys() - new_functions.keys())

    old_violating = _violating_functions(old_entry)
    new_violating = _violating_functions(new_entry)
    function_deltas = []
    for name in sorted(old_functions.keys() & new_functions.keys()):
        newly_violating = _bare_name(name) in new_violating - old_violating
        fn_delta = _diff_function(
            path, old_functions[name], new_functions[name], newly_violating, epsilon
        )
        if fn_delta is not None:
            function_deltas.append(fn_delta)

    file_delta = None
    if metric_deltas or functions_added or functions_removed:
        file_delta = FileDelta(
            path=path,
            metric_deltas=metric_deltas,
            functions_added=functions_added,
            functions_removed=functions_removed,
        )
    return file_delta, function_deltas


def _diff_function(
    path: str,
    old_fn: dict[str, Any],
    new_fn: dict[str, Any],
    new_violation: bool,
    epsilon: float,
) -> FunctionDelta | None:
    """Delta for one function present in both snapshots.

    ``None`` when the function has no comparable complexity score on both
    sides, or when the score change is within epsilon and no new violation
    appeared.
    """
    old_score = _complexity_score(old_fn)
    new_score = _complexity_score(new_fn)
    if old_score is None or new_score is None:
        return None
    score_delta = new_score - old_score
    if abs(score_delta) <= epsilon and not new_violation:
        return None
    line = new_fn.get("line")
    return FunctionDelta(
        path=path,
        name=str(new_fn.get("name")),
        line=line if isinstance(line, int) else None,
        old_score=old_score,
        new_score=new_score,
        score_delta=score_delta,
        metric_deltas=_diff_metrics(old_fn, new_fn, epsilon),
        new_violation=new_violation,
    )


def _violation_records(files: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """Index violations by ``(path, metric, function)``, mapping to messages.

    Line numbers are deliberately not part of the identity: code above a
    function moving it down the file must not read as a new violation.
    """
    records: dict[tuple[str, str, str], str] = {}
    for path, entry in files.items():
        for violation in entry.get("violations") or []:
            if not isinstance(violation, dict):
                continue
            key = (path, str(violation.get("type")), str(violation.get("function")))
            records[key] = str(violation.get("message"))
    return records


def _diff_violations(
    old_files: dict[str, dict[str, Any]], new_files: dict[str, dict[str, Any]]
) -> ViolationChanges:
    """Violations added and removed, including those in added/removed files."""
    old_records = _violation_records(old_files)
    new_records = _violation_records(new_files)
    return ViolationChanges(
        added=_to_records(new_records.keys() - old_records.keys(), new_records),
        removed=_to_records(old_records.keys() - new_records.keys(), old_records),
    )


def _to_records(
    keys: set[tuple[str, str, str]], source: dict[tuple[str, str, str], str]
) -> list[ViolationRecord]:
    """Materialize sorted :class:`ViolationRecord` rows for the given keys."""
    return [
        ViolationRecord(
            path=path,
            metric=metric,
            function=None if function == "None" else function,
            message=source[(path, metric, function)],
        )
        for path, metric, function in sorted(keys)
    ]
