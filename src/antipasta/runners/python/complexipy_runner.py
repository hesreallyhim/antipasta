"""Python cognitive complexity runner using Complexipy."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

from antipasta.core.detector import Language
from antipasta.core.metrics import FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner


class ComplexipyRunner(BaseRunner):
    """Runner for Python cognitive complexity using Complexipy."""

    def __init__(self) -> None:
        """Initialize the Complexipy runner."""
        self._available: bool | None = None
        self._command: list[str] | None = None

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics supported by Complexipy."""
        return [MetricType.COGNITIVE_COMPLEXITY.value]

    def is_available(self) -> bool:
        """Check if Complexipy is available."""
        if self._available is None:
            command = self._get_complexipy_command()
            if command is None:
                self._available = False
                return self._available

            try:
                result = subprocess.run(
                    [*command, "--help"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self._available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._available = False
        return self._available

    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a Python file using Complexipy.

        Args:
            file_path: Path to the Python file
            content: Optional file content (not used by Complexipy)

        Returns:
            FileMetrics with cognitive complexity metrics
        """
        if not self.is_available():
            return FileMetrics(
                file_path=file_path,
                language=Language.PYTHON.value,
                metrics=[],
                error="Complexipy is not installed. Install with: pip install complexipy",
            )

        # Run complexipy and get results
        metrics = self._get_cognitive_complexity(file_path)

        return FileMetrics(
            file_path=file_path,
            language=Language.PYTHON.value,
            metrics=metrics,
        )

    def _run_complexipy_command(self, file_path: Path) -> list[dict[str, Any]] | None:
        """Run complexipy command and return JSON output.

        Args:
            file_path: Path to analyze

        Returns:
            Parsed JSON output or None on error
        """
        command = self._get_complexipy_command()
        if command is None:
            return None
        env = os.environ.copy()
        env["COVERAGE_CORE"] = ""  # Disable coverage in subprocess

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                subprocess.run(
                    [*command, "--output-json", "--quiet", str(file_path.resolve())],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                    cwd=temp_dir,
                )

                # Complexipy writes JSON to a file, not stdout.
                json_file = self._find_output_json_file(Path(temp_dir))
                if not json_file.exists():
                    return None

                with json_file.open(encoding="utf-8") as file_handle:
                    data = json.load(file_handle)

                if isinstance(data, list):
                    return data
                return None

        except (OSError, json.JSONDecodeError, subprocess.SubprocessError):
            return None

    def _find_output_json_file(self, output_dir: Path) -> Path:
        """Resolve the JSON output file produced by complexipy.

        Complexipy 4.x emits ``complexipy.json`` while 5.x emits
        ``complexipy_results_<timestamp>.json``.
        """
        legacy_file = output_dir / "complexipy.json"
        if legacy_file.exists():
            return legacy_file

        result_files = sorted(
            output_dir.glob("complexipy_results_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if result_files:
            return result_files[0]

        return legacy_file

    def _get_complexipy_command(self) -> list[str] | None:
        """Get the command used to invoke complexipy."""
        if self._command is not None:
            return self._command

        executable = self._resolve_complexipy_executable()
        if executable is None:
            return None

        self._command = [str(executable)]
        return self._command

    def _resolve_complexipy_executable(self) -> Path | None:
        """Resolve the complexipy executable path.

        Resolution order:
        1. Sibling executable beside the active Python interpreter.
        2. First executable found on PATH.
        """
        python_path = Path(sys.executable)

        sibling_candidates: list[Path] = []
        if os.name == "nt":
            sibling_candidates.append(python_path.with_name("complexipy.exe"))
        sibling_candidates.append(python_path.with_name("complexipy"))

        for candidate in sibling_candidates:
            if candidate.exists():
                return candidate

        from_path = shutil.which("complexipy")
        if from_path:
            return Path(from_path)

        return None

    def _get_cognitive_complexity(self, file_path: Path) -> list[MetricResult]:
        """Get cognitive complexity metrics for the file.

        Args:
            file_path: Path to analyze

        Returns:
            List of cognitive complexity metrics
        """
        data = self._run_complexipy_command(file_path)

        metrics = []
        if data:
            # Complexipy returns a list of functions with their complexity
            for item in data:
                if isinstance(item, dict) and "complexity" in item:
                    # Extract line number from the function if possible
                    # Note: Complexipy doesn't provide line numbers in JSON
                    metrics.append(
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.COGNITIVE_COMPLEXITY,
                            value=float(item["complexity"]),
                            function_name=item.get("function_name", "unknown"),
                            details={
                                "file_name": item.get("file_name"),
                                "path": item.get("path"),
                            },
                        )
                    )

        # Also add file-level maximum if there are functions
        if metrics:
            max_complexity = max(m.value for m in metrics)
            function_count = len(metrics)  # Count before adding file maximum
            metrics.append(
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.COGNITIVE_COMPLEXITY,
                    value=max_complexity,
                    details={
                        "type": "file_maximum",
                        "function_count": function_count,
                    },
                )
            )

        return metrics
