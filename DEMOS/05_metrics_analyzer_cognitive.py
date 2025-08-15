"""Demo 5: Metrics Analyzer - High Cognitive Complexity

Metrics:
- Cyclomatic Complexity: 6-10 (varies by function)
- Cognitive Complexity: 10-15 (high due to nesting)
- Maintainability Index: ~55
- Halstead Volume: High

This demonstrates the difference between cyclomatic and cognitive complexity.
While cyclomatic complexity might be moderate, the cognitive complexity is
high due to nested conditions and mixed abstraction levels.
"""

import statistics
from dataclasses import dataclass
from typing import Any


@dataclass
class Metric:
    name: str
    value: float
    threshold: float
    severity: str = "info"


class MetricsAnalyzer:
    """Analyze code metrics with complex nested logic."""

    def analyze_project_metrics(
        self,
        files: list[dict[str, str | dict[str, float]]],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze metrics for entire project with nested analysis logic."""
        results: dict[str, Any] = {
            "summary": {},
            "files": [],
            "violations": [],
            "statistics": {},
        }

        all_complexities = []
        all_volumes = []
        all_maintainability = []

        for file_data in files:
            if isinstance(file_data, dict) and "path" in file_data:
                file_path = file_data["path"]

                if "metrics" in file_data and isinstance(
                    file_data["metrics"], dict
                ):
                    file_result: dict[str, Any] = {
                        "path": file_path,
                        "issues": [],
                    }

                    # Nested complexity analysis
                    if "complexity" in file_data["metrics"]:
                        complexity = file_data["metrics"]["complexity"]
                        all_complexities.append(complexity)

                        if config.get("complexity_thresholds"):
                            thresholds = config["complexity_thresholds"]

                            if complexity > thresholds.get("error", 15):
                                file_result["issues"].append(
                                    {
                                        "type": "complexity",
                                        "severity": "error",
                                        "value": complexity,
                                        "message": (
                                            f"Complexity {complexity} "
                                            "exceeds error threshold"
                                        ),
                                    }
                                )
                                results["violations"].append(
                                    {
                                        "file": file_path,
                                        "metric": "complexity",
                                        "severity": "error",
                                    }
                                )
                            elif complexity > thresholds.get("warning", 10):
                                file_result["issues"].append(
                                    {
                                        "type": "complexity",
                                        "severity": "warning",
                                        "value": complexity,
                                        "message": (
                                            f"Complexity {complexity} "
                                            "exceeds warning threshold"
                                        ),
                                    }
                                )

                                # Additional nested check for hotspots
                                if (
                                    "hotspots" in config
                                    and config["hotspots"].get("enabled")
                                    and complexity
                                    > thresholds.get("warning", 10) * 1.5
                                ):
                                    file_result["is_hotspot"] = True
                            else:
                                # Check trend if history available
                                if "history" in file_data:
                                    history = file_data["history"]
                                    if (
                                        isinstance(history, list)
                                        and len(history) > 0
                                    ):
                                        previous = history[-1].get(
                                            "complexity", 0
                                        )
                                        if (
                                            complexity > previous * 1.2
                                        ):  # 20% increase
                                            file_result["issues"].append(
                                                {
                                                    "type": "trend",
                                                    "severity": "info",
                                                    "message": (
                                                        "Complexity "
                                                        "increased by >20%"
                                                    ),
                                                }
                                            )

                    # Volume analysis with nested conditions
                    if "halstead_volume" in file_data["metrics"]:
                        volume = file_data["metrics"]["halstead_volume"]
                        all_volumes.append(volume)

                        # Complex nested logic for volume analysis
                        if volume > 1000 and "functions" in file_data:
                            func_count = len(file_data["functions"])
                            avg_volume = (
                                volume / func_count
                                if func_count > 0
                                else volume
                            )

                            if avg_volume > 500:
                                file_result["issues"].append(
                                    {
                                        "type": "volume",
                                        "severity": "warning",
                                        "message": (
                                            "High average function volume"
                                        ),
                                    }
                                )
                            elif avg_volume > 300 and complexity > 10:
                                file_result["issues"].append(
                                    {
                                        "type": "combined",
                                        "severity": "info",
                                        "message": (
                                            "Moderate volume "
                                            "with high complexity"
                                        ),
                                    }
                                )

                        # Special handling for test files
                        if (
                            isinstance(file_path, str)
                            and (
                                "test" in file_path.lower()
                                or "spec" in file_path.lower()
                            )
                            and volume > 2000
                        ):
                            file_result["issues"].append(
                                {
                                    "type": "test_volume",
                                    "severity": "info",
                                    "message": (
                                        "Consider splitting large test file"
                                    ),
                                }
                            )

                    # Maintainability index with multiple decision points
                    if "maintainability_index" in file_data["metrics"]:
                        mi = file_data["metrics"]["maintainability_index"]
                        all_maintainability.append(mi)

                        # Complex categorization logic
                        if mi < 10:
                            category = "unmaintainable"
                            severity = "error"
                        elif mi < 20:
                            category = "very_poor"
                            severity = "error"

                            # Additional check for critical files
                            if self._is_critical_file(file_path, config):
                                results["violations"].append(
                                    {
                                        "file": file_path,
                                        "metric": "maintainability",
                                        "severity": "critical",
                                        "note": "Critical file with poor maintainability",
                                    }
                                )
                        elif mi < 50:
                            category = "poor"
                            severity = "warning"
                        elif mi < 70:
                            category = "moderate"
                            severity = "info"
                        else:
                            category = "good"
                            severity = None

                        if severity:
                            file_result["issues"].append(
                                {
                                    "type": "maintainability",
                                    "severity": severity,
                                    "value": mi,
                                    "category": category,
                                }
                            )

                    results["files"].append(file_result)

        # Calculate statistics with nested aggregations
        if all_complexities:
            results["statistics"]["complexity"] = {
                "mean": statistics.mean(all_complexities),
                "median": statistics.median(all_complexities),
                "stdev": statistics.stdev(all_complexities)
                if len(all_complexities) > 1
                else 0,
                "percentiles": {
                    "75": self._percentile(all_complexities, 0.75),
                    "90": self._percentile(all_complexities, 0.90),
                    "95": self._percentile(all_complexities, 0.95),
                },
            }

            # Nested outlier detection
            if results["statistics"]["complexity"]["stdev"] > 0:
                mean = results["statistics"]["complexity"]["mean"]
                stdev = results["statistics"]["complexity"]["stdev"]
                outliers = []

                for i, c in enumerate(all_complexities):
                    if (
                        c > mean + 2 * stdev
                        and i < len(files)
                        and "path" in files[i]
                    ):
                        outliers.append(files[i]["path"])

                if outliers:
                    results["statistics"]["complexity"]["outliers"] = outliers

        # Generate summary with multiple aggregation levels
        results["summary"] = self._generate_summary(results, config)

        return results

    def _is_critical_file(
        self, file_path: str, config: dict[str, Any]
    ) -> bool:
        """Check if file is marked as critical in config."""
        critical_patterns = config.get("critical_files", [])

        if not critical_patterns:
            # Default critical patterns
            critical_patterns = [
                "main.",
                "app.",
                "server.",
                "database.",
                "auth.",
                "security.",
            ]

        for pattern in critical_patterns:
            if pattern in file_path.lower():
                return True

        return False

    def _percentile(self, data: list[float], p: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int(len(sorted_data) * p)

        if index >= len(sorted_data):
            return sorted_data[-1]

        return sorted_data[index]

    def _generate_summary(
        self, results: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate summary with health score calculation."""
        summary = {
            "total_files": len(results["files"]),
            "files_with_issues": 0,
            "total_issues": 0,
            "health_score": 100.0,
        }

        severity_weights = {"error": 10, "warning": 5, "info": 1}

        # Complex health score calculation
        for file_result in results["files"]:
            if file_result.get("issues"):
                summary["files_with_issues"] += 1

                for issue in file_result["issues"]:
                    summary["total_issues"] += 1

                    # Nested weight adjustments
                    weight = severity_weights.get(issue["severity"], 1)

                    if file_result.get("is_hotspot"):
                        weight *= 1.5

                    if "critical" in file_result.get("path", "").lower():
                        weight *= 2

                    summary["health_score"] -= weight

        # Ensure score doesn't go below 0
        summary["health_score"] = max(0, summary["health_score"])

        # Add risk level based on score
        if summary["health_score"] >= 90:
            summary["risk_level"] = "low"
        elif summary["health_score"] >= 70:
            summary["risk_level"] = "medium"
        elif summary["health_score"] >= 50:
            summary["risk_level"] = "high"
        else:
            summary["risk_level"] = "critical"

        return summary


# Example usage function with additional complexity
def analyze_codebase(
    directory: str,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    output_format: str = "json",
) -> dict[str, Any] | str:
    """Analyze codebase with multiple configuration options."""
    # This would normally scan files and extract metrics
    # Simplified for demo

    analyzer = MetricsAnalyzer()
    config = {
        "complexity_thresholds": {"error": 15, "warning": 10},
        "hotspots": {"enabled": True},
        "critical_files": ["main.py", "core.py"],
    }

    # Mock data for demo
    files = [
        {
            "path": "main.py",
            "metrics": {
                "complexity": 12,
                "halstead_volume": 1500,
                "maintainability_index": 45,
            },
            "functions": ["main", "setup", "run"],
        }
    ]

    results = analyzer.analyze_project_metrics(files, config)

    if output_format == "json":
        return results
    if output_format == "summary":
        return f"Health Score: {results['summary']['health_score']}, Risk: {results['summary']['risk_level']}"
    raise ValueError(f"Unknown output format: {output_format}")
