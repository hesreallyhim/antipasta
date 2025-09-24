"""Unit tests for ComplexipyRunner."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

from antipasta.core.detector import Language
from antipasta.core.metrics import MetricType
from antipasta.runners.python.complexipy_runner import ComplexipyRunner


class TestComplexipyRunner:
    """Tests for ComplexipyRunner."""

    @pytest.fixture
    def runner(self) -> ComplexipyRunner:
        """Create a ComplexipyRunner instance."""
        return ComplexipyRunner()

    def test_supported_metrics(self, runner: ComplexipyRunner) -> None:
        """Test that runner reports supported metrics."""
        assert runner.supported_metrics == [MetricType.COGNITIVE_COMPLEXITY.value]

    @patch("subprocess.run")
    def test_is_available_true(self, mock_run: MagicMock, runner: ComplexipyRunner) -> None:
        """Test availability check when complexipy is installed."""
        mock_run.return_value.returncode = 0
        assert runner.is_available() is True

        # Should cache the result
        assert runner.is_available() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_is_available_false(self, mock_run: MagicMock, runner: ComplexipyRunner) -> None:
        """Test availability check when complexipy is not installed."""
        mock_run.side_effect = FileNotFoundError()
        assert runner.is_available() is False

        # Should cache the result
        assert runner.is_available() is False
        mock_run.assert_called_once()

    def test_analyze_not_available(self, runner: ComplexipyRunner) -> None:
        """Test analyze when complexipy is not available."""
        runner._available = False
        result = runner.analyze(Path("test.py"))

        assert result.language == Language.PYTHON.value
        assert result.metrics == []
        assert result.error == "Complexipy is not installed. Install with: pip install complexipy"

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_analyze_simple_function(
        self,
        mock_unlink: MagicMock,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        runner: ComplexipyRunner,
    ) -> None:
        """Test analyzing a simple function."""
        # Mock subprocess output
        mock_run.return_value.returncode = 0

        # Mock JSON file existence and content
        mock_exists.return_value = True
        mock_json_data = [
            {
                "complexity": 5,
                "file_name": "test.py",
                "function_name": "simple_function",
                "path": "test.py",
            }
        ]

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_json_data))):
            result = runner.analyze(Path("test.py"))

        assert len(result.metrics) == 2  # Function + file maximum

        # Check function metric
        func_metric = result.metrics[0]
        assert func_metric.metric_type == MetricType.COGNITIVE_COMPLEXITY
        assert func_metric.value == 5.0
        assert func_metric.function_name == "simple_function"

        # Check file maximum metric
        file_metric = result.metrics[1]
        assert file_metric.metric_type == MetricType.COGNITIVE_COMPLEXITY
        assert file_metric.value == 5.0
        assert file_metric.details is not None
        assert file_metric.details["type"] == "file_maximum"

        # Verify cleanup
        mock_unlink.assert_called_once()

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_analyze_multiple_functions(
        self,
        mock_unlink: MagicMock,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        runner: ComplexipyRunner,
    ) -> None:
        """Test analyzing multiple functions."""
        mock_run.return_value.returncode = 0
        mock_exists.return_value = True

        mock_json_data = [
            {"complexity": 3, "file_name": "test.py", "function_name": "func1", "path": "test.py"},
            {"complexity": 10, "file_name": "test.py", "function_name": "func2", "path": "test.py"},
            {"complexity": 7, "file_name": "test.py", "function_name": "func3", "path": "test.py"},
        ]

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_json_data))):
            result = runner.analyze(Path("test.py"))

        assert len(result.metrics) == 4  # 3 functions + 1 file maximum

        # Check maximum is correct
        file_metric = result.metrics[-1]
        assert file_metric.value == 10.0  # Maximum complexity
        assert file_metric.details is not None
        assert file_metric.details["function_count"] == 3

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_analyze_json_parse_error(
        self, mock_exists: MagicMock, mock_run: MagicMock, runner: ComplexipyRunner
    ) -> None:
        """Test handling of JSON parse errors."""
        mock_run.return_value.returncode = 0
        mock_exists.return_value = True

        with patch("builtins.open", mock_open(read_data="invalid json")):
            result = runner.analyze(Path("test.py"))

        assert result.metrics == []
        assert result.error is None  # No error reported, just empty metrics

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_analyze_no_json_file(
        self, mock_exists: MagicMock, mock_run: MagicMock, runner: ComplexipyRunner
    ) -> None:
        """Test when complexipy doesn't create JSON file."""
        mock_run.return_value.returncode = 0
        mock_exists.return_value = False  # JSON file doesn't exist

        result = runner.analyze(Path("test.py"))

        assert result.metrics == []
        assert result.error is None

    @patch("subprocess.run")
    def test_analyze_subprocess_error(self, mock_run: MagicMock, runner: ComplexipyRunner) -> None:
        """Test handling of subprocess errors."""
        # First call is for is_available check, second is for analyze
        mock_run.side_effect = [
            MagicMock(returncode=0),  # is_available check
            subprocess.SubprocessError("Command failed"),  # analyze call
        ]

        result = runner.analyze(Path("test.py"))

        assert result.metrics == []
        assert result.error is None  # Errors are silently ignored

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_analyze_high_complexity_exit_code(
        self,
        mock_unlink: MagicMock,
        mock_exists: MagicMock,
        mock_run: MagicMock,
        runner: ComplexipyRunner,
    ) -> None:
        """Test that non-zero exit code doesn't prevent processing."""
        # Mock is_available check first, then complexipy command
        mock_run.side_effect = [
            MagicMock(returncode=0),  # is_available check
            MagicMock(returncode=1),  # complexipy command (returns non-zero for high complexity)
        ]
        mock_exists.return_value = True

        mock_json_data = [
            {
                "complexity": 50,
                "file_name": "test.py",
                "function_name": "complex_function",
                "path": "test.py",
            }
        ]

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_json_data))):
            result = runner.analyze(Path("test.py"))

        assert len(result.metrics) == 2
        assert result.metrics[0].value == 50.0
