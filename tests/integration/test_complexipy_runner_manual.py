#!/usr/bin/env python3
"""Manual test script for ComplexipyRunner.

This test file provides a simple way to manually test the ComplexipyRunner
implementation with real demo files. It tests:
- Runner availability detection
- Cognitive complexity analysis on demo files
- Output format and metric extraction

Created during Complexipy integration implementation on 2025-01-27.
Useful for debugging runner issues or understanding how Complexipy output is parsed.

To run: python tests/integration/test_complexipy_runner_manual.py
"""

from pathlib import Path

from antipasta.runners.python.complexipy_runner import ComplexipyRunner


def main() -> None:
    runner = ComplexipyRunner()

    # Check if available
    print(f"Complexipy available: {runner.is_available()}")
    print(f"Supported metrics: {runner.supported_metrics}")

    # Test on demo files
    demo_files = [
        "DEMOS/02_password_validator_complex.py",
        "DEMOS/05_metrics_analyzer_cognitive.py",
    ]

    for file_path in demo_files:
        path = Path(file_path)
        if path.exists():
            print(f"\nAnalyzing {file_path}:")
            result = runner.analyze(path)

            if result.error:
                print(f"  Error: {result.error}")
            else:
                for metric in result.metrics:
                    print(
                        f"  {metric.function_name or 'File'}: {metric.value} "
                        f"(type: "
                        f"{metric.details.get('type', 'function') if metric.details else 'function'}"  # noqa: E501
                    )


if __name__ == "__main__":
    main()
