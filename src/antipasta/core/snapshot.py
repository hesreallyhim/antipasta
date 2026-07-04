"""Snapshot builder for the report command.

Converts a list of :class:`FileReport` objects into a single JSON-serializable
dictionary (the "snapshot") that both the ``--format json`` output and the
offline HTML report consume.

The treemap node table is deliberately built here, in Python, as an explicit
``{id, parent, label, value}`` row set with a root node and every intermediate
directory present.  This is the mixed-depth-tree fix documented in
``docs/treemap_loc_fix.md``: the renderer (d3.stratify) must never see a node
whose parent is missing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from antipasta import __version__
from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.metrics import MetricResult
from antipasta.core.treemap import build_treemap_nodes
from antipasta.core.violations import FileReport, ProjectReport

# v2 (2026-07-04): adds the top-level "project" block (project-/directory-
# scoped reports from the derivation stage; empty until derivers register).
SCHEMA_VERSION = 2


#: ``details["type"]`` values that mark file-level aggregate rows emitted by
#: runners (they carry a function-count/aggregate, not a real function).
_AGGREGATE_ROW_TYPES = frozenset({"average", "file_maximum"})


def build_snapshot(
    reports: list[FileReport],
    config: AntipastaConfig,
    *,
    root: Path | None = None,
    summary: dict[str, Any] | None = None,
    project_reports: list[ProjectReport] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable snapshot of an analysis run.

    Args:
        reports: File reports produced by :class:`MetricAggregator`.
        config: The configuration the analysis ran with (used for thresholds
            and, when ``summary`` is not supplied, the summary computation).
        root: Directory the report paths should be shown relative to.
            Defaults to the current working directory.
        summary: Pre-computed summary (from ``execute_analysis``).  When
            omitted it is recomputed via ``MetricAggregator.generate_summary``.
        project_reports: Project-/directory-scoped reports from the
            derivation stage (empty until derivers register).

    Returns:
        The snapshot dictionary (see ``schema_version`` 2 layout).
    """
    root_path = (root or Path.cwd()).resolve()
    files = [
        _build_file_entry(report, root_path)
        for report in sorted(reports, key=lambda r: str(r.file_path))
    ]
    if summary is None:
        summary = MetricAggregator(config).generate_summary(reports)

    # Machine-neutral root when possible: snapshots get committed to git
    # (metrics history), and an absolute path would churn across machines.
    try:
        root_label = str(root_path.relative_to(Path.cwd()))
    except ValueError:
        root_label = str(root_path)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "root": root_label,
        "summary": summary,
        "thresholds": _build_thresholds(config),
        "language_coverage": _build_language_coverage(files),
        "files": files,
        "project": [report.to_dict() for report in (project_reports or [])],
        "treemap": build_treemap_nodes(files, root_label=root_path.name or str(root_path)),
    }


def _build_file_entry(report: FileReport, root: Path) -> dict[str, Any]:
    """Build the per-file snapshot entry."""
    return {
        "path": _relative_posix_path(report.file_path, root),
        "language": report.language,
        "error": report.error,
        "metrics": {
            metric.metric_type.value: metric.value
            for metric in report.metrics
            if metric.function_name is None
        },
        "violations": [violation.to_dict() for violation in report.violations],
        "functions": _group_functions(report.metrics),
    }


def _relative_posix_path(file_path: Path, root: Path) -> str:
    """Return ``file_path`` relative to ``root`` (POSIX separators) when possible."""
    try:
        return file_path.resolve().relative_to(root).as_posix()
    except ValueError:
        return file_path.as_posix()


def _function_identity(metric: MetricResult) -> tuple[str, str | None]:
    """Return ``(bare_name, qualified_name)`` for a per-function metric row.

    Runners disagree on naming: complexipy emits ``Class::method``, radon's
    cyclomatic rows emit ``method`` with the class in ``details.classname``,
    and radon's Halstead rows emit only the bare name.  Deriving both forms
    lets rows for the same function merge into one entry.
    """
    name = metric.function_name or ""
    if "::" in name:
        return name.rsplit("::", 1)[1], name
    details = metric.details or {}
    classname = details.get("classname")
    if classname:
        return name, f"{classname}::{name}"
    return name, None


def _select_per_function_rows(metrics: list[MetricResult]) -> list[MetricResult]:
    """Keep only real per-function rows (drop file-level aggregates)."""
    return [
        metric
        for metric in metrics
        if metric.function_name is not None
        and (metric.details or {}).get("type") not in _AGGREGATE_ROW_TYPES
    ]


def _index_qualified_names(rows: list[MetricResult]) -> dict[str, set[str]]:
    """Map each bare function name to the qualified forms seen for it."""
    qualified_by_bare: dict[str, set[str]] = {}
    for metric in rows:
        bare, qualified = _function_identity(metric)
        variants = qualified_by_bare.setdefault(bare, set())
        if qualified is not None:
            variants.add(qualified)
    return qualified_by_bare


