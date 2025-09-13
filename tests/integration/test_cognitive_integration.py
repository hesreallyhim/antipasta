#!/usr/bin/env python3
"""Integration test for cognitive complexity feature.

This test file verifies the complete integration of cognitive complexity
metrics including:
- Runner availability and initialization
- Metric collection from Complexipy
- Violation detection with configured thresholds
- Integration with the aggregator

Created during Complexipy integration debugging on 2025-01-27.
Useful for verifying the full cognitive complexity pipeline works end-to-end.
"""

from pathlib import Path

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.detector import Language


def main() -> None:
    # Load config
    config_path = Path(".antipasta.yaml")
    if config_path.exists():
        config = AntipastaConfig.from_yaml(config_path)
    else:
        config = AntipastaConfig.generate_default()
    print(f"Config defaults: max_cognitive_complexity = {config.defaults.max_cognitive_complexity}")

    # Create aggregator
    aggregator = MetricAggregator(config)

    # Check runners
    print(f"\nRunners for Python: {aggregator.runners}")
    for runner in aggregator.runners.get(Language.PYTHON, []):
        print(f"  - {runner.__class__.__name__}: available={runner.is_available()}")

    # Analyze a file
    test_file = Path("DEMOS/05_metrics_analyzer_cognitive.py")
    reports = aggregator.analyze_files([test_file])

    print(f"\nReport for {test_file}:")
    if reports:
        report = reports[0]
        print(f"  Total metrics: {len(report.metrics)}")

        # Show cognitive complexity metrics
        cog_metrics = [m for m in report.metrics if m.metric_type.value == "cognitive_complexity"]
        print(f"  Cognitive complexity metrics: {len(cog_metrics)}")
        for m in cog_metrics:
            print(f"    - {m.function_name or 'File'}: {m.value}")

        # Show violations
        print(f"\n  All violations: {len(report.violations)}")
        for v in report.violations:
            print(f"    - {v.metric_type.value}: {v.message}")

        cog_violations = [
            v for v in report.violations if v.metric_type.value == "cognitive_complexity"
        ]
        print(f"\n  Cognitive complexity violations: {len(cog_violations)}")
        for v in cog_violations:
            print(f"    - {v}")

        # Debug: Check if cognitive complexity is in the metric configs
        print("\n  Checking metric configs...")
        lang_config = config.get_language_config("python")
        if lang_config:
            cog_config = [m for m in lang_config.metrics if m.type.value == "cognitive_complexity"]
            print(f"    Language config has cognitive complexity: {len(cog_config) > 0}")
        else:
            print("    No language config - using defaults")


if __name__ == "__main__":
    main()
