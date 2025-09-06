# Code Statistics Feature

The `antipasta stats` command provides comprehensive statistical analysis of your codebase metrics.

## Overview

Collect and analyze metrics across files, directories, and modules to understand code distribution and complexity patterns.

## Basic Usage

```bash
# Get overall statistics for Python files
antipasta stats --pattern "**/*.py"

# Statistics for multiple file types
antipasta stats --pattern "**/*.py" --pattern "**/*.js" --pattern "**/*.ts"

# Statistics from specific directory
antipasta stats --pattern "src/**/*.py" --directory /path/to/project
```

## Grouping Options

### By Directory
```bash
antipasta stats --pattern "**/*.py" --by-directory
```

Shows metrics grouped by directory, useful for:
- Identifying which directories have the most code
- Finding complexity hotspots
- Comparing different parts of your codebase

### By Module (Python)
```bash
antipasta stats --pattern "**/*.py" --by-module
```

Groups by Python packages (directories with `__init__.py`), useful for:
- Understanding module-level complexity
- Comparing package sizes
- Architecture analysis

## Including Additional Metrics

```bash
antipasta stats --pattern "**/*.py" \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity \
    --metric maintainability_index \
    --metric halstead_volume
```

Available metrics:
- `cyclomatic_complexity` - Control flow complexity
- `cognitive_complexity` - How hard code is to understand
- `maintainability_index` - Overall maintainability score
- `halstead_volume` - Size/complexity based on operators/operands
- `halstead_difficulty` - How hard to write/understand
- `halstead_effort` - Mental effort required

## Output Formats

### Table (Default)
Human-readable table format:
```bash
antipasta stats --pattern "**/*.py"
```

### JSON
Machine-readable format for further processing:
```bash
antipasta stats --pattern "**/*.py" --format json
```

### CSV
For spreadsheet analysis:
```bash
antipasta stats --pattern "**/*.py" --by-directory --format csv
```

### Saving to Files
Save any format to a file instead of stdout:
```bash
antipasta stats --pattern "**/*.py" --output report.txt
antipasta stats --pattern "**/*.py" --format json --output metrics.json
antipasta stats --pattern "**/*.py" --format csv --output metrics.csv
```

### Generate All Formats (New!)
Analyze once and generate all 9 report combinations:
```bash
antipasta stats --pattern "**/*.py" --format all --output ./reports/
```

This creates:
- `stats_overall.json`, `stats_overall.csv`, `stats_overall.txt`
- `stats_by_directory.json`, `stats_by_directory.csv`, `stats_by_directory.txt`
- `stats_by_module.json`, `stats_by_module.csv`, `stats_by_module.txt`

Perfect for comprehensive reporting with a single analysis pass!

## Metrics Explained

### File Statistics
- **Total LOC**: Total lines of code across all files
- **Average LOC per file**: Mean file size
- **Min/Max LOC**: Smallest and largest files
- **Standard deviation**: How much file sizes vary

### Function Statistics
- **Total functions**: Number of functions/methods analyzed
- **Average complexity**: Mean cyclomatic complexity of functions
- **Min/Max complexity**: Range of function complexities
(Note: Function-level LOC is not currently available from analyzers)

### Additional Metrics
When included with `--metric` flag:
- **Count**: Number of measurements
- **Average**: Mean value
- **Min/Max**: Range of values
- **Standard deviation**: Variability

## Use Cases

### 1. Find Large Files
```bash
antipasta stats --pattern "**/*.py" --by-directory | grep -E "[0-9]{3,}\.[0-9]+"
```

### 2. Compare Complexity Across Teams
```bash
# Team A's code
antipasta stats --pattern "team_a/**/*.py" --metric cyclomatic_complexity

# Team B's code  
antipasta stats --pattern "team_b/**/*.py" --metric cyclomatic_complexity
```

### 3. Track Metrics Over Time
```bash
# Save weekly snapshots
antipasta stats --pattern "**/*.py" --format json > metrics_$(date +%Y%m%d).json
```

### 4. Identify Refactoring Targets
```bash
# Find directories with high average complexity
antipasta stats --pattern "**/*.py" --by-directory \
    --metric cyclomatic_complexity \
    --metric cognitive_complexity
```

### 5. Code Review Insights
```bash
# Before PR
git checkout main
antipasta stats --pattern "**/*.py" --format json > before.json

# After PR
git checkout feature-branch
antipasta stats --pattern "**/*.py" --format json > after.json

# Compare (would need a diff tool)
```

## Integration Examples

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Collect Code Metrics
  run: |
    antipasta stats --pattern "**/*.py" --format json > metrics.json
    # Upload or process metrics
```

### Git Hook
```bash
#!/bin/bash
# pre-commit hook
echo "Code metrics for this commit:"
antipasta stats --pattern "**/*.py" --metric cyclomatic_complexity
```

### Dashboard Integration
```python
import subprocess
import json

# Get metrics as JSON
result = subprocess.run(
    ["antipasta", "stats", "--pattern", "**/*.py", "--format", "json"],
    capture_output=True,
    text=True
)

metrics = json.loads(result.stdout)
# Send to monitoring system
```

## Best Practices

1. **Regular Monitoring**: Run stats weekly/monthly to track trends
2. **Set Baselines**: Document current metrics before major refactoring
3. **Compare Similar Code**: Group by module/directory for fair comparison
4. **Multiple Metrics**: Use various metrics for complete picture
5. **Automate Reporting**: Integrate into CI/CD for automatic tracking

## Limitations

- Function-level LOC requires language-specific analysis (not all runners provide this)
- Large codebases may take time to analyze
- Some metrics are only available for supported languages

## Future Enhancements

- Historical trending with built-in storage
- Percentile calculations (e.g., "90% of files have < 200 LOC")
- File-level detailed output
- HTML report generation
- Metric correlations (e.g., LOC vs complexity)