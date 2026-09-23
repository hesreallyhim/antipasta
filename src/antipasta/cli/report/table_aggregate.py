"""Scope-preserving aggregates and stable offender ranking."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import starmap
from statistics import median

from antipasta.cli.report.table_gates import gate_for, severity, violates
from antipasta.cli.report.table_policy import DIRECTIONS
from antipasta.cli.report.table_rows import TableRow
from antipasta.core.model.config import AntipastaConfig, MetricConfig


@dataclass(frozen=True)
class Aggregate:
    """Displayed numeric measures and their selected unit labels."""

    measures: dict[str, float]
    offenders: tuple[str, ...] = ()


def _offenders(
    evaluated: list[tuple[TableRow, MetricConfig | None]], direction: int
) -> tuple[str, ...]:
    gated = any(gate is not None for _, gate in evaluated)
    candidates = evaluated
    if gated:
        candidates = [(row, gate) for row, gate in evaluated if violates(row, gate)]
    ranked = sorted(
        candidates,
        key=lambda item: (-severity(item[0], item[1], direction), item[0].subject, item[0].value),
    )
    return tuple(f"{row.subject} ({row.value:g})" for row, _ in ranked[:3])


def _group_aggregate(rows: list[TableRow]) -> Aggregate:
    largest = min(rows, key=lambda row: (-row.value, row.subject))
    members = ", ".join(largest.members) or largest.subject
    return Aggregate({"groups": float(len(rows)), "largest": largest.value}, (members,))


def _descriptive(values: list[float]) -> Aggregate:
    return Aggregate({
        "units": float(len(values)),
        "min": min(values),
        "median": float(median(values)),
        "max": max(values),
    })


def aggregate(rows: list[TableRow], config: AntipastaConfig) -> Aggregate:
    """Compute exactly the measures displayed, for either current or old values."""
    first = rows[0]
    if first.scope == "group":
        return _group_aggregate(rows)
    if first.scope == "suite":
        return Aggregate({"value": first.value})
    values = [row.value for row in rows]
    direction = DIRECTIONS.get(first.metric, 1)
    if direction is None:
        return _descriptive(values)
    evaluated = [(row, gate_for(row, config)) for row in rows]
    measures = {"units": float(len(rows))}
    if any(gate is not None for _, gate in evaluated):
        measures["over"] = float(sum(starmap(violates, evaluated)))
    measures["worst"] = max(values) if direction > 0 else min(values)
    return Aggregate(measures, _offenders(evaluated, direction))
