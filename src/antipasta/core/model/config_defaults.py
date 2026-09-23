"""Bind inherited built-in gates to effective defaults without replacing explicit gates."""

from antipasta.core.model.config import AntipastaConfig

DEFAULT_GATE_FIELDS = {
    "cyclomatic_complexity": "max_cyclomatic_complexity",
    "cognitive_complexity": "max_cognitive_complexity",
    "maintainability_index": "min_maintainability_index",
    "halstead_volume": "max_halstead_volume",
    "halstead_difficulty": "max_halstead_difficulty",
    "halstead_effort": "max_halstead_effort",
}


def bind_default_gates(config: AntipastaConfig, sources: dict[str, str]) -> None:
    """Only the untouched built-in Python metric list follows merged defaults.

    Preset expansion and explicit metric lists supply authoritative values.
    Keeping the shipped list also preserves its enabled flags; deleting that
    list would enable the engine's cognitive gate on unconfigured projects.
    """
    key = "languages.python.metrics"
    if sources.get(key) != "defaults":
        return
    language = config.get_language_config("python")
    if language is None:
        return
    for metric in language.metrics:
        field = DEFAULT_GATE_FIELDS[metric.type.value]
        metric.threshold = float(getattr(config.defaults, field))
    providers = {
        sources.get(f"defaults.{field}", "defaults") for field in DEFAULT_GATE_FIELDS.values()
    }
    providers.discard("defaults")
    if providers:
        sources[key] = f"defaults (thresholds from {', '.join(sorted(providers))})"
