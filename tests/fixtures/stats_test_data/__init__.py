"""
Static test data directory for the stats CLI command.

This directory contains a snapshot of the antipasta codebase that was intended
to be used for testing the stats command against real code with varying complexity
metrics. However, it is currently NOT USED in any active tests.

Current status:
- The stats tests use dynamically generated temporary test files via the
  temp_project_dir fixture instead of this static data
- This directory could potentially be removed to reduce codebase complexity
- Alternatively, it could be incorporated into tests for more realistic testing
  scenarios with actual production code patterns

The fixture mimics the real antipasta project structure (antipasta/cli/,
antipasta/core/, etc.) and provides consistent, reproducible test data for
analyzing code metrics like cyclomatic complexity, LOC, and other metrics.
"""