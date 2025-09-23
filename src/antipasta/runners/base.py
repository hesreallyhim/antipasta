"""Abstract base runner for all language-specific metric runners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from antipasta.core.metrics import FileMetrics


class BaseRunner(ABC):
    """Abstract base class for metric runners."""

    @abstractmethod
    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a file and return metrics.

        Args:
            file_path: Path to the file to analyze
            content: Optional file content (if already loaded)

        Returns:
            FileMetrics object containing all calculated metrics
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this runner is available (dependencies installed).

        Returns:
            True if the runner can be used
        """

    @property
    @abstractmethod
    def supported_metrics(self) -> list[str]:
        """List of metric types supported by this runner.

        Returns:
            List of MetricType values as strings
        """
