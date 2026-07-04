"""Python metric runner using Radon's in-process API.

Radon is imported as a library, never spawned as a subprocess: the previous
implementation shelled out to ``python -m radon`` four times per file (cc, mi,
hal, raw), which cost four interpreter startups (~250 ms each) per analyzed
file and dominated antipasta's total runtime. ``multi=True`` on the
maintainability index matches the radon CLI default, so values are identical
to the subprocess era.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from antipasta.core.detector import Language
from antipasta.core.metrics import FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner

if TYPE_CHECKING:
    from radon.visitors import Function as RadonFunction

# Halstead metric types and their attribute on radon's HalsteadReport.
_HALSTEAD_FIELDS: tuple[tuple[MetricType, str], ...] = (
    (MetricType.HALSTEAD_VOLUME, "volume"),
    (MetricType.HALSTEAD_DIFFICULTY, "difficulty"),
    (MetricType.HALSTEAD_EFFORT, "effort"),
    (MetricType.HALSTEAD_TIME, "time"),
    (MetricType.HALSTEAD_BUGS, "bugs"),
)

# Raw metric types and their attribute on radon's raw Module report.
_RAW_FIELDS: tuple[tuple[MetricType, str], ...] = (
    (MetricType.LINES_OF_CODE, "loc"),
    (MetricType.LOGICAL_LINES_OF_CODE, "lloc"),
    (MetricType.SOURCE_LINES_OF_CODE, "sloc"),
    (MetricType.COMMENT_LINES, "comments"),
    (MetricType.BLANK_LINES, "blank"),
)


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
        metrics.extend(self._get_cyclomatic_complexity(file_path, content))

        mi_metric = self._get_maintainability_index(file_path, content)
        if mi_metric:
            metrics.append(mi_metric)

        metrics.extend(self._get_halstead_metrics(file_path, content))
        metrics.extend(self._get_raw_metrics(file_path, content))

        return FileMetrics(
            file_path=file_path,
            language=Language.PYTHON.value,
            metrics=metrics,
        )

    def _get_cyclomatic_complexity(self, file_path: Path, content: str) -> list[MetricResult]:
        """Get per-function cyclomatic complexity plus the file average."""
        from radon.complexity import cc_rank, cc_visit
        from radon.visitors import Function

        try:
            blocks = cc_visit(content)
        except Exception:
            # Unparseable source: match the subprocess era (no cc metrics).
            return []

        metrics: list[MetricResult] = []
        for block in blocks:
            # cc_visit returns methods as flattened Function entries alongside
            # a Class summary block; only Function rows are metric rows (the
            # subprocess JSON's type in {"function", "method"} filter).
            if not isinstance(block, Function):
                continue
            metrics.append(self._build_cc_result(file_path, block, cc_rank(block.complexity)))

        if metrics:
            # Order matters: the average and its function_count describe the
            # per-function cyclomatic rows only, so aggregate rows are
            # appended after both are computed.
            weighted_rows = self._weighted_methods_rows(file_path, metrics)
            avg_complexity = sum(m.value for m in metrics) / len(metrics)
            metrics.append(
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                    value=avg_complexity,
                    details={"type": "average", "function_count": len(metrics)},
                )
            )
            metrics.extend(weighted_rows)

        return metrics

    @staticmethod
    def _weighted_methods_rows(
        file_path: Path, cc_rows: list[MetricResult]
    ) -> list[MetricResult]:
        """Weighted Methods per Class: sum of member cyclomatic complexity.

        Derived here because radon's per-method rows already carry the owning
        class name — one aggregation, no second parse (adoption plan, Phase 2).
        """
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in cc_rows:
            class_name = (row.details or {}).get("classname")
            if class_name:
                sums[class_name] = sums.get(class_name, 0.0) + row.value
                counts[class_name] = counts.get(class_name, 0) + 1
        return [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.WEIGHTED_METHODS_PER_CLASS,
                value=total,
                function_name=class_name,
                details={"methods": counts[class_name]},
            )
            for class_name, total in sums.items()
        ]

    @staticmethod
    def _build_cc_result(file_path: Path, block: RadonFunction, rank: str) -> MetricResult:
        """Build one per-function cyclomatic complexity row."""
        return MetricResult(
            file_path=file_path,
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=float(block.complexity),
            line_number=block.lineno,
            function_name=block.name,
            details={
                "type": "method" if block.is_method else "function",
                "classname": block.classname,
                "rank": rank,
            },
        )

    def _get_maintainability_index(self, file_path: Path, content: str) -> MetricResult | None:
        """Get the maintainability index (multi=True matches the radon CLI)."""
        from radon.metrics import mi_rank, mi_visit

        try:
            value = float(mi_visit(content, multi=True))
        except Exception:
            return None

        return MetricResult(
            file_path=file_path,
            metric_type=MetricType.MAINTAINABILITY_INDEX,
            value=value,
            details={"rank": mi_rank(value)},
        )

    def _get_halstead_metrics(self, file_path: Path, content: str) -> list[MetricResult]:
        """Get Halstead metrics (file-level totals plus per-function rows)."""
        from radon.metrics import h_visit

        try:
            report = h_visit(content)
        except Exception:
            return []

        # File-level totals: unchanged, these are what thresholds check.
        metrics = self._build_halstead_results(file_path, report.total)
        # Per-function rows: informational (feed `antipasta report`).
        for name, function_report in report.functions:
            metrics.extend(
                self._build_halstead_results(file_path, function_report, function_name=name)
            )

        return metrics

    @staticmethod
    def _build_halstead_results(
        file_path: Path,
        hal_report: Any,
        function_name: str | None = None,
    ) -> list[MetricResult]:
        """Build the five Halstead metric results from one HalsteadReport."""
        return [
            MetricResult(
                file_path=file_path,
                metric_type=metric_type,
                value=float(getattr(hal_report, attribute, 0)),
                function_name=function_name,
                details={"type": "function"} if function_name is not None else None,
            )
            for metric_type, attribute in _HALSTEAD_FIELDS
        ]

    def _get_raw_metrics(self, file_path: Path, content: str) -> list[MetricResult]:
        """Get raw metrics (LOC, SLOC, etc.)."""
        from radon.raw import analyze

        try:
            report = analyze(content)
        except Exception:
            return []

        return [
            MetricResult(
                file_path=file_path,
                metric_type=metric_type,
                value=float(getattr(report, attribute, 0)),
            )
            for metric_type, attribute in _RAW_FIELDS
        ]
