"""Python metric runner using Radon."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from antipasta.core.detector import Language
from antipasta.core.metrics import FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner


class RadonRunner(BaseRunner):
    """Runner for Python metrics using Radon."""

    def __init__(self) -> None:
        """Initialize the Radon runner."""
        self._available: bool | None = None

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics supported by Radon."""
        return [
            MetricType.CYCLOMATIC_COMPLEXITY.value,
            MetricType.MAINTAINABILITY_INDEX.value,
            MetricType.HALSTEAD_VOLUME.value,
            MetricType.HALSTEAD_DIFFICULTY.value,
            MetricType.HALSTEAD_EFFORT.value,
            MetricType.HALSTEAD_TIME.value,
            MetricType.HALSTEAD_BUGS.value,
            MetricType.LINES_OF_CODE.value,
            MetricType.LOGICAL_LINES_OF_CODE.value,
            MetricType.SOURCE_LINES_OF_CODE.value,
            MetricType.COMMENT_LINES.value,
            MetricType.BLANK_LINES.value,
        ]

    def is_available(self) -> bool:
        """Check if Radon is available."""
        if self._available is None:
            try:
                # Try to import radon
                import radon  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a Python file using Radon.

        Args:
            file_path: Path to the Python file
            content: Optional file content

        Returns:
            FileMetrics with all calculated metrics
        """
        if not self.is_available():
            return FileMetrics(
                file_path=file_path,
                language=Language.PYTHON.value,
                metrics=[],
                error="Radon is not installed. Install with: pip install radon",
            )

        # Read content if not provided
        if content is None:
            try:
                content = file_path.read_text()
            except Exception as e:
                return FileMetrics(
                    file_path=file_path,
                    language=Language.PYTHON.value,
                    metrics=[],
                    error=f"Failed to read file: {e}",
                )

        metrics: list[MetricResult] = []

        # Get cyclomatic complexity
        cc_metrics = self._get_cyclomatic_complexity(file_path)
        metrics.extend(cc_metrics)

        # Get maintainability index
        mi_metric = self._get_maintainability_index(file_path)
        if mi_metric:
            metrics.append(mi_metric)

        # Get Halstead metrics
        hal_metrics = self._get_halstead_metrics(file_path)
        metrics.extend(hal_metrics)

        # Get raw metrics (LOC, SLOC, etc.)
        raw_metrics = self._get_raw_metrics(file_path)
        metrics.extend(raw_metrics)

        return FileMetrics(
            file_path=file_path,
            language=Language.PYTHON.value,
            metrics=metrics,
        )

    def _run_radon_command(self, command: list[str]) -> dict[str, Any] | None:
        """Run a radon command and return JSON output.

        Args:
            command: Command to run

        Returns:
            Parsed JSON output or None on error
        """
        import os

        env = os.environ.copy()
        env["COVERAGE_CORE"] = ""  # Disable coverage in subprocess

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                env=env,
            )
            data: dict[str, Any] = json.loads(result.stdout)
            return data
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None

    def _get_cyclomatic_complexity(self, file_path: Path) -> list[MetricResult]:
        """Get cyclomatic complexity metrics."""
        command = [sys.executable, "-m", "radon", "cc", "-j", str(file_path)]
        data = self._run_radon_command(command)

        metrics: list[MetricResult] = []
        if data and str(file_path) in data:
            file_data = data[str(file_path)]
            # Handle error response from radon
            if isinstance(file_data, dict) and "error" in file_data:
                return metrics

            for item in file_data:
                # Skip if item is not a dict (error case)
                if not isinstance(item, dict):
                    continue
                if item.get("type") in ("function", "method"):
                    metrics.append(
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                            value=float(item["complexity"]),
                            line_number=item["lineno"],
                            function_name=item["name"],
                            details={
                                "type": item["type"],
                                "classname": item.get("classname"),
                                "rank": item.get("rank", "A"),
                            },
                        )
                    )

        # Also add file-level average if there are functions
        if metrics:
            avg_complexity = sum(m.value for m in metrics) / len(metrics)
            metrics.append(
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                    value=avg_complexity,
                    details={"type": "average", "function_count": len(metrics) - 1},
                )
            )

        return metrics

    def _get_maintainability_index(self, file_path: Path) -> MetricResult | None:
        """Get maintainability index metric."""
        command = [sys.executable, "-m", "radon", "mi", "-j", str(file_path)]
        data = self._run_radon_command(command)

        if data and str(file_path) in data:
            mi_data = data[str(file_path)]
            # Check if this is an error response
            if isinstance(mi_data, dict) and "mi" in mi_data:
                return MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.MAINTAINABILITY_INDEX,
                    value=float(mi_data["mi"]),
                    details={"rank": mi_data.get("rank", "A")},
                )
        return None

    def _get_halstead_metrics(self, file_path: Path) -> list[MetricResult]:
        """Get Halstead metrics."""
        command = [sys.executable, "-m", "radon", "hal", "-j", str(file_path)]
        data = self._run_radon_command(command)

        metrics: list[MetricResult] = []
        if data and str(file_path) in data:
            file_data = data[str(file_path)]
            # Check if this is an error response or has expected structure
            if isinstance(file_data, dict) and "total" in file_data:
                hal_data = file_data["total"]
                metrics.extend(
                    [
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.HALSTEAD_VOLUME,
                            value=float(hal_data.get("volume", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.HALSTEAD_DIFFICULTY,
                            value=float(hal_data.get("difficulty", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.HALSTEAD_EFFORT,
                            value=float(hal_data.get("effort", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.HALSTEAD_TIME,
                            value=float(hal_data.get("time", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.HALSTEAD_BUGS,
                            value=float(hal_data.get("bugs", 0)),
                        ),
                    ]
                )

        return metrics

    def _get_raw_metrics(self, file_path: Path) -> list[MetricResult]:
        """Get raw metrics (LOC, SLOC, etc.)."""
        command = [sys.executable, "-m", "radon", "raw", "-j", str(file_path)]
        data = self._run_radon_command(command)

        metrics: list[MetricResult] = []
        if data and str(file_path) in data:
            raw_data = data[str(file_path)]
            # Check if this is a valid response with expected fields
            if isinstance(raw_data, dict) and "loc" in raw_data:
                metrics.extend(
                    [
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.LINES_OF_CODE,
                            value=float(raw_data.get("loc", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.LOGICAL_LINES_OF_CODE,
                            value=float(raw_data.get("lloc", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.SOURCE_LINES_OF_CODE,
                            value=float(raw_data.get("sloc", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.COMMENT_LINES,
                            value=float(raw_data.get("comments", 0)),
                        ),
                        MetricResult(
                            file_path=file_path,
                            metric_type=MetricType.BLANK_LINES,
                            value=float(raw_data.get("blank", 0)),
                        ),
                    ]
                )

        return metrics
