"""Unit tests for ComplexipyRunner (in-process API).

The runner imports complexipy as a library, so these tests analyze real
source instead of mocking subprocess plumbing — the analysis is fast enough
to run for real, and real runs can't drift from the implementation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from antipasta.core.detector import Language
from antipasta.core.metrics import MetricType
from antipasta.runners.python.complexipy_runner import ComplexipyRunner

NESTED_SOURCE = """\
def simple_function(x):
    return x + 1


def nested_function(items, flag):
    total = 0
    for item in items:
        if flag:
            if item > 0:
                total += item
    return total
"""


class TestComplexipyRunner:
    """Tests for ComplexipyRunner."""

    @pytest.fixture
    def runner(self) -> ComplexipyRunner:
        """Create a ComplexipyRunner instance."""
        return ComplexipyRunner()

    def test_supported_metrics(self, runner: ComplexipyRunner) -> None:
        """Test that runner reports supported metrics."""
        assert runner.supported_metrics == [MetricType.COGNITIVE_COMPLEXITY.value]

    def test_is_available_true(self, runner: ComplexipyRunner) -> None:
        """Complexipy is a hard dependency, so the import check succeeds."""
        assert runner.is_available() is True
        assert runner.is_available() is True  # cached second call

    def test_is_available_caches_false(self, runner: ComplexipyRunner) -> None:
        """A failed availability check is cached, not retried."""
        runner._available = False
        assert runner.is_available() is False

    def test_analyze_not_available(self, runner: ComplexipyRunner) -> None:
        """Test analyze when complexipy is not available."""
        runner._available = False
        result = runner.analyze(Path("test.py"))

        assert result.language == Language.PYTHON.value
        assert result.metrics == []
        assert result.error == "Complexipy is not installed. Install with: pip install complexipy"

    def test_analyze_from_file(self, runner: ComplexipyRunner, tmp_path: Path) -> None:
        """Analyzing a real file yields per-function rows plus a file maximum."""
        source_file = tmp_path / "sample.py"
        source_file.write_text(NESTED_SOURCE)

        result = runner.analyze(source_file)

        assert result.error is None
        assert len(result.metrics) == 3  # 2 functions + file maximum
        by_name = {m.function_name: m for m in result.metrics if m.function_name}
        assert by_name["simple_function"].value == 0.0
        assert by_name["nested_function"].value > 0.0
        assert all(m.metric_type == MetricType.COGNITIVE_COMPLEXITY for m in result.metrics)

    def test_analyze_with_content_skips_disk(self, runner: ComplexipyRunner) -> None:
        """Pre-loaded content is analyzed directly; the path need not exist."""
        result = runner.analyze(Path("not/on/disk.py"), content=NESTED_SOURCE)

        assert result.error is None
        assert len(result.metrics) == 3

    def test_file_maximum_row(self, runner: ComplexipyRunner) -> None:
        """The file-maximum row carries the max value and the function count."""
        result = runner.analyze(Path("mem.py"), content=NESTED_SOURCE)

        maximum = result.metrics[-1]
        assert maximum.details is not None
        assert maximum.details["type"] == "file_maximum"
        assert maximum.details["function_count"] == 2
        assert maximum.value == max(m.value for m in result.metrics[:-1])

    def test_function_rows_carry_line_numbers(self, runner: ComplexipyRunner) -> None:
        """The in-process API provides line numbers the CLI JSON lacked."""
        result = runner.analyze(Path("mem.py"), content=NESTED_SOURCE)

        function_rows = [m for m in result.metrics if m.function_name]
        assert all(isinstance(m.line_number, int) and m.line_number > 0 for m in function_rows)

    def test_unparseable_source_yields_no_metrics(self, runner: ComplexipyRunner) -> None:
        """Broken source produces an empty metric list, not a crash."""
        result = runner.analyze(Path("broken.py"), content="def broken(:\n")

        assert result.metrics == []

    def test_missing_file_yields_no_metrics(self, runner: ComplexipyRunner) -> None:
        """A nonexistent path (without content) produces no metrics."""
        result = runner.analyze(Path("definitely/not/here.py"))

        assert result.metrics == []

    def test_import_failure_marks_unavailable(self) -> None:
        """If the complexipy import fails, the runner reports unavailable."""
        runner = ComplexipyRunner()
        with patch.dict("sys.modules", {"complexipy": None}):
            assert runner.is_available() is False
