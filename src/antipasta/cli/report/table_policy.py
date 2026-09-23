"""Display taxonomy and direction policy for terminal snapshot tables.

Categories mirror the Category column in docs/supported_metrics.md. Keep the
mapping explicit so installed wheels never need a documentation checkout.
"""

from __future__ import annotations

CATEGORY_METRICS: dict[str, tuple[str, ...]] = {
    "Lines of code": (
        "lines_of_code",
        "logical_lines_of_code",
        "source_lines_of_code",
        "comment_lines",
        "blank_lines",
    ),
    "Complexity": (
        "cyclomatic_complexity",
        "halstead_volume",
        "halstead_difficulty",
        "halstead_effort",
        "halstead_time",
        "halstead_bugs",
        "function_statements",
        "cognitive_complexity",
        "function_arity",
    ),
    "SOLID": (
        "message_chain_depth",
        "boolean_flag_parameters",
        "global_state_reach",
        "lack_of_cohesion",
        "weighted_methods_per_class",
        "coupling_between_objects",
        "depth_of_inheritance_tree",
        "number_of_children",
        "directory_children",
        "efferent_coupling",
        "afferent_coupling",
        "instability",
        "dependency_cycles",
        "stable_dependencies_violations",
        "deferred_imports",
        "abstractness",
        "distance_from_main_sequence",
        "dependency_inversion",
        "layering_violations",
        "single_responsibility_index",
    ),
    "Maintainability": (
        "marker_density",
        "comment_density",
        "naming_antipatterns",
        "duplication_ratio",
        "clone_occurrences",
        "maintainability_index",
        "hotspot",
    ),
    "Test quality": (
        "assertions_per_test",
        "mock_call_assertions",
        "big_literal_assertions",
        "test_churn_ratio",
        "co_churn_multiplicity",
        "suite_redundancy_index",
        "blast_radius",
    ),
    "VCS": (
        "code_churn",
        "change_coupling",
    ),
    "Experimental": (
        "expression_flatness",
        "pipeline_linearity",
        "narrative_mixed_functions",
        "narrator_budget_exceeded",
        "computer_budget_exceeded",
        "step_down_ordering",
        "name_clarity",
    ),
}
CATEGORIES = tuple(CATEGORY_METRICS)
METRIC_CATEGORIES = {
    metric: category for category, metrics in CATEGORY_METRICS.items() for metric in metrics
}

# Higher is worse unless overridden here. None denotes a descriptive metric.
DIRECTIONS: dict[str, int | None] = {
    "maintainability_index": -1,
    "name_clarity": -1,
    "step_down_ordering": -1,
    "expression_flatness": -1,
    "pipeline_linearity": -1,
    "instability": None,
    "abstractness": None,
    "comment_density": None,
    "directory_children": None,
    "halstead_time": None,
    "halstead_bugs": None,
}
CLASS_METRICS = frozenset({
    "lack_of_cohesion",
    "weighted_methods_per_class",
    "coupling_between_objects",
    "depth_of_inheritance_tree",
    "number_of_children",
    "single_responsibility_index",
})
GROUP_METRICS = frozenset({"dependency_cycles", "clone_occurrences", "change_coupling"})
SUITE_METRICS = frozenset({"test_churn_ratio", "co_churn_multiplicity", "suite_redundancy_index"})
PROJECT_FILE_METRICS = frozenset({"duplication_ratio", "code_churn", "hotspot", "blast_radius"})
