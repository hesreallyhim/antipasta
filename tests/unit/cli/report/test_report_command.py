"""Tests for the report command, snapshot builder, and HTML assembly."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from click.testing import CliRunner
import pytest

from antipasta.cli.report import report
from antipasta.core.config import AntipastaConfig, ComparisonOperator
from antipasta.core.metrics import MetricResult, MetricType
from antipasta.core.snapshot import (
    SCHEMA_VERSION,
    build_snapshot,
    collect_worst_functions,
)
from antipasta.core.treemap import TREEMAP_ROOT_ID, build_treemap_nodes
from antipasta.core.violations import FileReport, Violation
from antipasta.report import render_report


def _metric(
    path: str,
    metric_type: MetricType,
    value: float,
    *,
    function_name: str | None = None,
    line_number: int | None = None,
    details: dict[str, Any] | None = None,
) -> MetricResult:
    """Build a MetricResult for test fixtures."""
    return MetricResult(
        file_path=Path(path),
        metric_type=metric_type,
        value=value,
        function_name=function_name,
        line_number=line_number,
        details=details,
    )


def _synthetic_report(path: str = "pkg/module.py") -> FileReport:
    """A FileReport resembling real radon + complexipy output for one file."""
    metrics = [
        # Per-function cyclomatic (radon style: bare name + classname detail)
        _metric(
            path,
            MetricType.CYCLOMATIC_COMPLEXITY,
            12.0,
            function_name="run",
            line_number=10,
            details={"type": "method", "classname": "Engine", "rank": "C"},
        ),
        # File-level cyclomatic average row
        _metric(
            path,
            MetricType.CYCLOMATIC_COMPLEXITY,
            12.0,
            details={"type": "average", "function_count": 1},
        ),
        # Per-function cognitive (complexipy style: qualified name)
        _metric(
            path,
            MetricType.COGNITIVE_COMPLEXITY,
            7.0,
            function_name="Engine::run",
        ),
        # File-level cognitive maximum row
        _metric(
            path,
            MetricType.COGNITIVE_COMPLEXITY,
            7.0,
            details={"type": "file_maximum", "function_count": 1},
        ),
        # File-level Halstead total + per-function Halstead row
        _metric(path, MetricType.HALSTEAD_VOLUME, 500.0),
        _metric(
            path,
            MetricType.HALSTEAD_VOLUME,
            120.0,
            function_name="run",
            details={"type": "function"},
        ),
        _metric(path, MetricType.MAINTAINABILITY_INDEX, 62.0),
        _metric(path, MetricType.LINES_OF_CODE, 100.0),
        _metric(path, MetricType.SOURCE_LINES_OF_CODE, 80.0),
    ]
    violations = [
        Violation(
            file_path=Path(path),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=12.0,
            threshold=10.0,
            comparison=ComparisonOperator.LE,
            line_number=10,
            function_name="run",
        )
    ]
    return FileReport(
        file_path=Path(path),
        language="python",
        metrics=metrics,
        violations=violations,
    )


class TestBuildSnapshot:
    """Golden-shape tests for build_snapshot."""

    @pytest.fixture
    def snapshot(self) -> dict[str, Any]:
        """Snapshot built from one synthetic report."""
        config = AntipastaConfig.generate_default()
        return build_snapshot([_synthetic_report()], config, root=Path.cwd())

    def test_schema_and_metadata(self, snapshot: dict[str, Any]) -> None:
        """Test top-level snapshot shape."""
        assert snapshot["schema_version"] == SCHEMA_VERSION == 2
        assert snapshot["files"], "expected one file entry"
        assert snapshot["summary"]["total_files"] == 1
        assert snapshot["summary"]["total_violations"] == 1
        assert snapshot["thresholds"]["cyclomatic_complexity"]["direction"] == "max"
        assert snapshot["thresholds"]["maintainability_index"]["direction"] == "min"

    def test_file_entry_metrics_are_file_level(self, snapshot: dict[str, Any]) -> None:
        """File-level metrics dict must hold only rows without function names."""
        entry = snapshot["files"][0]
        assert entry["path"] == "pkg/module.py"
        assert entry["language"] == "python"
        assert entry["metrics"]["halstead_volume"] == 500.0  # total, not per-function
        assert entry["metrics"]["cyclomatic_complexity"] == 12.0
        assert len(entry["violations"]) == 1

    def test_functions_merge_across_runners_with_halstead(self, snapshot: dict[str, Any]) -> None:
        """radon (bare name) and complexipy (qualified) rows merge into one entry."""
        functions = snapshot["files"][0]["functions"]
        assert len(functions) == 1
        fn = functions[0]
        assert fn["name"] == "Engine::run"
        assert fn["line"] == 10
        assert fn["metrics"]["cyclomatic_complexity"] == 12.0
        assert fn["metrics"]["cognitive_complexity"] == 7.0
        assert fn["metrics"]["halstead_volume"] == 120.0  # per-function row

    def test_language_coverage(self, snapshot: dict[str, Any]) -> None:
        """Coverage lists the metric types actually observed per language."""
        assert "cyclomatic_complexity" in snapshot["language_coverage"]["python"]
        assert "halstead_volume" in snapshot["language_coverage"]["python"]


class TestTreemapNodes:
    """Regression tests for the treemap node table (docs/treemap_loc_fix.md)."""

    def _files(self, *paths: str) -> list[dict[str, Any]]:
        return [
            {
                "path": p,
                "language": "python",
                "error": None,
                "metrics": {"source_lines_of_code": 10.0},
                "violations": [],
                "functions": [],
            }
            for p in paths
        ]

    def test_mixed_depth_tree_has_root_and_no_orphans(self) -> None:
        """Every node's parent must exist; exactly one root (the post-mortem bug)."""
        nodes = build_treemap_nodes(
            self._files("a.py", "pkg/b.py", "pkg/sub/deep/c.py", "pkg/sub/d.py"),
            root_label="repo",
        )
        ids = {n["id"] for n in nodes}
        roots = [n for n in nodes if n["parent"] is None]
        orphans = [n for n in nodes if n["parent"] is not None and n["parent"] not in ids]
        assert len(roots) == 1
        assert roots[0]["label"] == "repo"
        assert orphans == []
        # every intermediate directory is an explicit node
        assert {"pkg", "pkg/sub", "pkg/sub/deep"} <= ids

    def test_leaves_carry_value_and_file_index(self) -> None:
        """Leaf rows carry the area value and an index into files."""
        nodes = build_treemap_nodes(self._files("x.py", "d/y.py"))
        leaves = [n for n in nodes if "file_index" in n]
        assert [leaf["file_index"] for leaf in leaves] == [0, 1]
        assert all(leaf["value"] == 10.0 for leaf in leaves)

    def test_directories_carry_hoverable_aggregates(self) -> None:
        """Inner nodes (and the root) roll up files/value/violations/metric maxima.

        The treemap's directory rectangles are data, not just structure: a
        reviewer hovering `report/assets/` should see the subtree's totals and
        its worst file per metric (max is the threshold-meaningful aggregate).
        """
        files = self._files("report/assets/a.py", "report/assets/b.py", "report/html.py")
        files[0]["metrics"]["cyclomatic_complexity"] = 12.0
        files[1]["metrics"]["cyclomatic_complexity"] = 3.0
        files[0]["violations"] = [{"metric": "cyclomatic_complexity"}]
        nodes = {n["id"]: n for n in build_treemap_nodes(files)}

        assets = nodes["report/assets"]["aggregate"]
        assert assets["files"] == 2
        assert assets["value"] == 20.0
        assert assets["violations"] == 1
        worst = assets["metrics_max"]["cyclomatic_complexity"]
        assert worst == {"value": 12.0, "path": "report/assets/a.py"}

        report = nodes["report"]["aggregate"]
        assert report["files"] == 3
        assert report["value"] == 30.0

        root = nodes[TREEMAP_ROOT_ID]["aggregate"]
        assert root["files"] == 3

        # Leaves carry no aggregate — their data lives on the file entry.
        assert "aggregate" not in nodes["report/html.py"]

    def test_empty_input_still_has_root(self) -> None:
        """No files still produces a valid single-root table."""
        nodes = build_treemap_nodes([])
        assert len(nodes) == 1
        assert nodes[0]["parent"] is None


