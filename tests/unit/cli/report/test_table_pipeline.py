"""Exercise the table contract through real runners, derivers, and snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from antipasta.cli.metrics.metrics_utils_analysis import execute_analysis
from antipasta.cli.report.table import format_snapshot_table
from antipasta.cli.report.table_rows import collect_rows
from antipasta.core.model.config import AntipastaConfig
from antipasta.core.store.snapshot import build_snapshot


@pytest.fixture
def analyzed_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], AntipastaConfig]:
    monkeypatch.setenv("ANTIPASTA_NO_CACHE", "1")
    first = tmp_path / "a.py"
    first.write_text(
        "import b\n\n"
        "def alpha(x):\n    y = x + 1\n    z = y * 2\n    return z\n\n"
        "class Example:\n"
        "    def run(self, x):\n"
        "        if x:\n            return self.value\n        return 0\n"
    )
    second = tmp_path / "b.py"
    second.write_text("import a\n\ndef beta(q):\n    w = q + 1\n    v = w * 2\n    return v\n")
    config = AntipastaConfig.model_validate({"duplication": {}, "import_graph": {}})
    results = execute_analysis([first, second], config, quiet=True, root=tmp_path)
    snapshot = build_snapshot(
        results["reports"],
        config,
        root=tmp_path,
        summary=results["summary"],
        project_reports=results["project_reports"],
        import_graph=results["import_graph"],
    )
    return snapshot, config


def test_real_complexity_aggregates_survive_separate_from_functions(
    analyzed_snapshot: tuple[dict[str, Any], AntipastaConfig],
) -> None:
    snapshot, config = analyzed_snapshot
    rows = collect_rows(snapshot)
    assert sorted(row.value for row in rows["cyclomatic_complexity", "file"]) == [1, 1.5]
    assert sorted(row.value for row in rows["cyclomatic_complexity", "function"]) == [1, 1, 2]
    assert sorted(row.value for row in rows["cognitive_complexity", "file"]) == [0, 1]
    assert len(rows["cognitive_complexity", "function"]) == 3
    output = format_snapshot_table(snapshot, config)
    assert "cyclomatic_complexity [file] | units=2, over=0, worst=1.5" in output
    assert "cyclomatic_complexity [function] | units=3, over=0, worst=2" in output
    assert "cognitive_complexity [file] | units=2, over=0, worst=1" in output


def test_real_class_and_module_subjects_keep_their_identity(
    analyzed_snapshot: tuple[dict[str, Any], AntipastaConfig],
) -> None:
    snapshot, config = analyzed_snapshot
    rows = collect_rows(snapshot)
    assert rows["lack_of_cohesion", "class"][0].subject == "a.py:8 Example"
    assert rows["weighted_methods_per_class", "class"][0].subject == "a.py:8 Example"
    assert rows["depth_of_inheritance_tree", "class"][0].subject == "a::Example"
    assert {row.subject for row in rows["efferent_coupling", "module"]} == {"a", "b"}
    assert len(rows["efferent_coupling", "package"]) == 1
    output = format_snapshot_table(snapshot, config)
    assert "weighted_methods_per_class [class] | units=1, worst=2 | a.py:8 Example (2)" in output
    assert "depth_of_inheritance_tree [class] | units=1, worst=1 | a::Example (1)" in output


def test_real_group_details_and_project_violation_summary(
    analyzed_snapshot: tuple[dict[str, Any], AntipastaConfig],
) -> None:
    snapshot, config = analyzed_snapshot
    rows = collect_rows(snapshot)
    assert rows["clone_occurrences", "group"][0].members == ("a.py:3 alpha", "b.py:3 beta")
    assert rows["dependency_cycles", "group"][0].members == ("a", "b")
    output = format_snapshot_table(snapshot, config, fail_on=True)
    assert "clone_occurrences [group] | groups=1, largest=2 | a.py:3 alpha, b.py:3 beta" in output
    assert "dependency_cycles [group] | groups=1, largest=2 | a, b" in output
    assert output.endswith("Violations: 1 | Exit status: 2")
