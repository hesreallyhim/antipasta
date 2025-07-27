#!/bin/bash
# Examples of using the code-cop stats command

echo "=== Basic Statistics for Python Files ==="
code-cop stats --pattern "**/*.py"

echo -e "\n=== Statistics by Directory ==="
code-cop stats --pattern "**/*.py" --by-directory

echo -e "\n=== Statistics by Module (Python packages) ==="
code-cop stats --pattern "**/*.py" --by-module

echo -e "\n=== Include Complexity Metrics ==="
code-cop stats --pattern "**/*.py" \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity \
    --metric maintainability_index

echo -e "\n=== Statistics for Specific Directories ==="
code-cop stats --pattern "src/**/*.py" --pattern "tests/**/*.py" --by-directory

echo -e "\n=== Export as CSV ==="
code-cop stats --pattern "**/*.py" --by-directory --format csv > code_metrics.csv
echo "Saved to code_metrics.csv"

echo -e "\n=== Export as JSON ==="
code-cop stats --pattern "**/*.py" --format json > code_metrics.json
echo "Saved to code_metrics.json"

echo -e "\n=== Find Large Files ==="
echo "Files with more than 200 LOC:"
code-cop stats --pattern "**/*.py" --format json | \
    python -c "
import json, sys
data = json.load(sys.stdin)
files = []
# This would need actual file-level data, showing concept
print('Run with --by-file flag (when implemented) to see individual files')
"

echo -e "\n=== Compare Frontend vs Backend ==="
echo "Frontend (JS/TS):"
code-cop stats --pattern "**/*.js" --pattern "**/*.ts" --pattern "**/*.jsx" --pattern "**/*.tsx"

echo -e "\nBackend (Python):"
code-cop stats --pattern "**/*.py"