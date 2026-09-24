"""The gate resolver is the one answer to "which threshold applies here?"."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.detector import Language
from antipasta.core.model.gates import (
    default_language_config,
    language_gates,
    project_gates,
    resolve_gates,
)
from antipasta.core.model.violations import FileReport
from antipasta.core.store.snapshot import build_snapshot


def _config(**extra: object) -> AntipastaConfig:
    return AntipastaConfig.model_validate({
        "defaults": {"max_cyclomatic_complexity": 8},
        "languages": [
            {
                "name": "python",
                "extensions": [".py"],
                "metrics": [
                    {"type": "cyclomatic_complexity", "threshold": 8, "comparison": "<="},
                    {"type": "lines_of_code", "threshold": 1000, "comparison": "<="},
                    {
                        "type": "cognitive_complexity",
                        "threshold": 15,
                        "comparison": "<=",
                        "enabled": False,
                    },
                ],
            }
        ],
        **extra,
    })


def test_configured_language_uses_only_its_enabled_gates() -> None:
    gates = language_gates(_config(), "python")
    assert set(gates) == {"cyclomatic_complexity", "lines_of_code"}
    assert gates["lines_of_code"].threshold == 1000


def test_unconfigured_known_language_falls_back_to_built_in_gates() -> None:
    gates = language_gates(_config(), "javascript")
    assert set(gates) == {"cyclomatic_complexity"}
    assert gates["cyclomatic_complexity"].threshold == 8
    assert set(language_gates(AntipastaConfig(), "PYTHON")) == {
        "cyclomatic_complexity",
        "maintainability_index",
        "halstead_volume",
        "halstead_difficulty",
        "halstead_effort",
        "cognitive_complexity",
    }


def test_unknown_language_has_no_gates() -> None:
    assert language_gates(_config(), "rust") == {}
    typescript = default_language_config(AntipastaConfig(), Language.TYPESCRIPT)
    assert typescript.metrics[0].threshold == 10


def test_project_gates_follow_optional_config_blocks() -> None:
    assert project_gates(AntipastaConfig()) == {}
    config = _config(
        import_graph={"forbid_cycles": True},
        duplication={"max_ratio": 0.2},
        tree_shape={"layers": ["cli", "core"]},
    )
    gates = project_gates(config)
    assert set(gates) == {
        "stable_dependencies_violations",
        "dependency_cycles",
        "duplication_ratio",
        "layering_violations",
    }
    assert gates["duplication_ratio"].threshold == 0.2


def test_snapshot_embeds_resolved_gates_per_observed_language() -> None:
    reports = [
        FileReport(file_path=Path("a.py"), language="python", metrics=[], violations=[]),
        FileReport(file_path=Path("b.js"), language="javascript", metrics=[], violations=[]),
    ]
    snapshot = build_snapshot(reports, _config(), root=Path.cwd())
    gates = snapshot["gates"]
    assert set(gates["languages"]) == {"python", "javascript"}
    assert gates["languages"]["python"]["lines_of_code"] == {
        "threshold": 1000.0,
        "comparison": "<=",
    }
    assert "cognitive_complexity" not in gates["languages"]["python"]
    assert gates["languages"]["javascript"] == {
        "cyclomatic_complexity": {"threshold": 8.0, "comparison": "<="}
    }
    assert gates["project"] == {}
    # The legacy block still carries the global defaults for older readers.
    assert snapshot["thresholds"]["cognitive_complexity"]["threshold"] == 15.0


def test_resolve_gates_dedupes_and_sorts_languages() -> None:
    resolved = resolve_gates(AntipastaConfig(), ["python", "python", "javascript"])
    assert list(resolved["languages"]) == ["javascript", "python"]
