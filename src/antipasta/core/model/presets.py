"""Preset registry for coarse antipasta configuration bundles."""

from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
from typing import Any, Final, cast


class PresetName(StrEnum):
    """Named configuration presets."""

    BALANCED = "balanced"
    READABLE = "readable"
    COMPACT = "compact"
    ARCHITECTURE = "architecture"
    TESTING = "testing"


_PROFILES: Final[frozenset[str]] = frozenset({"extreme", "standard", "relaxed"})
_DEFAULT_IGNORE_PATTERNS: Final[list[str]] = ["**/test_*.py", "**/*_test.py", "**/tests/**"]
_LANGUAGE_EXTENSIONS: Final[dict[str, list[str]]] = {
    "python": [".py"],
    "javascript": [".js", ".mjs", ".cjs", ".jsx"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
}
_PROJECT_BLOCKS: Final[frozenset[str]] = frozenset({
    "tree_shape",
    "import_graph",
    "narrative",
    "duplication",
})


PRESET_DEFINITIONS: Final[dict[PresetName, dict[str, Any]]] = {
    PresetName.BALANCED: {
        "description": "Default adoption gates for broadly accepted complexity metrics.",
        "ignore_patterns": _DEFAULT_IGNORE_PATTERNS,
        "languages": {
            "python": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 8, "standard": 10, "relaxed": 12},
                    "comparison": "<=",
                },
                {
                    "type": "cognitive_complexity",
                    "threshold": {"extreme": 10, "standard": 15, "relaxed": 20},
                    "comparison": "<=",
                },
                {
                    "type": "maintainability_index",
                    "threshold": {"extreme": 60, "standard": 50, "relaxed": 40},
                    "comparison": ">=",
                },
                {
                    "type": "halstead_volume",
                    "threshold": {"extreme": 700, "standard": 1000, "relaxed": 1500},
                    "comparison": "<=",
                },
                {
                    "type": "halstead_difficulty",
                    "threshold": {"extreme": 8, "standard": 10, "relaxed": 12},
                    "comparison": "<=",
                },
                {
                    "type": "halstead_effort",
                    "threshold": {"extreme": 7000, "standard": 10000, "relaxed": 15000},
                    "comparison": "<=",
                },
            ],
            "javascript": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 8, "standard": 10, "relaxed": 12},
                    "comparison": "<=",
                }
            ],
            "typescript": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 8, "standard": 10, "relaxed": 12},
                    "comparison": "<=",
                }
            ],
        },
    },
    PresetName.READABLE: {
        "description": "Compose-method and local readability gates.",
        "ignore_patterns": _DEFAULT_IGNORE_PATTERNS,
        "languages": {
            "python": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 6, "standard": 8, "relaxed": 10},
                    "comparison": "<=",
                },
                {
                    "type": "cognitive_complexity",
                    "threshold": {"extreme": 8, "standard": 12, "relaxed": 15},
                    "comparison": "<=",
                },
                {
                    "type": "message_chain_depth",
                    "threshold": {"extreme": 2, "standard": 2, "relaxed": 3},
                    "comparison": "<=",
                },
                {
                    "type": "boolean_flag_parameters",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "exception_discipline",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "global_state_reach",
                    "threshold": {"extreme": 0, "standard": 1, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "function_statements",
                    "threshold": {"extreme": 8, "standard": 12, "relaxed": 16},
                    "comparison": "<=",
                },
            ],
            "javascript": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 6, "standard": 8, "relaxed": 10},
                    "comparison": "<=",
                },
                {
                    "type": "message_chain_depth",
                    "threshold": {"extreme": 2, "standard": 2, "relaxed": 3},
                    "comparison": "<=",
                },
                {
                    "type": "boolean_flag_parameters",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "exception_discipline",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "global_state_reach",
                    "threshold": {"extreme": 0, "standard": 1, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "function_statements",
                    "threshold": {"extreme": 8, "standard": 12, "relaxed": 16},
                    "comparison": "<=",
                },
            ],
            "typescript": [
                {
                    "type": "cyclomatic_complexity",
                    "threshold": {"extreme": 6, "standard": 8, "relaxed": 10},
                    "comparison": "<=",
                },
                {
                    "type": "message_chain_depth",
                    "threshold": {"extreme": 2, "standard": 2, "relaxed": 3},
                    "comparison": "<=",
                },
                {
                    "type": "boolean_flag_parameters",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "exception_discipline",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "global_state_reach",
                    "threshold": {"extreme": 0, "standard": 1, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "function_statements",
                    "threshold": {"extreme": 8, "standard": 12, "relaxed": 16},
                    "comparison": "<=",
                },
            ],
        },
        "narrative": {
            "narrator_step_budget": {"extreme": 7, "standard": 9, "relaxed": 11},
            "computer_statement_budget": {"extreme": 8, "standard": 12, "relaxed": 16},
            "computer_nesting_budget": {"extreme": 1, "standard": 1, "relaxed": 2},
            "name_clarity_floor": {"extreme": 0.75, "standard": 0.65, "relaxed": 0.60},
        },
    },
    PresetName.COMPACT: {
        "description": "Counterweight gates for size and duplication.",
        "ignore_patterns": _DEFAULT_IGNORE_PATTERNS,
        "languages": {
            "python": [
                {
                    "type": "source_lines_of_code",
                    "threshold": {"extreme": 250, "standard": 400, "relaxed": 600},
                    "comparison": "<=",
                },
                {
                    "type": "logical_lines_of_code",
                    "threshold": {"extreme": 200, "standard": 300, "relaxed": 450},
                    "comparison": "<=",
                },
            ],
            "javascript": [
                {
                    "type": "source_lines_of_code",
                    "threshold": {"extreme": 250, "standard": 400, "relaxed": 600},
                    "comparison": "<=",
                },
                {
                    "type": "logical_lines_of_code",
                    "threshold": {"extreme": 200, "standard": 300, "relaxed": 450},
                    "comparison": "<=",
                },
            ],
            "typescript": [
                {
                    "type": "source_lines_of_code",
                    "threshold": {"extreme": 250, "standard": 400, "relaxed": 600},
                    "comparison": "<=",
                },
                {
                    "type": "logical_lines_of_code",
                    "threshold": {"extreme": 200, "standard": 300, "relaxed": 450},
                    "comparison": "<=",
                },
            ],
        },
        "duplication": {
            "normalize_local_names": True,
            "normalize_constants": True,
            "min_count": 2,
            "max_ratio": {"extreme": 0.04, "standard": 0.08, "relaxed": 0.12},
        },
    },
    PresetName.ARCHITECTURE: {
        "description": "Project-structure gates for fan-out and imports.",
        "ignore_patterns": _DEFAULT_IGNORE_PATTERNS,
        "tree_shape": {
            "fan_out_min": {"extreme": 2, "standard": 2, "relaxed": 1},
            "fan_out_max": {"extreme": 5, "standard": 7, "relaxed": 10},
        },
        "import_graph": {
            "forbid_cycles": True,
            "max_stable_dependencies_violations": {"extreme": 0, "standard": 0, "relaxed": 2},
        },
    },
    PresetName.TESTING: {
        "description": "Test-suite maintainability gates.",
        "ignore_patterns": [],
        "languages": {
            "python": [
                {
                    "type": "assertions_per_test",
                    "threshold": {"extreme": 3, "standard": 5, "relaxed": 8},
                    "comparison": "<=",
                },
                {
                    "type": "mock_call_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "big_literal_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
            ],
            "javascript": [
                {
                    "type": "assertions_per_test",
                    "threshold": {"extreme": 3, "standard": 5, "relaxed": 8},
                    "comparison": "<=",
                },
                {
                    "type": "mock_call_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "big_literal_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
            ],
            "typescript": [
                {
                    "type": "assertions_per_test",
                    "threshold": {"extreme": 3, "standard": 5, "relaxed": 8},
                    "comparison": "<=",
                },
                {
                    "type": "mock_call_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
                {
                    "type": "big_literal_assertions",
                    "threshold": {"extreme": 0, "standard": 0, "relaxed": 1},
                    "comparison": "<=",
                },
            ],
        },
    },
}

PRESET_DESCRIPTIONS: Final[dict[PresetName, str]] = {
    preset: str(definition["description"]) for preset, definition in PRESET_DEFINITIONS.items()
}


def preset_choices() -> list[str]:
    """Return preset names in CLI/display order."""
    return [preset.value for preset in PresetName]


def expand_preset_config(data: dict[str, Any]) -> dict[str, Any]:
    """Merge the selected preset into raw config data.

    The merge intentionally treats caller-provided values as authoritative.
    Presets fill missing scalar blocks, append missing language metrics, and
    recursively fill missing keys in project-level config blocks.
    """
    preset_value = data.get("preset")
    if preset_value in (None, ""):
        return data
    try:
        preset = PresetName(str(preset_value))
    except ValueError:
        return data

    profile = _profile_name(data.get("profile"))
    expanded = cast("dict[str, Any]", _plain_value(data))
    add_missing_languages = "languages" not in expanded
    preset_data = _materialize_preset(PRESET_DEFINITIONS[preset], profile)
    _merge_missing(expanded, preset_data)
    _merge_languages(
        expanded,
        preset_data.get("languages", []),
        add_missing_languages=add_missing_languages,
    )
    return expanded


def _plain_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True, mode="json")
    if isinstance(value, dict):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_value(item) for item in value]
    return deepcopy(value)


