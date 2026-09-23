"""Resolve current gates independently of a snapshot's historical defaults."""

from __future__ import annotations

from collections.abc import Callable
import operator
from pathlib import Path

from antipasta.cli.report.table_rows import TableRow
from antipasta.core.model.config import AntipastaConfig, ComparisonOperator, MetricConfig
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import check_metric_violation

_DEFAULT_FIELDS = {
    "cyclomatic_complexity": "max_cyclomatic_complexity",
    "cognitive_complexity": "max_cognitive_complexity",
    "maintainability_index": "min_maintainability_index",
    "halstead_volume": "max_halstead_volume",
    "halstead_difficulty": "max_halstead_difficulty",
    "halstead_effort": "max_halstead_effort",
}
_COUNT_GATES = frozenset({
    "narrative_mixed_functions",
    "narrator_budget_exceeded",
    "computer_budget_exceeded",
    "naming_antipatterns",
})


def _default_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    """Mirror engine defaults only when the language has no configured entry."""
    language = row.language.lower()
    if language not in {"python", "javascript", "typescript"}:
        return None
    if language != "python" and row.metric != "cyclomatic_complexity":
        return None
    field = _DEFAULT_FIELDS.get(row.metric)
    if field is None:
        return None
    comparison = ComparisonOperator.LE
    if row.metric == "maintainability_index":
        comparison = ComparisonOperator.GE
    return MetricConfig(
        type=MetricType(row.metric),
        threshold=getattr(config.defaults, field),
        comparison=comparison,
    )


def _language_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    if row.scope == "function" and row.metric.startswith("halstead_"):
        return None
    language = config.get_language_config(row.language)
    if language is None:
        return _default_gate(row, config)
    matching = {gate.type.value: gate for gate in language.metrics}
    gate = matching.get(row.metric)
    return gate if gate is not None and gate.enabled else None


def _graph_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    graph = config.import_graph
    if graph is None:
        return None
    if row.metric == "stable_dependencies_violations":
        return graph.stable_dependencies_config()
    if row.metric == "dependency_cycles" and graph.forbid_cycles:
        return graph.cycles_config()
    return None


def _narrative_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    if config.experimental is None:
        return None
    narrative = config.experimental.narrative
    if narrative is None:
        return None
    if row.metric in _COUNT_GATES:
        return narrative.count_gate(MetricType(row.metric))
    if row.metric == "name_clarity" and narrative.name_clarity_floor is not None:
        return narrative.clarity_gate()
    return None


def _duplication_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    duplication = config.duplication
    if row.metric != "duplication_ratio" or duplication is None:
        return None
    return duplication.ratio_gate() if duplication.max_ratio is not None else None


def _layering_gate(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    tree = config.tree_shape
    if row.metric != "layering_violations" or tree is None:
        return None
    return tree.layering_config() if tree.layers else None


def gate_for(row: TableRow, config: AntipastaConfig) -> MetricConfig | None:
    """Use the same gate sources and scope restrictions as the analysis pipeline."""
    if not row.project:
        return _language_gate(row, config)
    resolvers = (_graph_gate, _narrative_gate, _duplication_gate, _layering_gate)
    return next((gate for resolve in resolvers if (gate := resolve(row, config))), None)


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
