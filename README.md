# code-cop

A code quality enforcement tool that analyzes code complexity across a number of metrics and helps maintain readable, maintainable code.

## What is code-cop?

code-cop analyzes your source code files and measures various complexity metrics, comparing them against configurable thresholds. If any metrics exceed their thresholds, code-cop reports violations and exits with a non-zero status code, making it suitable for CI/CD pipelines.

Currently, code-cop supports Python code analysis with plans to add JavaScript and TypeScript support.

## Why use code-cop?

Complex code is harder to understand, test, and maintain. By enforcing limits on complexity metrics, you can:

-   Catch overly complex functions before they're merged
-   Maintain consistent code quality standards across your team
-   Identify refactoring opportunities
-   Reduce technical debt over time

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/code-cop.git
cd code-cop

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Requirements

-   Python 3.11 or higher
-   Radon (automatically installed as a dependency)
-   Complexipy (optional, for cognitive complexity metrics)

## Basic Usage

### Analyze Files

```bash
# Analyze specific files
code-cop metrics --files src/main.py src/utils.py

# Analyze all Python files in a directory
code-cop metrics --directory src/

# Use a custom configuration file
code-cop metrics --config my-config.yaml --directory .

# Quiet mode (only show violations)
code-cop metrics --quiet --directory src/
```

### Validate Configuration

```bash
# Check if your configuration file is valid
code-cop validate-config .code_cop.yaml
```

## Configuration

code-cop uses YAML configuration files. By default, it looks for `.code_cop.yaml` in the current directory.

### Example Configuration

```yaml
# .code_cop.yaml

# Use patterns from .gitignore file (default: true)
use_gitignore: true

defaults:
    max_cyclomatic_complexity: 10
    min_maintainability_index: 50
    max_halstead_volume: 1000
    max_halstead_difficulty: 10
    max_halstead_effort: 10000
    max_cognitive_complexity: 15

languages:
    - name: python
      extensions:
          - .py
      metrics:
          - type: cyclomatic_complexity
            threshold: 10
            comparison: "<="
          - type: maintainability_index
            threshold: 50
            comparison: ">="
          - type: halstead_volume
            threshold: 1000
            comparison: "<="
          - type: halstead_difficulty
            threshold: 10
            comparison: "<="
          - type: halstead_effort
            threshold: 10000
            comparison: "<="
          - type: cognitive_complexity
            threshold: 15
            comparison: "<="
            enabled: true # Requires complexipy to be installed

ignore_patterns:
    - "**/test_*.py"
    - "**/*_test.py"
    - "**/tests/**"
    - "**/__pycache__/**"
```

### Configuration Structure

-   **use_gitignore**: Whether to automatically use patterns from `.gitignore` (default: true)
-   **defaults**: Default thresholds used when language-specific configuration is not provided
-   **languages**: Language-specific configurations
    -   **name**: Language identifier (currently only "python" is supported)
    -   **extensions**: File extensions to associate with this language
    -   **metrics**: List of metrics to check
        -   **type**: The metric type (see Metrics section below)
        -   **threshold**: The threshold value
        -   **comparison**: How to compare the metric value with the threshold
        -   **enabled**: Whether to check this metric (default: true)
-   **ignore_patterns**: Additional gitignore-style patterns for files to skip (combined with .gitignore if `use_gitignore` is true)

### Comparison Operators

-   `<=` - Metric value must be less than or equal to threshold
-   `<` - Metric value must be less than threshold
-   `>=` - Metric value must be greater than or equal to threshold
-   `>` - Metric value must be greater than threshold
-   `==` - Metric value must equal threshold
-   `!=` - Metric value must not equal threshold

## Metrics Explained

### Cyclomatic Complexity

Measures the number of linearly independent paths through a function. Higher values indicate more complex control flow.

-   **Good**: 1-10 (simple, easy to test)
-   **Moderate**: 11-20 (more complex, harder to test)
-   **High**: 21+ (very complex, consider refactoring)

Example of high complexity:

```python
def process_data(data, mode, validate, transform):
    if validate:
        if not data:
            return None
        if mode == "strict":
            if not isinstance(data, dict):
                raise ValueError("Invalid data")

    if transform:
        if mode == "simple":
            return data.lower()
        elif mode == "complex":
            if validate:
                return data.upper()
            else:
                return data.title()

    return data
```