class TestCollectWorstFunctions:
    """Tests for the --top ranking."""

    def test_ranked_by_max_of_cyclomatic_and_cognitive(self) -> None:
        """Ranking uses the larger of the two complexities, descending."""
        snapshot = {
            "files": [
                {
                    "path": "a.py",
                    "functions": [
                        {"name": "low", "line": 1, "metrics": {"cyclomatic_complexity": 2.0}},
                        {
                            "name": "high",
                            "line": 5,
                            "metrics": {
                                "cyclomatic_complexity": 3.0,
                                "cognitive_complexity": 20.0,
                            },
                        },
                        {"name": "nometrics", "line": 9, "metrics": {"halstead_volume": 1.0}},
                    ],
                }
            ]
        }
        rows = collect_worst_functions(snapshot, 10)
        assert [r["name"] for r in rows] == ["high", "low"]
        assert rows[0]["score"] == 20.0

    def test_limit_applies(self) -> None:
        """Only the requested number of rows is returned."""
        snapshot = {
            "files": [
                {
                    "path": "a.py",
                    "functions": [
                        {"name": f"f{i}", "line": i, "metrics": {"cyclomatic_complexity": float(i)}}
                        for i in range(1, 6)
                    ],
                }
            ]
        }
        assert len(collect_worst_functions(snapshot, 2)) == 2


