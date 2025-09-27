"""Integration tests for stats command with configuration overrides."""

from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from antipasta.cli.stats import stats


class TestStatsOverrides:
    """Test stats command with configuration overrides."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_include_pattern_override_stats(self) -> None:
        """Test that include patterns work with stats command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            test_file = test_dir / "test_example.py"
            test_file.write_text(
                """
def test_one():
    assert 1 == 1

def test_two():
    for i in range(10):
        if i > 5:
            print(i)
"""
            )

            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            src_file = src_dir / "module.py"
            src_file.write_text(
                """
def calculate(x):
    return x * 2
"""
            )

            # Create gitignore that excludes tests
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("tests/\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # Without override, tests should be ignored
                result = self.runner.invoke(stats, ["-p", "**/*.py", "-d", str(tmpdir)])
                # Should only find src files

                # With include pattern, tests should be included
                result = self.runner.invoke(
                    stats, ["-p", "**/*.py", "-d", str(tmpdir), "--include-pattern", "**/tests/**"]
                )
                assert result.exit_code == 0
                assert "Including patterns: **/tests/**" in result.output

    def test_exclude_pattern_override_stats(self) -> None:
        """Test that additional exclude patterns work with stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            src_file = src_dir / "module.py"
            src_file.write_text("def func():\n    return 42\n")

            generated_dir = Path(tmpdir) / "generated"
            generated_dir.mkdir()
            gen_file = generated_dir / "auto.py"
            gen_file.write_text("# Auto-generated\ndef gen():\n    pass\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # Exclude generated directory
                result = self.runner.invoke(
                    stats,
                    ["-p", "**/*.py", "-d", str(tmpdir), "--exclude-pattern", "**/generated/**"],
                )
                assert result.exit_code == 0
                assert "Additional exclusions: **/generated/**" in result.output

    def test_no_gitignore_flag_stats(self) -> None:
        """Test that --no-gitignore works with stats command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create gitignore
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("build/\n*.pyc\n")

            # Create files
            build_dir = Path(tmpdir) / "build"
            build_dir.mkdir()
            build_file = build_dir / "output.py"
            build_file.write_text("def build_func():\n    pass\n")

            src_file = Path(tmpdir) / "main.py"
            src_file.write_text("def main():\n    pass\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # With --no-gitignore, should include build directory
                result = self.runner.invoke(
                    stats, ["-p", "**/*.py", "-d", str(tmpdir), "--no-gitignore"]
                )
                assert result.exit_code == 0
                assert "Ignoring .gitignore patterns" in result.output

    def test_force_analyze_flag_stats(self) -> None:
        """Test that --force-analyze works with stats command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create various directories
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            test_file = test_dir / "test_all.py"
            test_file.write_text("def test():\n    pass\n")

            vendor_dir = Path(tmpdir) / "vendor"
            vendor_dir.mkdir()
            vendor_file = vendor_dir / "lib.py"
            vendor_file.write_text("def vendor_func():\n    pass\n")

            # Create gitignore
            gitignore = Path(tmpdir) / ".gitignore"
            gitignore.write_text("tests/\nvendor/\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # Force analyze everything
                result = self.runner.invoke(
                    stats, ["-p", "**/*.py", "-d", str(tmpdir), "--force-analyze"]
                )
                assert result.exit_code == 0
                assert "Force analyzing all files (ignoring exclusions)" in result.output

    def test_multiple_patterns_with_overrides(self) -> None:
        """Test multiple patterns combined with overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python files
            py_dir = Path(tmpdir) / "python"
            py_dir.mkdir()
            py_file = py_dir / "module.py"
            py_file.write_text("def py_func():\n    return 'python'\n")

            # Create JavaScript files
            js_dir = Path(tmpdir) / "javascript"
            js_dir.mkdir()
            js_file = js_dir / "module.js"
            js_file.write_text("function jsFunc() {\n    return 'js';\n}\n")

            # Create test files
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()
            test_py = test_dir / "test.py"
            test_py.write_text("def test():\n    assert True\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # Multiple patterns with include override
                result = self.runner.invoke(
                    stats,
                    [
                        "-p",
                        "**/*.py",
                        "-p",
                        "**/*.js",
                        "-d",
                        str(tmpdir),
                        "--include-pattern",
                        "**/tests/**",
                        "--metric",
                        "loc",
                    ],
                )
                assert result.exit_code == 0
                assert "Including patterns: **/tests/**" in result.output

    def test_stats_with_depth_and_overrides(self) -> None:
        """Test directory depth option with overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            deep_path = Path(tmpdir) / "src" / "app" / "modules" / "core"
            deep_path.mkdir(parents=True)
            deep_file = deep_path / "engine.py"
            deep_file.write_text(
                """
def process():
    data = []
    for i in range(100):
        if i % 2 == 0:
            data.append(i)
    return data
"""
            )

            # Ignored by default
            test_path = Path(tmpdir) / "src" / "app" / "tests"
            test_path.mkdir(parents=True)
            test_file = test_path / "test_engine.py"
            test_file.write_text("def test_process():\n    assert True\n")

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_reports: list[Any] = []
                mock_instance.analyze_files.return_value = mock_reports
                mock_aggregator.return_value = mock_instance

                # Test with depth and include pattern
                result = self.runner.invoke(
                    stats,
                    [
                        "-p",
                        "**/*.py",
                        "-d",
                        str(tmpdir),
                        "--by-directory",
                        "--depth",
                        "2",
                        "--include-pattern",
                        "**/tests/**",
                        "--metric",
                        "cyc",
                    ],
                )
                assert result.exit_code == 0

    def test_stats_output_formats_with_overrides(self) -> None:
        """Test different output formats work with overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            src_file = Path(tmpdir) / "main.py"
            src_file.write_text(
                """
def calculate(x, y):
    if x > 0:
        if y > 0:
            return x + y
        return x - y
    return -x
"""
            )

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                mock_instance = MagicMock()
                mock_instance.analyze_files.return_value = []
                mock_aggregator.return_value = mock_instance

                # Test JSON format with overrides
                result = self.runner.invoke(
                    stats,
                    [
                        "-p",
                        "**/*.py",
                        "-d",
                        str(tmpdir),
                        "--format",
                        "json",
                        "--force-analyze",
                        "--metric",
                        "all",
                    ],
                )
                assert result.exit_code == 0

                # Test CSV format with overrides
                result = self.runner.invoke(
                    stats,
                    [
                        "-p",
                        "**/*.py",
                        "-d",
                        str(tmpdir),
                        "--format",
                        "csv",
                        "--no-gitignore",
                        "--metric",
                        "cyc",
                    ],
                )
                assert result.exit_code == 0

                # Test table format (default) with overrides
                result = self.runner.invoke(
                    stats,
                    [
                        "-p",
                        "**/*.py",
                        "-d",
                        str(tmpdir),
                        "--exclude-pattern",
                        "**/build/**",
                        "--metric",
                        "loc",
                    ],
                )
                assert result.exit_code == 0