### Maintainability Index

A composite metric (0-100) that considers cyclomatic complexity, lines of code, and Halstead volume. Higher values indicate more maintainable code.

-   **Good**: 50-100 (maintainable)
-   **Moderate**: 20-49 (moderately maintainable)
-   **Low**: 0-19 (difficult to maintain)

### Halstead Metrics

Based on the number of operators and operands in code:

-   **Volume**: Program size based on the number of operations
-   **Difficulty**: How hard the code is to understand
-   **Effort**: Mental effort required to understand the code
-   **Time**: Estimated time to implement (in seconds)
-   **Bugs**: Estimated number of bugs (Volume / 3000)

### Cognitive Complexity

Measures how difficult code is to understand, focusing on human comprehension rather than execution paths. Unlike cyclomatic complexity, it penalizes nested structures more heavily.

-   **Good**: 1-15 (easy to understand)
-   **Moderate**: 16-30 (requires careful reading)
-   **High**: 31+ (difficult to understand, consider refactoring)

Key differences from cyclomatic complexity:
-   Heavily penalizes nested control structures
-   Considers break/continue statements in loops
-   Better represents actual cognitive load

**Note**: Requires `complexipy` to be installed (`pip install complexipy`)

### Lines of Code Metrics

-   **LOC**: Total lines of code
-   **SLOC**: Source lines of code (excluding comments and blanks)
-   **LLOC**: Logical lines of code
-   **Comment Lines**: Number of comment lines
-   **Blank Lines**: Number of blank lines

## Exit Codes

-   **0**: All metrics pass their thresholds
-   **1**: Error (invalid configuration, missing files, etc.)
-   **2**: One or more metrics violate their thresholds

This makes code-cop suitable for CI/CD pipelines:

```bash
# In your CI pipeline
code-cop metrics --directory src/ --quiet || exit 1
```

## Example Output

### Standard Output

```
Using configuration: .code_cop.yaml
Analyzing 3 files...

======================================================================
METRICS ANALYSIS SUMMARY
======================================================================
Total files analyzed: 3
Files with violations: 1
Total violations: 2

Violations by type:
  - cyclomatic_complexity: 1
  - maintainability_index: 1

----------------------------------------------------------------------
VIOLATIONS FOUND:
----------------------------------------------------------------------
❌ src/complex.py:15 (process_data): Cyclomatic Complexity is 12.00 (threshold: <= 10.0)
❌ src/complex.py: Maintainability Index is 45.23 (threshold: >= 50.0)

✗ Code quality check FAILED
```

### Quiet Mode Output

```
----------------------------------------------------------------------
VIOLATIONS FOUND:
----------------------------------------------------------------------
❌ src/complex.py:15 (process_data): Cyclomatic Complexity is 12.00 (threshold: <= 10.0)
❌ src/complex.py: Maintainability Index is 45.23 (threshold: >= 50.0)

✗ Code quality check FAILED
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=code_cop --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_config.py -v
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type checking
make type-check
```

### Project Structure

```
code_cop/
├── cli/              # Command-line interface
├── core/             # Core functionality
│   ├── config.py     # Configuration models
│   ├── detector.py   # Language detection
│   ├── metrics.py    # Metric definitions
│   ├── violations.py # Violation tracking
│   └── aggregator.py # Analysis coordination
├── runners/          # Language-specific analyzers
│   └── python/       # Python analysis (Radon)
└── utils/            # Utilities
```

## Current Limitations

1. **Python Only**: Currently only Python is supported. JavaScript and TypeScript support is planned.
2. **Cognitive Complexity**: This metric is defined but not yet implemented (requires complexipy integration).
3. **Function-Level Only**: Some metrics are only available at the function level, not class or module level.

## Future Enhancements

-   JavaScript/TypeScript support via ts-complex
-   Cognitive complexity for Python via complexipy
-   Pre-commit hook integration
-   Git hook support
-   HTML report generation
-   Baseline file support (ignore existing violations)
-   Trend analysis over time

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Add your license here]

## Acknowledgments

-   [Radon](https://github.com/rubik/radon) for Python code metrics
-   Inspired by various code quality tools like ESLint, Pylint, and SonarQube