def _profile_name(value: Any) -> str:
    profile = str(value or "standard")
    return profile if profile in _PROFILES else "standard"


def _materialize_preset(definition: dict[str, Any], profile: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if "ignore_patterns" in definition:
        data["ignore_patterns"] = deepcopy(definition["ignore_patterns"])
    if "languages" in definition:
        data["languages"] = [
            _materialize_language(language_name, metrics, profile)
            for language_name, metrics in definition["languages"].items()
        ]
    for block_name in _PROJECT_BLOCKS:
        if block_name in definition:
            data[block_name] = _resolve_profile_values(definition[block_name], profile)
    return data


def _materialize_language(
    language_name: str,
    metrics: list[dict[str, Any]],
    profile: str,
) -> dict[str, Any]:
    return {
        "name": language_name,
        "extensions": deepcopy(_LANGUAGE_EXTENSIONS[language_name]),
        "metrics": [_resolve_profile_values(metric, profile) for metric in metrics],
    }


def _resolve_profile_values(value: Any, profile: str) -> Any:
    if isinstance(value, dict):
        keys = set(value)
        if keys <= _PROFILES and "standard" in keys:
            return deepcopy(value[profile if profile in value else "standard"])
        return {key: _resolve_profile_values(item, profile) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_profile_values(item, profile) for item in value]
    return deepcopy(value)


def _merge_missing(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, source_value in source.items():
        if key == "languages":
            continue
        if key not in target:
            target[key] = deepcopy(source_value)
            continue
        target_value = target[key]
        if isinstance(target_value, dict) and isinstance(source_value, dict):
            _merge_missing(target_value, source_value)


def _merge_languages(
    target: dict[str, Any],
    preset_languages: list[dict[str, Any]],
    *,
    add_missing_languages: bool,
) -> None:
    if not preset_languages:
        return
    target_languages = target.setdefault("languages", [])
    if not isinstance(target_languages, list):
        return
    existing = {
        str(language.get("name", "")).lower(): language
        for language in target_languages
        if isinstance(language, dict)
    }
    for preset_language in preset_languages:
        name = str(preset_language.get("name", "")).lower()
        language = existing.get(name)
        if language is None:
            if add_missing_languages:
                target_languages.append(deepcopy(preset_language))
            continue
        _merge_language(language, preset_language)


def _merge_language(target: dict[str, Any], preset_language: dict[str, Any]) -> None:
    if "extensions" not in target and preset_language.get("extensions") is not None:
        target["extensions"] = deepcopy(preset_language["extensions"])
    target_metrics = target.setdefault("metrics", [])
    if not isinstance(target_metrics, list):
        return
    seen = {
        str(metric.get("type"))
        for metric in target_metrics
        if isinstance(metric, dict) and metric.get("type") is not None
    }
    for metric in preset_language.get("metrics", []):
        metric_type = str(metric.get("type"))
        if metric_type not in seen:
            target_metrics.append(deepcopy(metric))
            seen.add(metric_type)
