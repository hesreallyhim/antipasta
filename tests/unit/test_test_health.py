"""Tests for track D2 coverage-matrix analytics."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
import pytest

from antipasta.cli.test_health import test_health as cli_command
from antipasta.core.mining.coverage_matrix import (
    CoverageMatrix,
    blast_radius,
    matrix_reports,
    redundancy_index,
    unique_coverage,
)
from antipasta.core.model.metrics import MetricType


def _matrix() -> CoverageMatrix:
    # test_a covers lines nobody else does; test_b is fully subsumed by
    # test_a; test_c has its own territory.
    return CoverageMatrix(
        lines_by_test={
            "tests/test_x.py::test_a": {("src/m.py", 1), ("src/m.py", 2), ("src/m.py", 3)},
            "tests/test_x.py::test_b": {("src/m.py", 1), ("src/m.py", 2)},
            "tests/test_x.py::test_c": {("src/n.py", 1)},
        }
    )


class TestAnalytics:
    def test_unique_coverage(self) -> None:
        ratios = unique_coverage(_matrix())

        assert ratios["tests/test_x.py::test_b"] == 0.0  # fully subsumed
        assert ratios["tests/test_x.py::test_c"] == 1.0
        assert 0.0 < ratios["tests/test_x.py::test_a"] < 1.0

    def test_redundancy_index(self) -> None:
        index, cover = redundancy_index(_matrix())

        # a + c cover everything; b adds nothing: 1 - 2/3
        assert cover == 2
        assert round(index, 2) == 0.33

    def test_blast_radius(self) -> None:
        radii = blast_radius(_matrix())

        assert radii["src/m.py"] == 2
        assert radii["src/n.py"] == 1

    def test_reports_shape(self) -> None:
        reports = matrix_reports(_matrix())

        suite = next(r for r in reports if r.subject == "suite-redundancy")
        details = suite.metrics[0].details or {}
        assert details["zero_unique_tests"] == 1
        assert "candidates" in details["note"]
        radius_rows = [r for r in reports if r.metrics[0].metric_type is MetricType.BLAST_RADIUS]
        assert radius_rows[0].subject == "src/m.py"  # biggest radius first

    def test_empty_matrix(self) -> None:
        index, cover = redundancy_index(CoverageMatrix())
        assert (index, cover) == (0.0, 0)


class TestCommand:
    def test_default_coverage_directory_resolves_nested_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        seen: list[str] = []

        def fake_load_matrix(coverage_file: object) -> CoverageMatrix:
            seen.append(str(coverage_file))
            return CoverageMatrix(lines_by_test={"tests/test_x.py::test_a": {("src/m.py", 1)}})

        monkeypatch.setattr("antipasta.cli.test_health.load_matrix", fake_load_matrix)
        with runner.isolated_filesystem():
            coverage_dir = Path(".coverage")
            coverage_dir.mkdir()
            (coverage_dir / ".coverage").write_text("")

            result = runner.invoke(cli_command)

        assert result.exit_code == 0
        assert seen == [".coverage/.coverage"]
        assert "Matrix: 1 test contexts" in result.stderr

    def test_directory_without_nested_coverage_file_errors(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path(".coverage").mkdir()

            result = runner.invoke(cli_command)

        assert result.exit_code != 0
        assert ".coverage/.coverage was not found" in result.stderr
