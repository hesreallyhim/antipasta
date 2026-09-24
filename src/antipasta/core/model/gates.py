"""Resolve the gates that apply to a language or to project-level metrics.

The engine, the terminal table, and the snapshot embedded in the HTML report
must agree on which thresholds are in force. This module is the single place
that answers "which ``MetricConfig`` gates a given metric?" so the three
consumers cannot drift.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from antipasta.core.model.config import (
    AntipastaConfig,
    ComparisonOperator,
    LanguageConfig,
    MetricConfig,
)
from antipasta.core.model.detector import Language
from antipasta.core.model.metrics import MetricType

#: Narrative count metrics that share one configured gate.
NARRATIVE_COUNT_GATES = frozenset({
    "narrative_mixed_functions",
    "narrator_budget_exceeded",
    "computer_budget_exceeded",
    "naming_antipatterns",
})


def default_language_config(config: AntipastaConfig, language: Language) -> LanguageConfig:
    """Build the built-in gate list for a language with no configured entry.

    Python receives every default gate. JavaScript and TypeScript receive
    cyclomatic complexity only: lizard produces nothing else, so any other
    gate would silently never fire.
    """
    defaults = config.defaults
    metrics: list[MetricConfig] = []
    if language == Language.PYTHON:
        metrics = [
            MetricConfig(
                type=MetricType.CYCLOMATIC_COMPLEXITY,
                threshold=defaults.max_cyclomatic_complexity,
                comparison=ComparisonOperator.LE,
            ),
            MetricConfig(
                type=MetricType.MAINTAINABILITY_INDEX,
                threshold=defaults.min_maintainability_index,
                comparison=ComparisonOperator.GE,
            ),
            MetricConfig(
                type=MetricType.HALSTEAD_VOLUME,
                threshold=defaults.max_halstead_volume,
                comparison=ComparisonOperator.LE,
            ),
            MetricConfig(
                type=MetricType.HALSTEAD_DIFFICULTY,
                threshold=defaults.max_halstead_difficulty,
                comparison=ComparisonOperator.LE,
            ),
            MetricConfig(
                type=MetricType.HALSTEAD_EFFORT,
                threshold=defaults.max_halstead_effort,
                comparison=ComparisonOperator.LE,
            ),
            MetricConfig(
                type=MetricType.COGNITIVE_COMPLEXITY,
                threshold=defaults.max_cognitive_complexity,
                comparison=ComparisonOperator.LE,
            ),
        ]
    elif language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        metrics = [
            MetricConfig(
                type=MetricType.CYCLOMATIC_COMPLEXITY,
                threshold=defaults.max_cyclomatic_complexity,
                comparison=ComparisonOperator.LE,
            ),
        ]
    return LanguageConfig(name=language.value, metrics=metrics)


def language_config_for(config: AntipastaConfig, language: str) -> LanguageConfig | None:
    """The configured entry for ``language``, or the built-in list for known languages."""
    configured = config.get_language_config(language)
    if configured is not None:
        return configured
    try:
        known = Language(language.lower())
    except ValueError:
        return None
    return default_language_config(config, known)


def language_gates(config: AntipastaConfig, language: str) -> dict[str, MetricConfig]:
    """Enabled gates for a language, keyed by metric name."""
    entry = language_config_for(config, language)
    if entry is None:
        return {}
    return {gate.type.value: gate for gate in entry.metrics if gate.enabled}


def project_gates(config: AntipastaConfig) -> dict[str, MetricConfig]:
    """Gates for project-scope metrics: import graph, narrative, duplication, layering."""
    gates: dict[str, MetricConfig] = {}
    graph = config.import_graph
    if graph is not None:
        gates["stable_dependencies_violations"] = graph.stable_dependencies_config()
        if graph.forbid_cycles:
            gates["dependency_cycles"] = graph.cycles_config()
    narrative = config.experimental.narrative if config.experimental is not None else None
    if narrative is not None:
        for metric in sorted(NARRATIVE_COUNT_GATES):
            gates[metric] = narrative.count_gate(MetricType(metric))
        if narrative.name_clarity_floor is not None:
            gates["name_clarity"] = narrative.clarity_gate()
    duplication = config.duplication
    if duplication is not None and duplication.max_ratio is not None:
        gates["duplication_ratio"] = duplication.ratio_gate()
    tree = config.tree_shape
    if tree is not None and tree.layers:
        gates["layering_violations"] = tree.layering_config()
    return gates


def _serialize(gate: MetricConfig) -> dict[str, Any]:
    return {"threshold": float(gate.threshold), "comparison": gate.comparison.value}


def resolve_gates(config: AntipastaConfig, languages: Iterable[str]) -> dict[str, Any]:
    """JSON-serializable view of every gate in force for a run.

    ``languages`` are the languages observed in the analyzed files; each maps
    to its enabled gates. ``project`` holds the project-scope gates.
    """
    return {
        "languages": {
            language: {
                metric: _serialize(gate)
                for metric, gate in language_gates(config, language).items()
            }
            for language in sorted(set(languages))
        },
        "project": {metric: _serialize(gate) for metric, gate in project_gates(config).items()},
    }
