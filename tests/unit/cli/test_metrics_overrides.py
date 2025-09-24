"""Integration tests for metrics command with configuration overrides."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from antipasta.cli.metrics import metrics
from antipasta.core.config import ComparisonOperator
from antipasta.core.metrics import MetricType
from antipasta.core.violations import Violation


class TestMetricsOverrides:
    """Test metrics command with configuration overrides."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_include_pattern_override(self) -> None:
        """Test that include patterns override ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            test_file = test_dir / "test_example.py"
            test_file.write_text("def test_func():\n    pass\n")

            # Create config that ignores tests
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
ignore_patterns:
  - "**/tests/**"
"""
            )

            with patch(
                "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
            ) as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_instance.generate_summary.return_value = {
                    "success": True,
                    "total_files": 1,
                    "files_with_violations": 0,
                    "total_violations": 0,
                    "violations_by_type": {},
                }
                mock_aggregator.return_value = mock_instance

                # Without override, tests should be ignored
                result = self.runner.invoke(metrics, ["-d", str(tmpdir), "-c", str(config_file)])
                assert "No files found to analyze" in result.output

                # With include pattern, tests should be analyzed
                result = self.runner.invoke(
                    metrics,
                    ["-d", str(tmpdir), "-c", str(config_file), "--include-pattern", "**/tests/**"],
                )
                assert result.exit_code == 0
                assert "Including patterns: **/tests/**" in result.output
                mock_instance.analyze_files.assert_called()

    def test_exclude_pattern_override(self) -> None:
        """Test that additional exclude patterns work."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Create test files
                src_dir = Path(tmpdir) / "src"
                src_dir.mkdir()
                src_file = src_dir / "module.py"
                src_file.write_text("def func():\n    pass\n")

                build_dir = Path(tmpdir) / "build"
                build_dir.mkdir()
                build_file = build_dir / "generated.py"
                build_file.write_text("def gen_func():\n    pass\n")

                # Create minimal config
                config_file = Path(tmpdir) / ".antipasta.yaml"
                config_file.write_text(
                    """
defaults:
  max_cyclomatic_complexity: 10
languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
                )

                with patch(
                    "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
                ) as mock_aggregator:
                    mock_instance = MagicMock()
                    mock_instance.analyze_files.return_value = []
                    mock_instance.generate_summary.return_value = {
                        "success": True,
                        "total_files": 1,
                        "files_with_violations": 0,
                        "total_violations": 0,
                        "violations_by_type": {},
                    }
                    mock_aggregator.return_value = mock_instance

                    # With exclude pattern, build directory should be ignored
                    result = self.runner.invoke(
                        metrics,
                        ["-d", ".", "-c", ".antipasta.yaml", "--exclude-pattern", "**/build/**"],
                    )
                    if result.exit_code != 0:
                        print("Error output:", result.output)
                    assert result.exit_code == 0
                    assert "Additional exclusions: **/build/**" in result.output
            finally:
                os.chdir(old_cwd)

    def test_threshold_override(self) -> None:
        """Test that threshold overrides work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "complex.py"
            test_file.write_text(
                """
def complex_func(x):
    if x > 0:
        if x > 10:
            if x > 20:
                return "big"
            return "medium"
        return "small"
    return "negative"
"""
            )

            # Create config with strict threshold
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 3
languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 3
        comparison: "<="
"""
            )

            with patch(
                "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
            ) as mock_aggregator:
                mock_instance = MagicMock()

                # First call: with strict threshold (should fail)
                violation_report = MagicMock()
                violation_report.has_violations = True
                violation_report.violations = [
                    Violation(
                        metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                        message="Function 'complex_func' has cyclomatic complexity 5 "
                        "(threshold: 3)",
                        file_path=test_file,
                        line_number=1,
                        function_name="complex_func",
                        value=5.0,
                        threshold=3.0,
                        comparison=ComparisonOperator.LE,
                    )
                ]
                mock_instance.analyze_files.return_value = [violation_report]
                mock_instance.generate_summary.return_value = {
                    "success": False,
                    "total_files": 1,
                    "files_with_violations": 1,
                    "total_violations": 1,
                    "violations_by_type": {"cyclomatic_complexity": 1},
                }
                mock_aggregator.return_value = mock_instance

                # Run with default strict threshold
                result = self.runner.invoke(metrics, ["-f", str(test_file), "-c", str(config_file)])
                assert result.exit_code == 2  # Violation found
                assert "VIOLATIONS FOUND" in result.output

                # Run with overridden threshold
                mock_instance.analyze_files.return_value = []
                mock_instance.generate_summary.return_value = {
                    "success": True,
                    "total_files": 1,
                    "files_with_violations": 0,
                    "total_violations": 0,
                    "violations_by_type": {},
                }

                result = self.runner.invoke(
                    metrics,
                    [
                        "-f",
                        str(test_file),
                        "-c",
                        str(config_file),
                        "--threshold",
                        "cyclomatic_complexity=10",
                    ],
                )
                assert result.exit_code == 0  # Should pass with higher threshold
                assert "Threshold overrides: cyclomatic_complexity=10" in result.output

    def test_no_gitignore_flag(self) -> None:
        """Test that --no-gitignore flag disables gitignore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create gitignore
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("ignored.py\n")

            # Create files
            normal_file = Path(tmpdir) / "normal.py"
            normal_file.write_text("def func():\n    pass\n")

            ignored_file = Path(tmpdir) / "ignored.py"
            ignored_file.write_text("def ignored_func():\n    pass\n")

            # Create config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
use_gitignore: true
"""
            )

            with patch(
                "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
            ) as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_instance.generate_summary.return_value = {
                    "success": True,
                    "total_files": 2,
                    "files_with_violations": 0,
                    "total_violations": 0,
                    "violations_by_type": {},
                }
                mock_aggregator.return_value = mock_instance

                # With --no-gitignore, should analyze ignored files
                result = self.runner.invoke(
                    metrics, ["-d", str(tmpdir), "-c", str(config_file), "--no-gitignore"]
                )
                assert result.exit_code == 0
                assert "Ignoring .gitignore patterns" in result.output

    def test_force_analyze_flag(self) -> None:
        """Test that --force-analyze ignores all exclusions."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Create test structure
                test_dir = Path(tmpdir) / "tests"
                test_dir.mkdir()
                test_file = test_dir / "test_example.py"
                test_file.write_text("def test_func():\n    pass\n")

                build_dir = Path(tmpdir) / "build"
                build_dir.mkdir()
                build_file = build_dir / "generated.py"
                build_file.write_text("def gen_func():\n    pass\n")

                normal_file = Path(tmpdir) / "main.py"
                normal_file.write_text("def main():\n    pass\n")

                # Create config that excludes tests and build
                config_file = Path(tmpdir) / ".antipasta.yaml"
                config_file.write_text(
                    """
