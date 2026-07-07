"""JavaScript/TypeScript metric runner using lizard (in-process)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antipasta.core.detector import EXTENSION_MAP, Language
from antipasta.core.metrics import FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner


class LizardRunner(BaseRunner):
    """Runner for JavaScript/TypeScript metrics using lizard.

    lizard parses JS/TS/JSX/TSX in-process (no subprocess), producing
    per-function cyclomatic complexity and NLOC.  Metrics it cannot compute
    (cognitive complexity, Halstead, maintainability index) are simply not
    emitted; every row carries ``details["analyzer"] = "lizard"`` so
    cross-language complexity numbers stay honestly labeled.
    """

    def __init__(self) -> None:
        """Initialize the lizard runner."""
        self._available: bool | None = None

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics supported by lizard."""
        return [
            MetricType.CYCLOMATIC_COMPLEXITY.value,
            MetricType.SOURCE_LINES_OF_CODE.value,
            MetricType.LINES_OF_CODE.value,
        ]

    def is_available(self) -> bool:
        """Check if lizard is available."""
        if self._available is None:
            try:
                import lizard  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a JavaScript/TypeScript file using lizard.

        Args:
            file_path: Path to the file
            content: Optional file content (if already loaded)

        Returns:
            FileMetrics with cyclomatic complexity and line-count metrics
        """
        language = self._detect_language(file_path)

        if not self.is_available():
            return FileMetrics(
                file_path=file_path,
                language=language,
                metrics=[],
                error="lizard is not installed. Install with: pip install lizard",
            )

        if content is None:
            try:
                content = file_path.read_text()
            except Exception as e:
                return FileMetrics(
                    file_path=file_path,
                    language=language,
                    metrics=[],
                    error=f"Failed to read file: {e}",
                )

        import lizard

        try:
            analysis = lizard.analyze_file.analyze_source_code(str(file_path), content)
        except Exception as e:  # lizard can choke on unusual syntax
            return FileMetrics(
                file_path=file_path,
                language=language,
                metrics=[],
                error=f"lizard failed to analyze file: {e}",
            )

        metrics = self._build_function_metrics(file_path, analysis)
        metrics.extend(self._build_file_metrics(file_path, analysis, content))

        return FileMetrics(
            file_path=file_path,
            language=language,
            metrics=metrics,
        )

    @staticmethod
    def _detect_language(file_path: Path) -> str:
        """Detect the language string from the file extension."""
        language = EXTENSION_MAP.get(file_path.suffix.lower(), Language.UNKNOWN)
        return language.value

    def _build_function_metrics(self, file_path: Path, analysis: Any) -> list[MetricResult]:
        """Build per-function cyclomatic complexity rows plus the file average."""
        metrics = [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                value=float(function.cyclomatic_complexity),
                line_number=int(function.start_line),
                function_name=str(function.name),
                details={
                    "type": "function",
                    "analyzer": "lizard",
                    "nloc": int(function.nloc),
                    "end_line": int(function.end_line),
                },
            )
            for function in analysis.function_list
        ]

        # File-level average row, mirroring the radon runner's convention.
        if metrics:
            average = sum(m.value for m in metrics) / len(metrics)
            metrics.append(
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                    value=average,
                    details={
                        "type": "average",
                        "analyzer": "lizard",
                        "function_count": len(metrics),
                    },
                )
            )

        return metrics

    @staticmethod
    def _build_file_metrics(file_path: Path, analysis: Any, content: str) -> list[MetricResult]:
        """Build file-level line-count rows (SLOC from lizard's NLOC, raw LOC)."""
        return [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.SOURCE_LINES_OF_CODE,
                value=float(analysis.nloc),
                details={"analyzer": "lizard"},
            ),
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.LINES_OF_CODE,
                value=float(len(content.splitlines())),
                details={"analyzer": "lizard"},
            ),
        ]
