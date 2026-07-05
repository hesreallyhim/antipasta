"""Tests for the snapshot diff engine (antipasta.core.store.snapshot_diff).

The diff is the heart of baseline comparison: these tests pin down file
add/remove, rename-ish churn, metric deltas (epsilon, missing, non-numeric),
function score deltas, violation changes, schema drift tolerance, and the
degenerate empty cases.
"""

from __future__ import annotations

from typing import Any

from antipasta.cli.report.diff_summary import format_diff_summary
from antipasta.core.store.snapshot_diff import DEFAULT_EPSILON, SnapshotDiff, diff
from antipasta.report.baseline import build_baseline_payload

# ----- snapshot fixture builders -------------------------------------------


def _function(name: str, line: int | None = 1, **metrics: float | None) -> dict[str, Any]:
    """A snapshot function entry."""
    return {"name": name, "line": line, "metrics": dict(metrics)}


def _violation(metric: str, function: str | None, message: str | None = None) -> dict[str, Any]:
    """A snapshot violation entry (subset of Violation.to_dict)."""
    return {
        "type": metric,
        "function": function,
        "message": message or f"{function or 'file'}: {metric} over threshold",
        "line_number": 1,
        "value": 99.0,
        "threshold": 10.0,
        "comparison": "<=",
    }