defaults:
  max_cyclomatic_complexity: 10
languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
ignore_patterns:
  - "**/tests/**"
  - "**/build/**"
"""
                )

                with patch(
                    "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
                ) as mock_aggregator:
                    mock_instance = MagicMock()
                    mock_instance.analyze_files.return_value = []
                    mock_instance.generate_summary.return_value = {
                        "success": True,
                        "total_files": 3,  # Should analyze all 3 files
                        "files_with_violations": 0,
                        "total_violations": 0,
                        "violations_by_type": {},
                    }
                    mock_aggregator.return_value = mock_instance

                    # With --force-analyze, should analyze everything
                    result = self.runner.invoke(
                        metrics, ["-d", ".", "-c", ".antipasta.yaml", "--force-analyze"]
                    )
                    if result.exit_code != 0:
                        print("Error output:", result.output)
                    assert result.exit_code == 0
                    assert "Force analyzing all files (ignoring exclusions)" in result.output
            finally:
                os.chdir(old_cwd)

    def test_multiple_overrides_combined(self) -> None:
        """Test combining multiple override types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            test_file = test_dir / "test_complex.py"
            test_file.write_text(
                """
def test_complex():
    for i in range(10):
        if i % 2 == 0:
            if i > 5:
                print(i)
"""
            )

            # Create config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 3
  min_maintainability_index: 70
languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 3
        comparison: "<="
      - type: maintainability_index
        threshold: 70
        comparison: ">="
ignore_patterns:
  - "**/tests/**"
use_gitignore: true
"""
            )

            with patch(
                "antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator"
            ) as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_instance.generate_summary.return_value = {
                    "success": True,
                    "total_files": 1,
                    "files_with_violations": 0,
                    "total_violations": 0,
                    "violations_by_type": {},
                }
                mock_aggregator.return_value = mock_instance

                # Combine multiple overrides
                result = self.runner.invoke(
                    metrics,
                    [
                        "-d",
                        str(tmpdir),
                        "-c",
                        str(config_file),
                        "--include-pattern",
                        "**/tests/**",
                        "--threshold",
                        "cyclomatic_complexity=10",
                        "--threshold",
                        "maintainability_index=40",
                        "--no-gitignore",
                    ],
                )
                assert result.exit_code == 0
                assert "Including patterns: **/tests/**" in result.output
                assert (
                    "Threshold overrides: cyclomatic_complexity=10, maintainability_index=40"
                    in result.output
                )
                assert "Ignoring .gitignore patterns" in result.output

    def test_invalid_threshold_format(self) -> None:
        """Test error handling for invalid threshold format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
            )

            # Invalid format (no equals sign)
            result = self.runner.invoke(
                metrics, ["-c", str(config_file), "--threshold", "cyclomatic_complexity"]
            )
            assert result.exit_code == 1
            assert "Error" in result.output
            assert "Expected 'metric_type=value'" in result.output

            # Invalid metric type
            result = self.runner.invoke(
                metrics, ["-c", str(config_file), "--threshold", "invalid_metric=10"]
            )
            assert result.exit_code == 1
            assert "Error" in result.output
            assert "Invalid metric type" in result.output

            # Invalid value
            result = self.runner.invoke(
                metrics, ["-c", str(config_file), "--threshold", "cyclomatic_complexity=abc"]
            )
            assert result.exit_code == 1
            assert "Error" in result.output
            assert "Must be a number" in result.output