class TestRenderReport:
    """Tests for offline HTML assembly."""

    @pytest.fixture
    def html(self) -> str:
        """Rendered report for one synthetic file."""
        config = AntipastaConfig.generate_default()
        snapshot = build_snapshot([_synthetic_report()], config, root=Path.cwd())
        return render_report(snapshot)

    def test_data_is_injected_and_marker_removed(self, html: str) -> None:
        """The snapshot JSON replaces the marker entirely."""
        assert "/*__ANTIPASTA_DATA__*/" not in html
        assert "window.ANTIPASTA_DATA" in html
        assert '"schema_version":2' in html
        assert "pkg/module.py" in html

    def test_no_network_references(self, html: str) -> None:
        """The single-file report must be fully offline."""
        assert re.search(r"https?://", html, re.IGNORECASE) is None
        assert "<script src" not in html
        assert "<link" not in html

    def test_all_assets_inlined(self, html: str) -> None:
        """CSS, d3, and the report script are all embedded."""
        assert "/*__ANTIPASTA_CSS__*/" not in html
        assert "/*__D3_JS__*/" not in html
        assert "/*__ANTIPASTA_JS__*/" not in html
        assert "d3js.org v7" in html  # d3 banner (defanged) is present


class TestReportCommand:
    """CLI smoke tests."""

    def test_json_format_stdout_is_clean_json(self, tmp_path: Path) -> None:
        """`report --format json` exits 0 and stdout parses as JSON."""
        source = tmp_path / "sample.py"
        source.write_text("def hello():\n    return 'world'\n")

        runner = CliRunner()
        result = runner.invoke(
            report,
            ["-d", str(tmp_path), "--format", "json", "-c", str(tmp_path / "missing.yaml")],
        )

        assert result.exit_code == 0, result.output
        snapshot = json.loads(result.stdout)
        assert snapshot["schema_version"] == 2
        assert snapshot["summary"]["total_files"] == 1

    def test_html_written_to_output_file(self, tmp_path: Path) -> None:
        """`report -o out.html` writes an offline HTML document."""
        source = tmp_path / "sample.py"
        source.write_text("def hello():\n    return 'world'\n")
        out = tmp_path / "out.html"

        runner = CliRunner()
        result = runner.invoke(
            report,
            ["-d", str(tmp_path), "-o", str(out), "-c", str(tmp_path / "missing.yaml")],
        )

        assert result.exit_code == 0, result.output
        html = out.read_text()
        assert re.search(r"https?://", html, re.IGNORECASE) is None
        assert "window.ANTIPASTA_DATA" in html

    def test_top_table_goes_to_stdout_when_data_in_file(self, tmp_path: Path) -> None:
        """With -o, the --top ranking shares stdout."""
        source = tmp_path / "sample.py"
        source.write_text(
            "def branchy(a, b):\n"
            "    if a:\n"
            "        if b:\n"
            "            return 1\n"
            "        return 2\n"
            "    return 3\n"
        )
        out = tmp_path / "snap.json"

        runner = CliRunner()
        result = runner.invoke(
            report,
            [
                "-d",
                str(tmp_path),
                "--format",
                "json",
                "-o",
                str(out),
                "--top",
                "5",
                "-c",
                str(tmp_path / "missing.yaml"),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "branchy" in result.stdout
        assert json.loads(out.read_text())["schema_version"] == 2
