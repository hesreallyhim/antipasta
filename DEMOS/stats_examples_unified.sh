#!/bin/bash
# Examples of the unified stats command - efficient single analysis

echo "=== UNIFIED STATS COMMAND ==="
echo "The stats command now analyzes files only once!"
echo

echo "=== Basic Statistics (displayed to terminal) ==="
antipasta stats --pattern "**/*.py"

echo -e "\n=== Save to file ==="
antipasta stats --pattern "**/*.py" --output stats.txt
echo "Saved to stats.txt"

echo -e "\n=== Export as JSON ==="
antipasta stats --pattern "**/*.py" --format json --output stats.json
echo "Saved to stats.json"

echo -e "\n=== Export as CSV ==="
antipasta stats --pattern "**/*.py" --format csv --output stats.csv
echo "Saved to stats.csv"

echo -e "\n=== Statistics by Directory ==="
antipasta stats --pattern "**/*.py" --by-directory

echo -e "\n=== Statistics by Module ==="
antipasta stats --pattern "**/*.py" --by-module

echo -e "\n=== Generate ALL reports at once (9 files from 1 analysis!) ==="
antipasta stats --pattern "**/*.py" --format all --output ./all_reports/
echo
ls -la ./all_reports/

echo -e "\n=== Include additional metrics ==="
antipasta stats --pattern "**/*.py" \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity \
    --metric maintainability_index

echo -e "\n=== Key Features ==="
echo "✓ Single analysis for any output format"
echo "✓ Save to file with --output"
echo "✓ Generate all 9 report combinations with --format all"
echo "✓ Efficient performance - no redundant analysis!"
