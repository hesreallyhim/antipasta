"""Data bridge between terminal UI and core engine."""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from code_cop.core.aggregator import MetricAggregator
from code_cop.core.config import CodeCopConfig
from code_cop.core.violations import FileReport


class DashboardDataBridge:
    """Bridge between terminal dashboard and metric collection engine."""

    def __init__(self, project_path: str | Path):
        """Initialize the data bridge.

        Args:
            project_path: Root path of the project to analyze
        """
        self.project_path = Path(project_path)
        self.config = self._load_config()
        self.aggregator = MetricAggregator(self.config)
        self._cache: dict[str, Any] = {}
        self._update_callbacks: list[Callable[[], None]] = []

    def _load_config(self) -> CodeCopConfig:
        """Load configuration from project directory."""
        config_paths = [
            self.project_path / ".code_cop.yaml",
            self.project_path / ".code_cop.yml",
            self.project_path / ".code_cop.json",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    if config_path.suffix == ".json":
                        # TODO: Add JSON config support
                        return CodeCopConfig.generate_default()
                    else:
                        return CodeCopConfig.from_yaml(config_path)
                except Exception:
                    pass

        return CodeCopConfig.generate_default()

    def collect_files(self) -> list[Path]:
        """Collect all files to analyze in the project."""
        patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
        files: list[Path] = []

        for pattern in patterns:
            files.extend(self.project_path.glob(pattern))

        # Filter out common directories to ignore
        ignore_dirs = {"node_modules", "venv", "__pycache__", ".git", "dist", "build"}
        files = [f for f in files if not any(part in f.parts for part in ignore_dirs)]

        return sorted(files)

    def analyze_all(self) -> tuple[list[FileReport], dict[str, Any]]:
        """Analyze all files in the project.

        Returns:
            Tuple of (file reports, summary)
        """
        files = self.collect_files()
        if not files:
            return [], {"total_files": 0, "success": True}

        reports = self.aggregator.analyze_files(files)
        summary = self.aggregator.generate_summary(reports)

        # Cache results
        self._cache["reports"] = reports
        self._cache["summary"] = summary
        self._cache["files"] = files

        # Notify callbacks
        self._notify_updates()

        return reports, summary

    def analyze_file(self, file_path: Path) -> Optional[FileReport]:
        """Analyze a single file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            FileReport or None if analysis failed
        """
        try:
            reports = self.aggregator.analyze_files([file_path])
            return reports[0] if reports else None
        except Exception:
            return None

    def get_file_tree(self) -> dict[str, Any]:
        """Get file tree structure with metrics.

        Returns:
            Nested dictionary representing the file tree
        """
        if "reports" not in self._cache:
            self.analyze_all()

        tree: dict[str, Any] = {"type": "directory", "name": ".", "children": {}}

        for report in self._cache.get("reports", []):
            parts = report.file_path.relative_to(self.project_path).parts
            current = tree

            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # File node
                    current["children"][part] = {
                        "type": "file",
                        "name": part,
                        "report": report,
                        "complexity": self._get_max_complexity(report),
                        "violations": len(report.violations),
                    }
                else:
                    # Directory node
                    if part not in current["children"]:
                        current["children"][part] = {
                            "type": "directory",
                            "name": part,
                            "children": {},
                        }
                    current = current["children"][part]

        return tree

    def get_heatmap_data(self) -> list[dict[str, Any]]:
        """Get data for heatmap visualization.

        Returns:
            List of heatmap entries
        """
        if "reports" not in self._cache:
            self.analyze_all()

        # Aggregate by directory
        dir_stats: dict[Path, dict[str, Any]] = {}

        for report in self._cache.get("reports", []):
            dir_path = report.file_path.parent.relative_to(self.project_path)

            if dir_path not in dir_stats:
                dir_stats[dir_path] = {
                    "path": str(dir_path),
                    "files": 0,
                    "total_complexity": 0,
                    "max_complexity": 0,
                    "violations": 0,
                }

            stats = dir_stats[dir_path]
            stats["files"] += 1
            complexity = self._get_max_complexity(report)
            stats["total_complexity"] += complexity
            stats["max_complexity"] = max(stats["max_complexity"], complexity)
            stats["violations"] += len(report.violations)

        # Calculate averages and sort by complexity
        heatmap_data = []
        for stats in dir_stats.values():
            stats["avg_complexity"] = stats["total_complexity"] / stats["files"]
            heatmap_data.append(stats)

        return sorted(heatmap_data, key=lambda x: x["avg_complexity"], reverse=True)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get overall metrics summary."""
        if "summary" not in self._cache:
            self.analyze_all()

        summary = self._cache.get("summary", {})
        reports = self._cache.get("reports", [])

        # Add complexity distribution
        complexity_bins = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for report in reports:
            complexity = self._get_max_complexity(report)
            if complexity <= 5:
                complexity_bins["low"] += 1
            elif complexity <= 10:
                complexity_bins["medium"] += 1
            elif complexity <= 20:
                complexity_bins["high"] += 1
            else:
                complexity_bins["critical"] += 1

        summary["complexity_distribution"] = complexity_bins
        result: dict[str, Any] = summary
        return result

    def _get_max_complexity(self, report: FileReport) -> float:
        """Get maximum complexity from a file report."""
        complexities = []

        # Check if metrics is a list (MetricResult objects) or dict
        if isinstance(report.metrics, list):
            # Handle list of MetricResult objects
            for metric in report.metrics:
                if hasattr(metric, "value") and metric.value is not None:
                    complexities.append(metric.value)
        elif isinstance(report.metrics, dict):
            # Handle dict of metric values
            if (
                "cyclomatic_complexity" in report.metrics
                and report.metrics["cyclomatic_complexity"] is not None
            ):
                complexities.append(report.metrics["cyclomatic_complexity"])
            if (
                "cognitive_complexity" in report.metrics
                and report.metrics["cognitive_complexity"] is not None
            ):
                complexities.append(report.metrics["cognitive_complexity"])

        return max(complexities) if complexities else 0

    def register_update_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for data updates."""
        self._update_callbacks.append(callback)

    def _notify_updates(self) -> None:
        """Notify all registered callbacks of data updates."""
        for callback in self._update_callbacks:
            callback()

    async def watch_for_changes(self) -> None:
        """Watch for file changes and trigger updates."""
        # TODO: Implement file watching with watchdog or similar
        # For now, just periodic refresh
        while True:
            await asyncio.sleep(5)
            self.analyze_all()
