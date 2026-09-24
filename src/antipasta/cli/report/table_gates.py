"""Resolve current gates independently of a snapshot's historical defaults."""

from __future__ import annotations

from collections.abc import Callable
import operator
from pathlib import Path

from antipasta.cli.report.table_rows import TableRow
from antipasta.core.model.config import AntipastaConfig, ComparisonOperator, MetricConfig
from antipasta.core.model.gates import language_gates, project_gates
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import check_metric_violation


def _language_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    """Function-scope Halstead rows are never gated; the rest follow the language's gates."""
    if row.scope == "function" and row.metric.startswith("halstead_"):
        return None
    return language_gates(config, row.language).get(row.metric)


def gate_for(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    """Use the same gate sources and scope restrictions as the analysis pipeline."""
    if not row.project:
        return _language_gate(row, config)
    return project_gates(config).get(row.metric)


def violates(row: TableRow, gate: MetricConfig | None) -> bool:
    if gate is None:
        return False
    metric = MetricResult(Path(row.subject), MetricType(row.metric), row.value)
    return check_metric_violation(metric, gate) is not None


def _distance(value: float, threshold: float) -> float:
    return abs(value - threshold)


_SEVERITY: dict[ComparisonOperator, Callable[[float, float], float]] = {
    ComparisonOperator.LE: operator.sub,
    ComparisonOperator.LT: operator.sub,
    ComparisonOperator.GE: lambda value, threshold: threshold - value,
    ComparisonOperator.GT: lambda value, threshold: threshold - value,
    ComparisonOperator.EQ: _distance,
    ComparisonOperator.NE: lambda value, threshold: -abs(value - threshold),
}


def severity(row: TableRow, gate: MetricConfig | None, direction: int) -> float:
    """Signed threshold-relative excess; zero thresholds use an absolute distance."""
    if gate is None:
        return direction * row.value
    distance = _SEVERITY[gate.comparison](row.value, gate.threshold)
    return distance / (abs(gate.threshold) or 1.0)
