"""Unit tests for ComplexipyRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def test_resolve_executable_prefers_sibling(self, tmp_path: Path) -> None:
        """Test that sibling executable to sys.executable is preferred."""
        fake_python = tmp_path / "venv" / "bin" / "python"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_text("")
        sibling_complexipy = fake_python.with_name("complexipy")
        sibling_complexipy.write_text("")

        runner = ComplexipyRunner()
        with patch("sys.executable", str(fake_python)), patch("shutil.which", return_value=None):
            resolved = runner._resolve_complexipy_executable()

        assert resolved == sibling_complexipy

    def test_resolve_executable_falls_back_to_path(self) -> None:
        """Test fallback resolution via PATH when sibling executable is missing."""
        runner = ComplexipyRunner()
        with (
            patch("sys.executable", "/tmp/fake-python"),
            patch("pathlib.Path.exists", return_value=False),
            patch("shutil.which", return_value="/usr/local/bin/complexipy"),
        ):
            resolved = runner._resolve_complexipy_executable()

        assert resolved == Path("/usr/local/bin/complexipy")

    @patch("subprocess.run")
    def test_is_available_true(self, mock_run: MagicMock, runner: ComplexipyRunner) -> None:
        """Test availability check when complexipy is available."""
        mock_run.return_value.returncode = 0

        with patch.object(runner, "_get_complexipy_command", return_value=["/tmp/complexipy"]):
            assert runner.is_available() is True
            assert runner.is_available() is True

        mock_run.assert_called_once()

    def test_is_available_false_no_command(self, runner: ComplexipyRunner) -> None:
        """Test availability check when command cannot be resolved."""
        with patch.object(runner, "_get_complexipy_command", return_value=None):
            assert runner.is_available() is False
            assert runner.is_available() is False

    def test_analyze_not_available(self, runner: ComplexipyRunner) -> None:
        """Test analyze when complexipy is not available."""
        runner._available = False
        result = runner.analyze(Path("test.py"))

        assert result.language == Language.PYTHON.value
        assert result.metrics == []
        assert result.error == "Complexipy is not installed. Install with: pip install complexipy"

    def test_analyze_simple_function(self, runner: ComplexipyRunner) -> None:
        """Test analyzing a simple function."""
        with patch.object(
            runner,
            "_run_complexipy_command",
            return_value=[
                {
                    "complexity": 5,
                    "file_name": "test.py",
                    "function_name": "simple_function",
                    "path": "test.py",
                }
            ],
        ):
            result = runner.analyze(Path("test.py"))

        assert len(result.metrics) == 2  # function + file maximum
        assert result.metrics[0].metric_type == MetricType.COGNITIVE_COMPLEXITY
        assert result.metrics[0].value == 5.0
        assert result.metrics[0].function_name == "simple_function"
        assert result.metrics[1].details is not None
        assert result.metrics[1].details["type"] == "file_maximum"

    def test_analyze_multiple_functions(self, runner: ComplexipyRunner) -> None:
        """Test analyzing multiple functions."""
        with patch.object(
            runner,
            "_run_complexipy_command",
            return_value=[
                {
                    "complexity": 3,
                    "file_name": "test.py",
                    "function_name": "func1",
                    "path": "test.py",
                },
                {
                    "complexity": 10,
                    "file_name": "test.py",
                    "function_name": "func2",
                    "path": "test.py",
                },
                {
                    "complexity": 7,
                    "file_name": "test.py",
                    "function_name": "func3",
                    "path": "test.py",
                },
            ],
        ):
            result = runner.analyze(Path("test.py"))

        assert len(result.metrics) == 4  # 3 functions + 1 file maximum
        assert result.metrics[-1].value == 10.0
        assert result.metrics[-1].details is not None
        assert result.metrics[-1].details["function_count"] == 3

    @patch("subprocess.run")
    def test_run_command_uses_temp_dir_and_no_workspace_artifact(
        self, mock_run: MagicMock, tmp_path: Path, runner: ComplexipyRunner
    ) -> None:
        """Test that JSON output is read from a temp dir, not workspace."""
        source_file = tmp_path / "sample.py"
        source_file.write_text("def sample():\n    return 1\n")
        workspace_json = tmp_path / "complexipy.json"
        assert not workspace_json.exists()

        runner._command = ["/tmp/complexipy"]

        def side_effect(*_args: object, **kwargs: object) -> MagicMock:
            cwd = kwargs.get("cwd")
            assert isinstance(cwd, str)
            output_file = Path(cwd) / "complexipy.json"
            output_file.write_text(
                json.dumps(
                    [
                        {
                            "complexity": 2,
                            "file_name": str(source_file),
                            "function_name": "sample",
                            "path": str(source_file),
                        }
                    ]
                )
            )
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        data = runner._run_complexipy_command(source_file)

        assert data is not None
        assert data[0]["complexity"] == 2
        assert not workspace_json.exists()

        args, kwargs = mock_run.call_args
        command = args[0]
        assert isinstance(command, list)
        assert command[-1] == str(source_file.resolve())
        assert "cwd" in kwargs
        assert kwargs["cwd"] != str(tmp_path)

    @patch("subprocess.run")
    def test_run_command_json_parse_error(
        self, mock_run: MagicMock, tmp_path: Path, runner: ComplexipyRunner
    ) -> None:
        """Test handling invalid JSON output."""
        source_file = tmp_path / "invalid.py"
        source_file.write_text("def invalid():\n    pass\n")
        runner._command = ["/tmp/complexipy"]

        def side_effect(*_args: object, **kwargs: object) -> MagicMock:
            cwd = kwargs.get("cwd")
            assert isinstance(cwd, str)
            (Path(cwd) / "complexipy.json").write_text("invalid json")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        assert runner._run_complexipy_command(source_file) is None

    @patch("subprocess.run")
    def test_run_command_no_json_file(
        self, mock_run: MagicMock, tmp_path: Path, runner: ComplexipyRunner
    ) -> None:
        """Test handling when complexipy does not emit a JSON file."""
        source_file = tmp_path / "missing.py"
        source_file.write_text("def missing():\n    pass\n")
        runner._command = ["/tmp/complexipy"]

        mock_run.return_value = MagicMock(returncode=0)

        assert runner._run_complexipy_command(source_file) is None

    @patch("subprocess.run")
    def test_run_command_supports_timestamped_output_file(
        self, mock_run: MagicMock, tmp_path: Path, runner: ComplexipyRunner
    ) -> None:
        """Test support for complexipy 5.x timestamped JSON output files."""
        source_file = tmp_path / "sample_v5.py"
        source_file.write_text("def sample_v5():\n    return 2\n")
        runner._command = ["/tmp/complexipy"]

        def side_effect(*_args: object, **kwargs: object) -> MagicMock:
            cwd = kwargs.get("cwd")
            assert isinstance(cwd, str)
            output_file = Path(cwd) / "complexipy_results_20260322010000.json"
            output_file.write_text(
                json.dumps(
                    [
                        {
                            "complexity": 4,
                            "file_name": str(source_file),
                            "function_name": "sample_v5",
                            "path": str(source_file),
                        }
                    ]
                )
            )
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        data = runner._run_complexipy_command(source_file)

        assert data is not None
        assert data[0]["complexity"] == 4
