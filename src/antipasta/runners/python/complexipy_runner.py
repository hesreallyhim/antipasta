"""Python cognitive complexity runner using Complexipy's in-process API.

Complexipy is imported as a library, never spawned as a subprocess: the
previous implementation ran the ``complexipy`` executable once per file (with
a temp dir and a JSON file round-trip), costing ~300 ms of process startup per
analyzed file. The in-process API also provides function line numbers, which
the CLI's JSON output did not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antipasta.core.model.detector import Language
from antipasta.core.model.metrics import FileMetrics, MetricResult, MetricType
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
                import complexipy  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a Python file using Complexipy.

        Args:
            file_path: Path to the Python file
            content: Optional file content (analyzed directly when provided)

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

        return FileMetrics(
            file_path=file_path,
            language=Language.PYTHON.value,
            metrics=self._get_cognitive_complexity(file_path, content),
        )

    def _get_cognitive_complexity(self, file_path: Path, content: str | None) -> list[MetricResult]:
        """Get per-function cognitive complexity plus the file maximum.

        Args:
            file_path: Path to analyze
            content: Optional pre-loaded source (avoids a second disk read)

        Returns:
            List of cognitive complexity metrics
        """
        from complexipy import code_complexity, file_complexity

        # CodeComplexity and FileComplexity are distinct types sharing the
        # `.functions` shape.
        result: Any
        try:
            if content is not None:
                result = code_complexity(content)
            else:
                result = file_complexity(str(file_path.resolve()))
        except Exception:
            # Unparseable source: match the subprocess era (no metrics).
            return []

        # No path-derived data in details: metric rows must stay
        # path-independent so content-addressed cache entries rehydrate
        # correctly for identical files at different paths (the row's own
        # file_path field carries the location).
        metrics = [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.COGNITIVE_COMPLEXITY,
                value=float(function.complexity),
                line_number=function.line_start,
                function_name=function.name,
            )
            for function in result.functions
        ]

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
