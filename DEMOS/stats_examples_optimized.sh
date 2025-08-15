#!/bin/bash
# Optimized examples showing single analysis with multiple outputs

echo "=== OPTIMIZED: Single Analysis, Multiple Reports ==="
echo "Performing analysis once and generating all report formats..."
echo

# Time the single analysis approach
START_TIME=$(date +%s)

# Run analysis once and generate all reports
code-cop stats-all \
    --pattern "**/*.py" \
    --output-dir ./stats_reports \
    --prefix project \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
echo "✅ Completed in ${DURATION} seconds"
echo
echo "Generated files:"
ls -la ./stats_reports/

echo
echo "=== Sample outputs ==="

echo
echo "Overall statistics (JSON):"
cat ./stats_reports/project_overall.json | head -20

echo
echo "Directory statistics (CSV):"
cat ./stats_reports/project_by_directory.csv | head -10

echo
echo "=== Comparison with original approach ==="
echo "Original approach (multiple analyses):"
echo "  - code-cop stats --pattern '**/*.py'"
echo "  - code-cop stats --pattern '**/*.py' --by-directory"
echo "  - code-cop stats --pattern '**/*.py' --by-module"
echo "  - code-cop stats --pattern '**/*.py' --format json"
echo "  - code-cop stats --pattern '**/*.py' --format csv"
echo "  = 5 separate analyses of the same files"
echo
echo "Optimized approach (single analysis):"
echo "  - code-cop stats-all --pattern '**/*.py'"
echo "  = 1 analysis generating all formats"
echo
echo "🚀 Performance improvement: ~5x faster for complete reporting!"