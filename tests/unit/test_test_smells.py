"""Tests for track D1 static test smells."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.model.metrics import FileMetrics, MetricType
from antipasta.runners.python.house_style import HouseStyleRunner


def _analyze_as_test_file(source: str) -> FileMetrics:
    return HouseStyleRunner().analyze(Path("tests/unit/test_sample.py"), content=source)


def _value(result: FileMetrics, metric_type: MetricType, name: str) -> float:
    for metric in result.metrics:
        if metric.metric_type is metric_type and metric.function_name == name:
            return metric.value
    raise AssertionError(f"no {metric_type} row for {name}")


class TestSmellRows:
    def test_assertion_count(self) -> None:
        source = (
            "def test_many():\n"
            "    assert 1\n"
            "    assert 2\n"
            "    assert 3\n"
        )
        result = _analyze_as_test_file(source)
        assert _value(result, MetricType.ASSERTIONS_PER_TEST, "test_many") == 3.0

    def test_mock_assertions_counted_twice_over(self) -> None:
        source = (
            "def test_pinned(mock):\n"
            "    mock.assert_called_once_with(1)\n"
            "    mock.assert_has_calls([])\n"
            "    assert mock.value\n"
        )
        result = _analyze_as_test_file(source)
        assert _value(result, MetricType.MOCK_CALL_ASSERTIONS, "test_pinned") == 2.0
        # mock asserts count into the assertion total too
        assert _value(result, MetricType.ASSERTIONS_PER_TEST, "test_pinned") == 3.0

    def test_big_literal_assertion(self) -> None:
        source = (
            "def test_snapshotish(result):\n"
            "    assert result == {'a': 1, 'b': 2, 'c': 3, 'd': 4,\n"
            "                      'e': 5, 'f': 6, 'g': 7, 'h': 8}\n"
        )
        result = _analyze_as_test_file(source)
        assert _value(result, MetricType.BIG_LITERAL_ASSERTIONS, "test_snapshotish") == 1.0

    def test_helper_functions_get_no_smell_rows(self) -> None:
        source = "def helper():\n    assert True\n"
        result = _analyze_as_test_file(source)
        smells = [
            m for m in result.metrics
            if m.metric_type is MetricType.ASSERTIONS_PER_TEST
        ]
        assert smells == []

    def test_source_files_get_no_smell_rows(self) -> None:
        source = "def test_looking_name():\n    assert True\n"
        result = HouseStyleRunner().analyze(Path("src/pkg/engine.py"), content=source)
        smells = [
            m for m in result.metrics
            if m.metric_type is MetricType.ASSERTIONS_PER_TEST
        ]
        assert smells == []
