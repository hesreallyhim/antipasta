"""Contract tests for the scope-aware terminal overview."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from antipasta.cli.report.table import format_snapshot_table
from antipasta.cli.report.table_policy import METRIC_CATEGORIES
from antipasta.core.model.config import AntipastaConfig


def _config(**extra: Any) -> AntipastaConfig:
    return AntipastaConfig.model_validate({
        "languages": [
            {
                "name": "python",
                "metrics": [
                    {"type": "cyclomatic_complexity", "threshold": 10},
                    {"type": "maintainability_index", "threshold": 50, "comparison": ">="},
                    {"type": "halstead_volume", "threshold": 1000},
                ],
            }
        ],
        **extra,
    })


def _file(
    path: str = "a.py",
    metrics: dict[str, float] | None = None,
    functions: list[dict[str, Any]] | None = None,
    language: str = "python",
) -> dict[str, Any]:
    return {
        "path": path,
        "language": language,
        "metrics": metrics or {},
        "functions": functions or [],
        "violations": [],
    }


def _function(name: str, **metrics: float) -> dict[str, Any]:
    return {"name": name, "line": 1, "metrics": metrics}


def _project(subject: str, metric: str, value: float, **details: Any) -> dict[str, Any]:
    return {
        "subject": subject,
        "metrics": [{"type": metric, "value": value, "details": details}],
        "violations": [],
    }


def _line(output: str, metric: str, scope: str) -> str:
    return next(line for line in output.splitlines() if line.startswith(f"{metric} [{scope}]"))


def test_taxonomy_matches_supported_metrics_reference() -> None:
    reference = Path(__file__).resolve().parents[4] / "docs" / "supported_metrics.md"
    rows = [
        line.split("|") for line in reference.read_text().splitlines() if line.startswith("| `")
    ]
    documented = {row[1].strip().strip("`"): row[2].strip() for row in rows}
    assert documented == METRIC_CATEGORIES


def test_scopes_and_halstead_gates_are_separate() -> None:
    snapshot = {
        "files": [
            _file(
                metrics={"cyclomatic_complexity": 12, "halstead_volume": 2000},
                functions=[
                    _function(
                        "f", cyclomatic_complexity=15, halstead_volume=3000, lack_of_cohesion=3
                    )
                ],
            )
        ]
    }
    output = format_snapshot_table(snapshot, _config())
    assert "units=1, over=1, worst=12" in _line(output, "cyclomatic_complexity", "file")
    assert "units=1, over=1, worst=15" in _line(output, "cyclomatic_complexity", "function")
    assert "over=1" in _line(output, "halstead_volume", "file")
    assert "over=" not in _line(output, "halstead_volume", "function")
    assert "lack_of_cohesion [class]" in output
    assert "Delta" not in output
    assert "Experimental" not in output
    assert "VCS" not in output
    assert "Test quality" not in output


def test_current_thresholds_drive_both_sides_of_delta() -> None:
    old: dict[str, Any] = {
        "files": [_file(functions=[_function("f", cyclomatic_complexity=12)])],
        "thresholds": {"cyclomatic_complexity": {"threshold": 1}},
    }
    current = {"files": [_file(functions=[_function("f", cyclomatic_complexity=17)])]}
    config = _config()
    config.languages[0].metrics[0].threshold = 15
    output = format_snapshot_table(current, config, baseline=old)
    assert "over=+1, worst=+5" in output
    assert "units=1, over=1, worst=17" in output


def test_lower_direction_neutral_statistics_and_ungated_offenders() -> None:
    snapshot = {
        "files": [
            _file("a.py", {"maintainability_index": 20, "comment_density": 10}),
            _file("b.py", {"maintainability_index": 30, "comment_density": 50}),
            _file("c.py", {"maintainability_index": 70, "comment_density": 20}),
        ]
    }
    output = format_snapshot_table(snapshot, _config())
    low = _line(output, "maintainability_index", "file")
    assert "worst=20" in low
    assert low.index("a.py") < low.index("b.py")
    assert "c.py" not in low
    neutral = _line(output, "comment_density", "file")
    assert "units=3, min=10, median=20, max=50 | -" in neutral


def test_threshold_relative_severity_and_three_offender_limit() -> None:
    config = _config()
    config.languages.append(
        config.languages[0].model_copy(update={"name": "javascript"}, deep=True)
    )
    config.languages[1].metrics[0].threshold = 20
    files = [
        _file("z.py", functions=[_function("f", cyclomatic_complexity=15)]),
        _file("a.js", functions=[_function("f", cyclomatic_complexity=25)], language="javascript"),
    ]
    files.extend(
        _file(f"{name}.py", functions=[_function("f", cyclomatic_complexity=12)])
        for name in ("c", "b", "d")
    )
    output = format_snapshot_table({"files": files}, config)
    line = _line(output, "cyclomatic_complexity", "function")
    assert line.index("z.py") < line.index("a.js") < line.index("b.py")
    assert "c.py" not in line
    assert "d.py" not in line


def test_project_groups_suites_and_optional_categories() -> None:
    snapshot = {
        "project": [
            _project("a", "stable_dependencies_violations", 2),
            _project("b", "stable_dependencies_violations", 4),
            _project("cycle a", "dependency_cycles", 2, members=["a", "b"]),
            _project("cycle b", "dependency_cycles", 3, members=["x", "y", "z"]),
            _project("clone", "clone_occurrences", 2, members=["a.py:1", "b.py:1"]),
            _project("pair", "change_coupling", 5, pair=["a.py", "b.py"]),
            _project("a.py", "duplication_ratio", 0.7),
            _project("suite", "test_churn_ratio", 0.3),
            _project(".", "directory_children", 4),
            _project("a.C", "depth_of_inheritance_tree", 3),
            _project("package a", "efferent_coupling", 2),
        ]
    }
    output = format_snapshot_table(
        snapshot, _config(import_graph={}, duplication={"max_ratio": 0.5})
    )
    assert "groups=2, largest=3 | x, y, z" in output
    assert "a.py:1, b.py:1" in output
    assert "change_coupling [group] | groups=1, largest=5 | a.py, b.py" in output
    assert "test_churn_ratio [suite] | value=0.3" in output
    assert "depth_of_inheritance_tree [class]" in output
    assert "efferent_coupling [package]" in output
    assert "directory_children [directory] | units=1, min=4, median=4, max=4 | -" in output
    assert "over=1" in _line(output, "duplication_ratio", "file")
    zero = _line(output, "stable_dependencies_violations", "module")
    assert "over=2" in zero
    assert zero.index("b (4)") < zero.index("a (2)")
    assert output.index("SOLID\n") < output.index("Maintainability\n")
    assert output.index("Test quality\n") < output.index("VCS\n")


def test_experimental_visibility_and_lower_ratio_order() -> None:
    snapshot = {
        "files": [
            _file(
                functions=[
                    _function("a", expression_flatness=0.2),
                    _function("b", expression_flatness=0.8),
                ]
            )
        ],
        "project": [_project("a", "name_clarity", 0.1)],
    }
    assert "expression_flatness" not in format_snapshot_table(snapshot, _config())
    config = _config(experimental={"narrative": {"name_clarity_floor": 0.5}})
    output = format_snapshot_table(snapshot, config)
    line = _line(output, "expression_flatness", "function")
    assert "worst=0.2" in line
    assert line.index("a.py:1 a") < line.index("a.py:1 b")
    assert "over=1, worst=0.1" in output


def test_metadata_noise_missing_scopes_and_footer() -> None:
    old: dict[str, Any] = {
        "project": [_project("a", "directory_children", 3, analyzer="house-style")],
        "files": [_file(metrics={"maintainability_index": 40})],
    }
    current = deepcopy(old)
    current["project"][0]["metrics"][0]["details"]["analyzer"] = "javascript-structural"
    current["files"] = [_file(metrics={"lines_of_code": 8})]
    current["summary"] = {"total_violations": 2}
    output = format_snapshot_table(current, _config(), baseline=old, fail_on=True)
    assert "min=+0, median=+0, max=+0" in output
    assert "removed" in _line(output, "maintainability_index", "file")
    assert "new" in _line(output, "lines_of_code", "file")
    assert output.endswith("Violations: 2 | Exit status: 2")
    assert format_snapshot_table({}, _config(), fail_on=True) == "Violations: 0 | Exit status: 0"


def test_omitted_or_disabled_gates_stay_ungated() -> None:
    config = _config()
    config.languages[0].metrics[0].enabled = False
    snapshot = {
        "files": [
            _file(functions=[_function("f", cyclomatic_complexity=25, cognitive_complexity=30)])
        ]
    }
    output = format_snapshot_table(snapshot, config)
    assert "over=" not in output


def test_default_language_fallback_and_unavailable_project_rows() -> None:
    snapshot = {
        "files": [_file(functions=[_function("f", cognitive_complexity=30)])],
        "project": [_project("duplication", "clone_occurrences", 0, unavailable="engine missing")],
    }
    output = format_snapshot_table(snapshot, AntipastaConfig())
    assert "over=1" in output
    assert "clone_occurrences" not in output


def test_analysis_errors_take_priority_over_threshold_exit_status() -> None:
    failed = {**_file(), "error": "Failed to read file"}
    for count in (0, 2):
        snapshot = {"files": [failed], "summary": {"total_violations": count}}
        output = format_snapshot_table(snapshot, _config(), fail_on=True)
        assert output.endswith(f"Violations: {count} | Exit status: 1")


def test_unknown_metrics_have_their_own_section_after_known_categories() -> None:
    snapshot = {
        "files": [_file(metrics={"future_metric": 3, "maintainability_index": 60})],
        "project": [_project("a.py", "code_churn", 4)],
    }
    output = format_snapshot_table(snapshot, _config())
    known, other = output.split("\n\nOther\n")
    assert "future_metric" not in known
    assert "future_metric [file] | units=1, worst=3" in other
    assert known.index("Maintainability\n") < known.index("VCS\n")
    assert "Other\n" not in format_snapshot_table({}, _config())
