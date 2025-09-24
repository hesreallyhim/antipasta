"""Tests for the metrics CLI command."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from antipasta.cli.metrics import metrics


class TestMetricsCommandValidation:
    """Test validation of file and directory arguments."""

    def test_file_flag_rejects_directory(self) -> None:
        """Test that -f/--files flag rejects directories with proper error."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory to test against
            test_dir = Path(tmpdir) / "test_dir"
            test_dir.mkdir()

            result = runner.invoke(metrics, ["-f", str(test_dir)])

            assert result.exit_code != 0
            assert "Error: Invalid value for '--files' / '-f'" in result.output
            assert f"File '{test_dir}' is a directory" in result.output

    def test_directory_flag_rejects_file(self) -> None:
        """Test that -d/--directory flag rejects files with proper error."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to test against
            test_file = Path(tmpdir) / "test_file.py"
            test_file.write_text("# test content\n")

            result = runner.invoke(metrics, ["-d", str(test_file)])

            assert result.exit_code != 0
            assert "Error: Invalid value for '--directory' / '-d'" in result.output
            assert f"Directory '{test_file}' is a file" in result.output

    def test_file_flag_accepts_valid_file(self) -> None:
        """Test that -f/--files flag accepts valid files."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file
            test_file = Path(tmpdir) / "test_file.py"
            test_file.write_text("def hello():\n    return 'world'\n")

            # Create a minimal config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
            )

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                # Mock the analyzer to avoid actual metric computation
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

                result = runner.invoke(metrics, ["-f", str(test_file), "-c", str(config_file)])

                assert result.exit_code == 0
                assert "Analyzing 1 files" in result.output

    def test_directory_flag_accepts_valid_directory(self) -> None:
        """Test that -d/--directory flag accepts valid directories."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory with Python files
            test_dir = Path(tmpdir) / "src"
            test_dir.mkdir()

            test_file = test_dir / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")

            # Create a minimal config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
            )

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
                # Mock the analyzer
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

                result = runner.invoke(metrics, ["-d", str(test_dir), "-c", str(config_file)])

                assert result.exit_code == 0
                assert "Analyzing 1 files" in result.output

    def test_multiple_file_flags(self) -> None:
        """Test that multiple -f flags can be specified."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple Python files
            file1 = Path(tmpdir) / "file1.py"
            file1.write_text("def func1():\n    pass\n")

            file2 = Path(tmpdir) / "file2.py"
            file2.write_text("def func2():\n    pass\n")

            # Create config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
            )

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
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

                result = runner.invoke(
                    metrics, ["-f", str(file1), "-f", str(file2), "-c", str(config_file)]
                )

                assert result.exit_code == 0
                assert "Analyzing 2 files" in result.output

    def test_nonexistent_file_error(self) -> None:
        """Test that nonexistent file paths produce proper error."""
        runner = CliRunner()
        result = runner.invoke(metrics, ["-f", "/nonexistent/file.py"])

        assert result.exit_code != 0
        assert "Error: Invalid value for '--files' / '-f'" in result.output
        assert "does not exist" in result.output

    def test_nonexistent_directory_error(self) -> None:
        """Test that nonexistent directory paths produce proper error."""
        runner = CliRunner()
        result = runner.invoke(metrics, ["-d", "/nonexistent/directory"])

        assert result.exit_code != 0
        assert "Error: Invalid value for '--directory' / '-d'" in result.output
        assert "does not exist" in result.output

    def test_mixed_file_and_directory_flags(self) -> None:
        """Test that both -f and -d flags can be used together."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file and a directory with a file
            single_file = Path(tmpdir) / "single.py"
            single_file.write_text("def single():\n    pass\n")

            test_dir = Path(tmpdir) / "src"
            test_dir.mkdir()
            dir_file = test_dir / "module.py"
            dir_file.write_text("def module():\n    pass\n")

            # Create config
            config_file = Path(tmpdir) / ".antipasta.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
"""
            )

            with patch("antipasta.core.aggregator.MetricAggregator") as mock_aggregator:
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

                result = runner.invoke(
                    metrics, ["-f", str(single_file), "-d", str(test_dir), "-c", str(config_file)]
                )

                assert result.exit_code == 0
                assert "Analyzing 2 files" in result.output