def _resolve_group_key(
    metric: MetricResult, qualified_by_bare: dict[str, set[str]]
) -> tuple[str, str]:
    """Return ``(group_key, display_name)`` for a per-function metric row."""
    bare, qualified = _function_identity(metric)
    variants = qualified_by_bare[bare]
    if len(variants) <= 1:
        # Unambiguous: merge all runners' rows under the bare name and
        # display the qualified form when one runner provided it.
        return bare, next(iter(variants), bare)
    # Ambiguous (same bare name under several classes): split by qualified
    # form; unqualified rows stay under the bare name.
    key = qualified or bare
    return key, key


def _merge_metric_into_entry(entry: dict[str, Any], metric: MetricResult) -> None:
    """Fold one metric row into a grouped function entry (earliest line wins)."""
    if metric.line_number is not None and (
        entry["line"] is None or metric.line_number < entry["line"]
    ):
        entry["line"] = metric.line_number
    entry["metrics"][metric.metric_type.value] = metric.value


def _group_functions(metrics: list[MetricResult]) -> list[dict[str, Any]]:
    """Group per-function metric rows into one entry per function.

    Rows are grouped by bare function name unless a file contains the same
    bare name under multiple qualified forms (e.g. ``A::run`` and ``B::run``),
    in which case qualified rows split into their own entries.
    """
    rows = _select_per_function_rows(metrics)
    qualified_by_bare = _index_qualified_names(rows)

    functions: dict[str, dict[str, Any]] = {}
    for metric in rows:
        key, display = _resolve_group_key(metric, qualified_by_bare)
        entry = functions.setdefault(key, {"name": display, "line": None, "metrics": {}})
        _merge_metric_into_entry(entry, metric)

    return sorted(
        functions.values(),
        key=lambda f: (f["line"] is None, f["line"] or 0, f["name"]),
    )


def _build_thresholds(config: AntipastaConfig) -> dict[str, dict[str, Any]]:
    """Map metric types to their configured default threshold and direction.

    ``direction`` is ``"max"`` when values at or below the threshold are good
    and ``"min"`` when values at or above the threshold are good.
    """
    defaults = config.defaults
    return {
        "cyclomatic_complexity": {
            "threshold": float(defaults.max_cyclomatic_complexity),
            "direction": "max",
        },
        "cognitive_complexity": {
            "threshold": float(defaults.max_cognitive_complexity),
            "direction": "max",
        },
        "maintainability_index": {
            "threshold": float(defaults.min_maintainability_index),
            "direction": "min",
        },
        "halstead_volume": {
            "threshold": float(defaults.max_halstead_volume),
            "direction": "max",
        },
        "halstead_difficulty": {
            "threshold": float(defaults.max_halstead_difficulty),
            "direction": "max",
        },
        "halstead_effort": {
            "threshold": float(defaults.max_halstead_effort),
            "direction": "max",
        },
    }


def _build_language_coverage(files: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Compute which metric types were actually observed for each language.

    The HTML report uses this for honest per-language coverage labels: a
    metric a language's runners never produce must render neutral, not "good".
    """
    coverage: dict[str, set[str]] = {}
    for entry in files:
        seen = coverage.setdefault(entry["language"], set())
        seen.update(entry["metrics"])
        for function in entry["functions"]:
            seen.update(function["metrics"])
    return {language: sorted(metrics) for language, metrics in sorted(coverage.items())}


def collect_worst_functions(snapshot: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    """Rank functions by ``max(cyclomatic, cognitive)`` complexity, worst first.

    Functions with neither complexity metric are excluded.  Ties are broken
    by path/name for deterministic output.
    """
    rows: list[dict[str, Any]] = []
    for entry in snapshot["files"]:
        for function in entry["functions"]:
            cyclomatic = function["metrics"].get("cyclomatic_complexity")
            cognitive = function["metrics"].get("cognitive_complexity")
            candidates = [v for v in (cyclomatic, cognitive) if v is not None]
            if not candidates:
                continue
            rows.append(
                {
                    "score": max(candidates),
                    "cyclomatic": cyclomatic,
                    "cognitive": cognitive,
                    "name": function["name"],
                    "path": entry["path"],
                    "line": function["line"],
                }
            )

    rows.sort(key=lambda r: (-r["score"], r["path"], r["name"]))
    return rows[: limit if limit > 0 else len(rows)]


def format_worst_functions_table(snapshot: dict[str, Any], limit: int) -> str:
    """Format the worst-functions ranking as an aligned plain-text table."""
    rows = collect_worst_functions(snapshot, limit)
    if not rows:
        return "No function-level complexity data available."

    def fmt(value: float | None) -> str:
        return "-" if value is None else f"{value:g}"

    header = ("#", "score", "cyc", "cog", "function", "location")
    body = [
        (
            str(rank),
            fmt(row["score"]),
            fmt(row["cyclomatic"]),
            fmt(row["cognitive"]),
            row["name"],
            f"{row['path']}:{row['line']}" if row["line"] is not None else row["path"],
        )
        for rank, row in enumerate(rows, start=1)
    ]
    widths = [max(len(header[i]), *(len(line[i]) for line in body)) for i in range(len(header))]
    lines = [
        "  ".join(header[i].ljust(widths[i]) for i in range(len(header))),
        "  ".join("-" * widths[i] for i in range(len(header))),
    ]
    lines.extend("  ".join(line[i].ljust(widths[i]) for i in range(len(header))) for line in body)
    return "\n".join(lines)
