"""Plain terminal overview built solely from the public snapshot shape."""

from __future__ import annotations

from typing import Any

from antipasta.cli.report.table_aggregate import Aggregate, aggregate
from antipasta.cli.report.table_policy import CATEGORIES, METRIC_CATEGORIES
from antipasta.cli.report.table_rows import TableRow, collect_rows
from antipasta.core.model.config import AntipastaConfig


def _numbers(measures: dict[str, float]) -> str:
    return ", ".join(f"{name}={value:g}" for name, value in measures.items())


def _delta(current: Aggregate | None, previous: Aggregate | None) -> str:
    if current is None:
        return "removed"
    if previous is None:
        return "new"
    return ", ".join(
        f"{name}={value - previous.measures[name]:+g}"
        for name, value in current.measures.items()
        if name in previous.measures
    )


def _line(
    key: tuple[str, str],
    current: Aggregate | None,
    previous: Aggregate | None,
    show_delta: bool,
) -> str:
    metric, scope = key
    measures = _numbers(current.measures) if current else "no current rows"
    offenders = "; ".join(current.offenders) if current else ""
    columns = [f"{metric} [{scope}]", measures, offenders or "-"]
    if show_delta:
        columns.append(_delta(current, previous))
    return " | ".join(columns)


def _aggregate_rows(
    rows: dict[tuple[str, str], list[TableRow]],
    config: AntipastaConfig,
) -> dict[tuple[str, str], Aggregate]:
    return {key: aggregate(values, config) for key, values in rows.items()}


def _category(key: tuple[str, str]) -> str:
    return METRIC_CATEGORIES.get(key[0], "Other")


def _footer(snapshot: dict[str, Any], fail_on: bool) -> str:
    count = snapshot.get("summary", {}).get("total_violations")
    if count is None:
        entries = [*snapshot.get("files", []), *snapshot.get("project", [])]
        count = sum(len(entry.get("violations", [])) for entry in entries)
    text = f"Violations: {count}"
    if fail_on:
        status = 2 if count else 0
        if any(entry.get("error") for entry in snapshot.get("files", [])):
            status = 1
        text += f" | Exit status: {status}"
    return text


def format_snapshot_table(
    snapshot: dict[str, Any],
    config: AntipastaConfig,
    *,
    baseline: dict[str, Any] | None = None,
    fail_on: bool = False,
) -> str:
    """Render scope-separated aggregates using current gates for both snapshots.

    Missing metric/scope groups are explicitly marked new or removed: absence
    is never treated as a zero measurement. Historical violation lists and
    default-threshold metadata do not participate in aggregate comparisons.
    """
    current = _aggregate_rows(collect_rows(snapshot), config)
    previous = _aggregate_rows(collect_rows(baseline or {}), config)
    keys = sorted(current.keys() | previous.keys())
    sections = []
    for category in (*CATEGORIES, "Other"):
        if category == "Experimental" and not config.experimental_enabled("narrative"):
            continue
        selected = [key for key in keys if _category(key) == category]
        if selected:
            sections.append(_section(category, selected, current, previous, baseline is not None))
    sections.append(_footer(snapshot, fail_on))
    return "\n\n".join(sections)


def _section(
    category: str,
    keys: list[tuple[str, str]],
    current: dict[tuple[str, str], Aggregate],
    previous: dict[tuple[str, str], Aggregate],
    show_delta: bool,
) -> str:
    header = "Metric [scope] | Measures | Offenders / largest group members"
    if show_delta:
        header += " | Delta"
    lines = [category, header]
    lines.extend(_line(key, current.get(key), previous.get(key), show_delta) for key in keys)
    return "\n".join(lines)
