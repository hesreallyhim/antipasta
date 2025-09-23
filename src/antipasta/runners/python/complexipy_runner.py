"""Python cognitive complexity runner using Complexipy."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from antipasta.core.detector import Language
from antipasta.core.metrics import FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner


class ComplexipyRunner(BaseRunner):
    """Runner for Python cognitive complexity using Complexipy."""

    def __init__(self) -> None:
        """Initialize the Complexipy runner."""
        self._available: bool | None = None

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics supported by Complexipy."""
        return [MetricType.COGNITIVE_COMPLEXITY.value]

    def is_available(self) -> bool:
        """Check if Complexipy is available."""
        if self._available is None:
            try:
                # Try to run complexipy command
                result = subprocess.run(
                    ["complexipy", "--help"],
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
        import os

        env = os.environ.copy()
        env["COVERAGE_CORE"] = ""  # Disable coverage in subprocess

        try:
            # Run complexipy with JSON output
            result = subprocess.run(
                ["complexipy", "--output-json", "--quiet", str(file_path)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            if result.returncode != 0:
                # Complexipy returns non-zero for files with high complexity
                # but still outputs valid JSON,
                # so we don't treat this as an error
                pass

            # Complexipy writes JSON to a file, not stdout
            # Look for the output file
            json_file = Path("complexipy.json")
            if json_file.exists():
                try:
                    with open(json_file) as f:
                        data: list[dict[str, Any]] = json.load(f)
                    # Clean up the output file
                    json_file.unlink()
                    return data
                except (OSError, json.JSONDecodeError):
                    return None

            return None

        except (subprocess.SubprocessError, FileNotFoundError):
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
