"""Unit tests for LizardRunner (JavaScript/TypeScript support)."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from antipasta.core.metrics import MetricType
from antipasta.runners.javascript.lizard_runner import LizardRunner

TS_FIXTURE = """\
export function pickFirst(items: number[] | null): number | null {
  if (items && items.length) {
    for (const item of items) {
      if (item > 2) {
        return item ? 1 : 0;
      }
    }
  }
  return null;
}
"""

TSX_FIXTURE = """\
export function Widget({ items }: { items: string[] }) {
  if (!items.length) {
    return null;
  }
  return items.map((item) => item.toUpperCase());
}
"""

JSX_FIXTURE = """\
function renderList(items) {
  if (!items) {
    return [];
  }
  return items.filter((item) => item && item.visible);
}
"""


class TestLizardRunner:
    """Tests for LizardRunner."""

    @pytest.fixture
    def runner(self) -> LizardRunner:
        """Create a LizardRunner instance."""
        return LizardRunner()

    def test_supported_metrics(self, runner: LizardRunner) -> None:
        """Test that the runner reports its supported metrics."""
        assert runner.supported_metrics == [
            MetricType.CYCLOMATIC_COMPLEXITY.value,
            MetricType.SOURCE_LINES_OF_CODE.value,
            MetricType.LINES_OF_CODE.value,
        ]

    def test_is_available(self, runner: LizardRunner) -> None:
        """Test availability when lizard is installed (it is a dependency)."""
        assert runner.is_available() is True

    def test_is_available_false_when_import_fails(self) -> None:
        """Test the graceful path when the lizard import fails."""
        runner = LizardRunner()
        # None in sys.modules makes `import lizard` raise ImportError.
        with patch.dict(sys.modules, {"lizard": None}):
            assert runner.is_available() is False
        # The result is cached, so it stays unavailable afterwards.
        assert runner.is_available() is False

    def test_analyze_not_available(self) -> None:
        """Test analyze when lizard is not available."""
        runner = LizardRunner()
        runner._available = False

        result = runner.analyze(Path("sample.ts"), content=TS_FIXTURE)

        assert result.language == "typescript"
        assert result.metrics == []
        assert result.error == "lizard is not installed. Install with: pip install lizard"

    def test_analyze_typescript_function(self, runner: LizardRunner) -> None:
        """Test per-function cyclomatic complexity rows for a .ts file."""
        result = runner.analyze(Path("sample.ts"), content=TS_FIXTURE)

        assert result.error is None
        assert result.language == "typescript"

        function_rows = [
            m
            for m in result.metrics
            if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY and m.function_name is not None
        ]
        assert len(function_rows) == 1
        row = function_rows[0]
        assert row.function_name == "pickFirst"
        assert row.line_number == 1
        assert row.value >= 4  # if + for + if + ternary branches
        assert row.details is not None
        assert row.details["analyzer"] == "lizard"
        assert row.details["type"] == "function"
        assert row.details["end_line"] >= row.line_number

    def test_analyze_emits_average_and_line_counts(self, runner: LizardRunner) -> None:
        """Test the file-level average row and line-count metrics."""
        result = runner.analyze(Path("sample.ts"), content=TS_FIXTURE)

        average_rows = [
            m
            for m in result.metrics
            if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY and m.function_name is None
        ]
        assert len(average_rows) == 1
        assert average_rows[0].details is not None
        assert average_rows[0].details["type"] == "average"
        assert average_rows[0].details["function_count"] == 1

        sloc = [m for m in result.metrics if m.metric_type == MetricType.SOURCE_LINES_OF_CODE]
        loc = [m for m in result.metrics if m.metric_type == MetricType.LINES_OF_CODE]
        assert len(sloc) == 1
        assert len(loc) == 1
        assert sloc[0].value > 0
        assert loc[0].value == float(len(TS_FIXTURE.splitlines()))

    def test_analyze_tsx_language(self, runner: LizardRunner) -> None:
        """Test that .tsx files are detected as TypeScript and analyzed."""
        result = runner.analyze(Path("component.tsx"), content=TSX_FIXTURE)

        assert result.error is None
        assert result.language == "typescript"
        names = {m.function_name for m in result.metrics if m.function_name}
        assert "Widget" in names

    def test_analyze_jsx_language(self, runner: LizardRunner) -> None:
        """Test that .jsx files are detected as JavaScript and analyzed."""
        result = runner.analyze(Path("list.jsx"), content=JSX_FIXTURE)

        assert result.error is None
        assert result.language == "javascript"
        names = {m.function_name for m in result.metrics if m.function_name}
        assert "renderList" in names

    def test_analyze_mjs_language(self, runner: LizardRunner) -> None:
        """Test that .mjs module files are detected as JavaScript and analyzed."""
        result = runner.analyze(Path("module.mjs"), content=JSX_FIXTURE)

        assert result.error is None
        assert result.language == "javascript"
        names = {m.function_name for m in result.metrics if m.function_name}
        assert "renderList" in names

    def test_analyze_reads_file_from_disk(self, runner: LizardRunner, tmp_path: Path) -> None:
        """Test analysis when content is loaded from the file itself."""
        source = tmp_path / "sample.ts"
        source.write_text(TS_FIXTURE)

        result = runner.analyze(source)

        assert result.error is None
        assert any(m.function_name == "pickFirst" for m in result.metrics)

    def test_analyze_missing_file(self, runner: LizardRunner, tmp_path: Path) -> None:
        """Test the read-error path for a nonexistent file."""
        result = runner.analyze(tmp_path / "missing.ts")

        assert result.metrics == []
        assert result.error is not None
        assert result.error.startswith("Failed to read file")