def _file(
    path: str,
    metrics: dict[str, Any] | None = None,
    functions: list[dict[str, Any]] | None = None,
    violations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A snapshot file entry."""
    return {
        "path": path,
        "language": "python",
        "error": None,
        "metrics": metrics or {},
        "violations": violations or [],
        "functions": functions or [],
    }


def _snapshot(files: list[dict[str, Any]], schema_version: int = 1) -> dict[str, Any]:
    """A minimal snapshot dictionary."""
    return {"schema_version": schema_version, "files": files}


# ----- files added / removed ------------------------------------------------


class TestFileChurn:
    """File-level add/remove detection."""

    def test_added_and_removed_files_are_sorted(self) -> None:
        """New paths land in files_added, missing ones in files_removed."""
        old = _snapshot([_file("kept.py"), _file("z_gone.py"), _file("a_gone.py")])
        new = _snapshot([_file("kept.py"), _file("z_new.py"), _file("a_new.py")])

        result = diff(old, new)

        assert result.files_added == ["a_new.py", "z_new.py"]
        assert result.files_removed == ["a_gone.py", "z_gone.py"]

    def test_identical_snapshots_diff_empty(self) -> None:
        """Same snapshot on both sides produces an empty diff."""
        functions = [_function("f", 1, cyclomatic_complexity=3.0)]
        snapshot = _snapshot([_file("a.py", {"cyclomatic_complexity": 3.0}, functions)])

        result = diff(snapshot, snapshot)

        assert result.is_empty
        assert result.warnings == []

    def test_empty_snapshots(self) -> None:
        """Two empty snapshots diff to an empty result without errors."""
        result = diff(_snapshot([]), _snapshot([]))

        assert result.is_empty

    def test_missing_files_key_is_tolerated(self) -> None:
        """A snapshot without a files list diffs as if it had no files."""
        result = diff({}, _snapshot([_file("a.py")]))

        assert result.files_added == ["a.py"]
        # {} has schema_version None vs 1 -> drift warning
        assert len(result.warnings) == 1

    def test_malformed_file_entries_are_skipped(self) -> None:
        """Entries without a string path are ignored, not fatal."""
        old = _snapshot([{"metrics": {}}, "not-a-dict", _file("ok.py")])  # type: ignore[list-item]
        new = _snapshot([_file("ok.py")])

        result = diff(old, new)

        assert result.is_empty


# ----- file-level metric deltas ---------------------------------------------


class TestFileMetricDeltas:
    """Per-file metric delta extraction."""

    def test_delta_above_epsilon_is_reported(self) -> None:
        """A real change shows old value, new value, and signed delta."""
        old = _snapshot([_file("a.py", {"cyclomatic_complexity": 10.0, "lines_of_code": 100.0})])
        new = _snapshot([_file("a.py", {"cyclomatic_complexity": 14.0, "lines_of_code": 100.0})])

        result = diff(old, new)

        assert len(result.file_deltas) == 1
        (delta,) = result.file_deltas[0].metric_deltas
        assert delta.metric == "cyclomatic_complexity"
        assert delta.old_value == 10.0
        assert delta.new_value == 14.0
        assert delta.delta == 4.0
        assert delta.regressed

    def test_delta_within_epsilon_is_noise(self) -> None:
        """Changes at or below epsilon do not produce a file delta."""
        old = _snapshot([_file("a.py", {"halstead_volume": 500.0})])
        new = _snapshot([_file("a.py", {"halstead_volume": 500.0 + DEFAULT_EPSILON})])

        assert diff(old, new).file_deltas == []

    def test_custom_epsilon(self) -> None:
        """The epsilon threshold is configurable."""
        old = _snapshot([_file("a.py", {"halstead_volume": 500.0})])
        new = _snapshot([_file("a.py", {"halstead_volume": 502.0})])

        assert diff(old, new).file_deltas != []
        assert diff(old, new, epsilon=5.0).file_deltas == []

    def test_metric_missing_on_either_side_is_not_a_delta(self) -> None:
        """Only metrics present on both sides are compared."""
        old = _snapshot([_file("a.py", {"cyclomatic_complexity": 5.0})])
        new = _snapshot([_file("a.py", {"cognitive_complexity": 50.0})])

        assert diff(old, new).file_deltas == []

    def test_non_numeric_metric_values_are_skipped(self) -> None:
        """None/str metric values (schema drift) never crash the diff."""
        old = _snapshot([_file("a.py", {"cyclomatic_complexity": None, "lines_of_code": "many"})])
        new = _snapshot([_file("a.py", {"cyclomatic_complexity": 5.0, "lines_of_code": 10.0})])

        assert diff(old, new).file_deltas == []

    def test_maintainability_index_drop_is_a_regression(self) -> None:
        """Direction-aware: for min-direction metrics a negative delta regresses."""
        old = _snapshot([_file("a.py", {"maintainability_index": 80.0})])
        new = _snapshot([_file("a.py", {"maintainability_index": 60.0})])

        (delta,) = diff(old, new).file_deltas[0].metric_deltas
        assert delta.delta == -20.0
        assert delta.regressed

    def test_maintainability_index_rise_is_not_a_regression(self) -> None:
        """Direction-aware: an MI increase is an improvement."""
        old = _snapshot([_file("a.py", {"maintainability_index": 60.0})])
        new = _snapshot([_file("a.py", {"maintainability_index": 80.0})])

        (delta,) = diff(old, new).file_deltas[0].metric_deltas
        assert not delta.regressed


# ----- function deltas -------------------------------------------------------


class TestFunctionDeltas:
    """Per-function score deltas, regressions, and improvements."""

    def _pair(self, old_fn: dict[str, Any], new_fn: dict[str, Any]) -> SnapshotDiff:
        return diff(
            _snapshot([_file("a.py", functions=[old_fn])]),
            _snapshot([_file("a.py", functions=[new_fn])]),
        )

    def test_score_uses_max_of_cyclomatic_and_cognitive(self) -> None:
        """The score mirrors the report UI: max(cyc, cog)."""
        result = self._pair(
            _function("f", 1, cyclomatic_complexity=3.0, cognitive_complexity=8.0),
            _function("f", 1, cyclomatic_complexity=4.0, cognitive_complexity=12.0),
        )

        (fn,) = result.function_deltas
        assert fn.old_score == 8.0
        assert fn.new_score == 12.0
        assert fn.score_delta == 4.0
        assert result.regressions == [fn]
        assert result.improvements == []

    def test_improvement_is_negative_delta(self) -> None:
        """A drop in complexity lands in improvements, not regressions."""
        result = self._pair(
            _function("f", 1, cyclomatic_complexity=9.0),
            _function("f", 1, cyclomatic_complexity=4.0),
        )

        (fn,) = result.function_deltas
        assert fn.score_delta == -5.0
        assert result.improvements == [fn]
        assert result.regressions == []

    def test_unchanged_function_produces_no_delta(self) -> None:
        """Equal scores (and no new violation) yield nothing."""
        result = self._pair(
            _function("f", 1, cyclomatic_complexity=5.0),
            _function("f", 1, cyclomatic_complexity=5.0),
        )

        assert result.function_deltas == []

    def test_function_without_score_on_one_side_is_skipped(self) -> None:
        """Missing complexity metrics (e.g. halstead-only rows) are not scored."""
        result = self._pair(
            _function("f", 1, halstead_volume=100.0),
            _function("f", 1, cyclomatic_complexity=12.0),
        )

        assert result.function_deltas == []

    def test_function_metric_deltas_are_included(self) -> None:
        """The per-metric breakdown rides along on the function delta."""
        result = self._pair(
            _function("f", 1, cyclomatic_complexity=5.0, halstead_volume=100.0),
            _function("f", 1, cyclomatic_complexity=9.0, halstead_volume=180.0),
        )

        (fn,) = result.function_deltas
        assert {md.metric: md.delta for md in fn.metric_deltas} == {
            "cyclomatic_complexity": 4.0,
            "halstead_volume": 80.0,
        }

    def test_line_number_comes_from_new_snapshot(self) -> None:
        """The reported line is where the function lives *now*."""
        result = self._pair(
            _function("f", 10, cyclomatic_complexity=5.0),
            _function("f", 42, cyclomatic_complexity=9.0),
        )

        assert result.function_deltas[0].line == 42

    def test_rename_ish_shows_as_function_add_and_remove(self) -> None:
        """A renamed function appears as removed + added churn, not a delta."""
        old_fns = [_function("old_name", 1, cyclomatic_complexity=5.0)]
        new_fns = [_function("new_name", 1, cyclomatic_complexity=5.0)]
        old = _snapshot([_file("a.py", functions=old_fns)])
        new = _snapshot([_file("a.py", functions=new_fns)])

        result = diff(old, new)

        assert result.function_deltas == []
        (fd,) = result.file_deltas
        assert fd.functions_added == ["new_name"]
        assert fd.functions_removed == ["old_name"]

    def test_sorted_by_worst_regression_first(self) -> None:
        """function_deltas orders by descending score delta."""
        old = _snapshot([
            _file(
                "a.py",
                functions=[
                    _function("small", 1, cyclomatic_complexity=5.0),
                    _function("big", 2, cyclomatic_complexity=5.0),
                    _function("better", 3, cyclomatic_complexity=5.0),
                ],
            )
        ])
        new = _snapshot([
            _file(
                "a.py",
                functions=[
                    _function("small", 1, cyclomatic_complexity=7.0),
                    _function("big", 2, cyclomatic_complexity=15.0),
                    _function("better", 3, cyclomatic_complexity=2.0),
                ],
            )
        ])

        names = [fn.name for fn in diff(old, new).function_deltas]
        assert names == ["big", "small", "better"]

    def test_new_violation_puts_function_first_in_regressions(self) -> None:
        """Regressions list new violations before larger plain deltas."""
        old = _snapshot([
            _file(
                "a.py",
                functions=[
                    _function("plain", 1, cyclomatic_complexity=5.0),
                    _function("violator", 2, cyclomatic_complexity=9.0),
                ],
            )
        ])
        new = _snapshot([
            _file(
                "a.py",
                functions=[
                    _function("plain", 1, cyclomatic_complexity=25.0),
                    _function("violator", 2, cyclomatic_complexity=11.0),
                ],
                violations=[_violation("cyclomatic_complexity", "violator")],
            )
        ])

        regressions = diff(old, new).regressions
        assert [fn.name for fn in regressions] == ["violator", "plain"]
        assert regressions[0].new_violation
        assert not regressions[1].new_violation

    def test_new_violation_matches_qualified_function_names(self) -> None:
        """A violation on bare 'run' flags the qualified 'Engine::run' entry."""
        old = _snapshot([
            _file("a.py", functions=[_function("Engine::run", 1, cyclomatic_complexity=9.0)])
        ])
        new = _snapshot([
            _file(
                "a.py",
                functions=[_function("Engine::run", 1, cyclomatic_complexity=11.0)],
                violations=[_violation("cyclomatic_complexity", "run")],
            )
        ])

        (fn,) = diff(old, new).function_deltas
        assert fn.new_violation

    def test_preexisting_violation_is_not_new(self) -> None:
        """A function violating in both snapshots is not flagged as new."""
        violations = [_violation("cyclomatic_complexity", "f")]
        old_fns = [_function("f", 1, cyclomatic_complexity=11.0)]
        new_fns = [_function("f", 1, cyclomatic_complexity=13.0)]
        old = _snapshot([_file("a.py", functions=old_fns, violations=violations)])
        new = _snapshot([_file("a.py", functions=new_fns, violations=violations)])

        (fn,) = diff(old, new).function_deltas
        assert not fn.new_violation


# ----- violation changes -----------------------------------------------------


class TestViolationChanges:
    """Added/resolved violation tracking."""

    def test_new_violation_in_added_file_is_reported(self) -> None:
        """Violations arriving with brand-new files count as added."""
        violations = [_violation("cyclomatic_complexity", "f", "new.py: too complex")]
        new = _snapshot([_file("new.py", violations=violations)])

        changes = diff(_snapshot([]), new).violation_changes

        assert [record.path for record in changes.added] == ["new.py"]
        assert changes.added[0].message == "new.py: too complex"
        assert changes.removed == []

    def test_violation_in_removed_file_is_resolved(self) -> None:
        """Violations leaving with deleted files count as removed."""
        old = _snapshot([_file("gone.py", violations=[_violation("halstead_volume", None)])])

        changes = diff(old, _snapshot([])).violation_changes

        assert [record.path for record in changes.removed] == ["gone.py"]
        assert changes.removed[0].function is None
        assert changes.added == []

    def test_value_change_of_existing_violation_is_neither(self) -> None:
        """Identity is (path, metric, function): a worse value is not 'new'."""
        old_violations = [_violation("cyclomatic_complexity", "f", "was 12")]
        new_violations = [_violation("cyclomatic_complexity", "f", "now 15")]
        old = _snapshot([_file("a.py", violations=old_violations)])
        new = _snapshot([_file("a.py", violations=new_violations)])

        changes = diff(old, new).violation_changes

        assert changes.added == []
        assert changes.removed == []

    def test_different_metric_same_function_is_new(self) -> None:
        """A second metric violating on the same function is a new violation."""
        old = _snapshot([_file("a.py", violations=[_violation("cyclomatic_complexity", "f")])])
        new = _snapshot([
            _file(
                "a.py",
                violations=[
                    _violation("cyclomatic_complexity", "f"),
                    _violation("cognitive_complexity", "f"),
                ],
            )
        ])

        changes = diff(old, new).violation_changes

        assert [record.metric for record in changes.added] == ["cognitive_complexity"]


# ----- schema drift ----------------------------------------------------------


class TestSchemaDrift:
    """Tolerance for snapshots from other schema versions."""

    def test_schema_version_mismatch_warns_but_diffs(self) -> None:
        """Differing schema versions produce a warning and a best-effort diff."""
        old = _snapshot([_file("a.py", {"cyclomatic_complexity": 5.0})], schema_version=0)
        new = _snapshot([_file("a.py", {"cyclomatic_complexity": 9.0})], schema_version=1)

        result = diff(old, new)

        assert len(result.warnings) == 1
        assert "schema_version" in result.warnings[0]
        assert result.file_deltas[0].metric_deltas[0].delta == 4.0

    def test_matching_schema_versions_do_not_warn(self) -> None:
        """No warning when both snapshots share a schema version."""
        assert diff(_snapshot([]), _snapshot([])).warnings == []

    def test_unknown_extra_keys_are_ignored(self) -> None:
        """Future snapshot keys never break the diff."""
        old = _snapshot([_file("a.py")])
        old["future_field"] = {"anything": True}
        new = _snapshot([_file("a.py")])

        assert diff(old, new).is_empty


# ----- terminal summary ------------------------------------------------------


class TestFormatDiffSummary:
    """The plain-text delta summary."""

    def test_empty_diff_prints_no_differences(self) -> None:
        """An empty diff renders the no-differences line with the epsilon."""
        summary = format_diff_summary(
            diff(_snapshot([]), _snapshot([])), baseline_label="base.json"
        )

        assert "base.json" in summary
        assert "No differences" in summary

    def test_full_summary_sections_and_order(self) -> None:
        """Sections appear with churn first, then violations, then functions."""
        old = _snapshot([
            _file("gone.py"),
            _file(
                "a.py",
                {"cyclomatic_complexity": 10.0},
                functions=[
                    _function("worse", 1, cyclomatic_complexity=5.0),
                    _function("nicer", 2, cyclomatic_complexity=9.0),
                ],
            ),
        ])
        new = _snapshot([
            _file("added.py"),
            _file(
                "a.py",
                {"cyclomatic_complexity": 16.0},
                functions=[
                    _function("worse", 1, cyclomatic_complexity=11.0),
                    _function("nicer", 2, cyclomatic_complexity=4.0),
                ],
                violations=[_violation("cyclomatic_complexity", "worse", "a.py: worse over")],
            ),
        ])

        summary = format_diff_summary(diff(old, new), baseline_label="base.json")

        assert "Files: 1 added, 1 removed, 1 changed" in summary
        assert "+ added.py" in summary
        assert "- gone.py" in summary
        assert "New violations (1):" in summary
        assert "a.py: worse over" in summary
        assert "* +6  worse  a.py:1" in summary
        assert "-5  nicer  a.py:2" in summary
        assert "cyclomatic_complexity 10→16 (+6)" in summary
        # regressions section appears before improvements
        assert summary.index("worse  a.py:1") < summary.index("nicer  a.py:2")


# ----- HTML payload ----------------------------------------------------------


class TestBuildBaselinePayload:
    """The baseline object embedded in the HTML report."""

    def test_payload_shape(self) -> None:
        """Payload carries label, metadata, delta map, and function rows."""
        old = _snapshot([
            _file(
                "a.py",
                {"cyclomatic_complexity": 10.0},
                functions=[_function("f", 3, cyclomatic_complexity=5.0)],
            )
        ])
        old["generated_at"] = "2026-07-01T00:00:00+00:00"
        new = _snapshot([
            _file(
                "a.py",
                {"cyclomatic_complexity": 14.0},
                functions=[_function("f", 3, cyclomatic_complexity=9.0)],
            ),
            _file("b.py"),
        ])

        payload = build_baseline_payload(diff(old, new), old, label="base.json")

        assert payload["label"] == "base.json"
        assert payload["generated_at"] == "2026-07-01T00:00:00+00:00"
        assert payload["files_added"] == ["b.py"]
        assert payload["files_removed"] == []
        assert payload["file_deltas"] == {"a.py": {"cyclomatic_complexity": 4.0}}
        (row,) = payload["regressions"]
        assert row["name"] == "f"
        assert row["line"] == 3
        assert row["score_delta"] == 4.0
        assert row["new_violation"] is False
        assert row["deltas"]["cyclomatic_complexity"] == {"old": 5.0, "new": 9.0, "delta": 4.0}
        assert payload["improvements"] == []
        assert payload["violations_added"] == 0

    def test_payload_is_json_serializable(self) -> None:
        """The payload must embed cleanly in the report data."""
        import json

        payload = build_baseline_payload(
            diff(_snapshot([_file("a.py")]), _snapshot([])), _snapshot([]), label="x"
        )

        assert json.loads(json.dumps(payload))["files_removed"] == ["a.py"]
