#!/bin/bash
# Examples of using the antipasta stats command

echo "=== Basic Statistics for Python Files ==="
antipasta stats --pattern "**/*.py"

echo -e "\n=== Statistics by Directory ==="
antipasta stats --pattern "**/*.py" --by-directory

echo -e "\n=== Statistics by Module (Python packages) ==="
antipasta stats --pattern "**/*.py" --by-module

echo -e "\n=== Include Complexity Metrics ==="
antipasta stats --pattern "**/*.py" \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity \
    --metric maintainability_index

echo -e "\n=== Statistics for Specific Directories ==="
antipasta stats --pattern "src/**/*.py" --pattern "tests/**/*.py" --by-directory

echo -e "\n=== Export as CSV ==="
antipasta stats --pattern "**/*.py" --by-directory --format csv > code_metrics.csv
echo "Saved to code_metrics.csv"

echo -e "\n=== Export as JSON ==="
antipasta stats --pattern "**/*.py" --format json > code_metrics.json
echo "Saved to code_metrics.json"

echo -e "\n=== Find Large Files ==="
echo "Files with more than 200 LOC:"
antipasta stats --pattern "**/*.py" --format json | \
    python -c "
import json, sys
data = json.load(sys.stdin)
files = []
# This would need actual file-level data, showing concept
print('Run with --by-file flag (when implemented) to see individual files')
"

echo -e "\n=== Compare Frontend vs Backend ==="
echo "Frontend (JS/TS):"
antipasta stats --pattern "**/*.js" --pattern "**/*.ts" --pattern "**/*.jsx" --pattern "**/*.tsx"

echo -e "\nBackend (Python):"
antipasta stats --pattern "**/*.py"
