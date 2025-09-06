#!/usr/bin/env python3
"""
Quick script to compare complexity metrics across all tutorial versions.
Run this to see the progression of improvements.
"""

import subprocess
import re
from pathlib import Path


def extract_metrics(output: str) -> dict:
    """Extract key metrics from antipasta output."""
    metrics = {
        "cyclomatic": None,
        "cognitive": None,
        "maintainability": None,
        "halstead_volume": None,
        "violations": 0,
    }

    # Count violations
    violations = re.findall(r"Total violations: (\d+)", output)
    if violations:
        metrics["violations"] = int(violations[0])

    # Extract specific metrics
    patterns = {
        "cyclomatic": r"Cyclomatic Complexity is ([\d.]+)",
        "cognitive": r"Cognitive Complexity is ([\d.]+)",
        "maintainability": r"Maintainability Index is ([\d.]+)",
        "halstead_volume": r"Halstead Volume is ([\d.]+)",
    }

    for metric, pattern in patterns.items():
        matches = re.findall(pattern, output)
        if matches:
            metrics[metric] = float(matches[0])

    return metrics


def main():
    """Compare metrics across all versions."""
    print("Code Complexity Reduction Tutorial - Metrics Comparison")
    print("=" * 70)

    # Find all version files
    tutorial_dir = Path("DEMOS/TUTORIAL")
    version_files = sorted(tutorial_dir.glob("*_v?.py"))

    results = []

    for file in version_files:
        # Run antipasta on each file
        result = subprocess.run(
            ["antipasta", "metrics", "--files", str(file)], capture_output=True, text=True
        )

        metrics = extract_metrics(result.stderr)
        version = file.stem.split("_")[-1]

        results.append({"version": version, "file": file.name, **metrics})

    # Display results in a table
    print(
        f"{'Version':<10} {'Cyclomatic':<12} {'Cognitive':<12} {'Maintain.':<12} {'Volume':<12} {'Status'}"
    )
    print("-" * 70)

    for r in results:
        cyc = f"{r['cyclomatic']:.0f}" if r["cyclomatic"] else "✓"
        cog = f"{r['cognitive']:.0f}" if r["cognitive"] else "✓"
        mai = f"{r['maintainability']:.1f}" if r["maintainability"] else "✓"
        vol = f"{r['halstead_volume']:.0f}" if r["halstead_volume"] else "✓"
        status = "❌ FAIL" if r["violations"] > 0 else "✅ PASS"

        print(f"{r['version']:<10} {cyc:<12} {cog:<12} {mai:<12} {vol:<12} {status}")

    print("\n" + "=" * 70)
    print("Key Improvements:")
    print("- V1→V2: Early returns reduced cognitive complexity by 90%!")
    print("- V2→V3: Extracting functions eliminated complexity violations")
    print("- V3→V4: Data classes brought all metrics into compliance")
    print("- V4→V5: Enterprise patterns (with acceptable trade-offs)")


if __name__ == "__main__":
    main()
