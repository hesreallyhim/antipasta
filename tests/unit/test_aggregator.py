"""Tests for the metric aggregator."""

from pathlib import Path

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import (
    AntipastaConfig,
    ComparisonOperator,
    LanguageConfig,
    MetricConfig,
)
from antipasta.core.metrics import MetricType


class TestMetricAggregator:
    """Tests for MetricAggregator class."""

    def test_aggregator_initialization(self) -> None:
        """Test creating an aggregator."""
        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        assert aggregator.config == config
        assert aggregator.detector is not None
        assert len(aggregator.runners) > 0

    def test_analyze_simple_python_file(self, tmp_path: Path) -> None:
        """Test analyzing a simple Python file."""
        # Create a simple Python file
        file_path = tmp_path / "simple.py"
        file_path.write_text(
            """
def hello():
    print("Hello, World!")
"""
        )

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([file_path])

        assert len(reports) == 1
        report = reports[0]
        assert report.file_path == file_path
        assert report.language == "python"
        assert len(report.metrics) > 0
        assert not report.has_violations  # Simple function should pass

    def test_analyze_complex_file_with_violations(self, tmp_path: Path) -> None:
        """Test analyzing a file that violates thresholds."""
        # Create a complex Python file
        file_path = tmp_path / "complex.py"
        file_path.write_text(
            """
def complex_function(a, b, c, d):
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    return a + b + c + d
                else:
                    return a + b + c
            else:
                if d > 0:
                    return a + b + d
                else:
                    return a + b
        else:
            if c > 0:
                if d > 0:
                    return a + c + d
                else:
                    return a + c
            else:
                if d > 0:
                    return a + d
                else:
                    return a
    else:
        return 0
"""
        )

        # Create config with low complexity threshold
        config = AntipastaConfig(
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[
                        MetricConfig(
                            type=MetricType.CYCLOMATIC_COMPLEXITY,
                            threshold=5,  # Low threshold
                            comparison=ComparisonOperator.LE,
                        )
                    ],
                )
            ]
        )

        aggregator = MetricAggregator(config)
        reports = aggregator.analyze_files([file_path])

        assert len(reports) == 1
        report = reports[0]
        assert report.has_violations
        assert report.violation_count > 0

        # Check that the violation is for cyclomatic complexity
        violation = report.violations[0]
        assert violation.metric_type == MetricType.CYCLOMATIC_COMPLEXITY
        assert violation.value > 5

    def test_analyze_multiple_files(self, tmp_path: Path) -> None:
        """Test analyzing multiple files."""
        # Create multiple Python files
        file1 = tmp_path / "file1.py"
        file1.write_text("def simple(): return 1")

        file2 = tmp_path / "file2.py"
        file2.write_text("def another(): return 2")

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([file1, file2])

        assert len(reports) == 2
        assert all(report.language == "python" for report in reports)
        assert all(not report.has_violations for report in reports)

    def test_analyze_mixed_languages(self, tmp_path: Path) -> None:
        """Test analyzing files of different languages."""
        # Create Python file
        py_file = tmp_path / "test.py"
        py_file.write_text("def test(): pass")

        # Create JavaScript file (will be skipped as no runner)
        js_file = tmp_path / "test.js"
        js_file.write_text("function test() {}")

        # Create unknown file
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("Hello")

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([py_file, js_file, txt_file])

        # Only Python file should be analyzed
        assert len(reports) == 1
        assert reports[0].file_path == py_file

    def test_analyze_with_ignore_patterns(self, tmp_path: Path) -> None:
        """Test that ignored files are skipped."""
        # Create files
        main_file = tmp_path / "main.py"
        main_file.write_text("def main(): pass")

        test_file = tmp_path / "test_main.py"
        test_file.write_text("def test(): pass")

        config = AntipastaConfig(
            ignore_patterns=["test_*.py"],
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[],
                )
            ],
        )

        aggregator = MetricAggregator(config)
        reports = aggregator.analyze_files([main_file, test_file])

        # Only main.py should be analyzed
        assert len(reports) == 1
        assert reports[0].file_path == main_file

    def test_generate_summary_no_violations(self, tmp_path: Path) -> None:
        """Test generating summary with no violations."""
        file_path = tmp_path / "good.py"
        file_path.write_text("def simple(): return 42")

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([file_path])
        summary = aggregator.generate_summary(reports)

        assert summary["total_files"] == 1
        assert summary["files_with_violations"] == 0
        assert summary["total_violations"] == 0
        assert summary["success"] is True
        assert summary["files_by_language"]["python"] == 1

    def test_generate_summary_with_violations(self, tmp_path: Path) -> None:
        """Test generating summary with violations."""
        # Create a file that violates maintainability index
        file_path = tmp_path / "unmaintainable.py"
        file_path.write_text(
            """
# Very complex and unmaintainable code
def x(a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                if h:
                                    if i:
                                        if j:
                                            if k:
                                                if l:
                                                    if m:
                                                        if n:
                                                            if o:
                                                                if p:
                                                                    return 1
    return 0
"""
        )

        config = AntipastaConfig(
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[
                        MetricConfig(
                            type=MetricType.MAINTAINABILITY_INDEX,
                            threshold=80,  # High threshold
                            comparison=ComparisonOperator.GE,
                        ),
                        MetricConfig(
                            type=MetricType.CYCLOMATIC_COMPLEXITY,
                            threshold=5,
                            comparison=ComparisonOperator.LE,
                        ),
                    ],
                )
            ]
        )

        aggregator = MetricAggregator(config)
        reports = aggregator.analyze_files([file_path])
        summary = aggregator.generate_summary(reports)

        assert summary["total_files"] == 1
        assert summary["files_with_violations"] == 1
        assert summary["total_violations"] > 0
        assert summary["success"] is False
        assert len(summary["violations_by_type"]) > 0

    def test_analyze_nonexistent_file(self) -> None:
        """Test analyzing a file that doesn't exist."""
        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([Path("/nonexistent/file.py")])

        assert len(reports) == 1
        assert reports[0].error is not None
        assert not reports[0].has_violations

    def test_default_config_fallback(self, tmp_path: Path) -> None:
        """Test that defaults are used when no language config exists."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def test(): pass")

        # Config with no language-specific settings
        config = AntipastaConfig(languages=[])
        aggregator = MetricAggregator(config)

        reports = aggregator.analyze_files([file_path])

        assert len(reports) == 1
        # Should still analyze using defaults
        assert len(reports[0].metrics) > 0
