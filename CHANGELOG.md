# Changelog

All notable changes to antipasta will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-01-27

### Added
- **CLI Threshold Override Features**
  - Dynamic threshold overrides via command-line arguments
  - Three-letter prefix support for metric names (e.g., "cyc" for cyclomatic_complexity)
  - Validation for CLI override values and operators
  - Enhanced configuration override system (`config_override.py`)

- **Comprehensive Test Coverage**
  - Tests for refactored stats modules
  - Config override validation tests
  - Metrics utility tests
  - Test coverage for all new submodules

### Changed
- **Major Codebase Refactoring** - antipasta now meets its own complexity constraints
  - **Modularization of Large Files**
    - `cli/stats.py` (906 lines) → organized submodules under `cli/stats/`:
      - `aggregation/` - Directory and module aggregation logic
      - `collection/` - Metrics collection and analysis
      - `output/` - Display formatting and output handling
      - `utils.py` - Shared utilities
      - `command.py` - Main command orchestration
    - `cli/config_generate.py` (421 lines) → `cli/config/config_generate/` submodules:
      - `main.py` - Command entry point
      - `interactive_prompts.py` - User interaction logic
      - `language_config.py` - Language-specific configuration
      - `project_config.py` - Project configuration handling
      - `file_operations.py` - File I/O operations
      - `validation.py` - Config validation logic
    - `cli/config_view.py` (242 lines) → `cli/config/config_view/` submodules:
      - `main.py` - Command entry point
      - `display_formats.py` - Format handling (JSON, YAML)
      - `table_display.py` - Table formatting logic
    - `cli/metrics.py` (210 lines) → `cli/metrics/` submodules:
      - `metrics.py` - Main command logic
      - `metrics_utils_*.py` - Specialized utility modules

  - **Complexity Reduction Techniques**
    - Applied Compose Method pattern throughout to reduce cyclomatic complexity
    - Extracted complex conditionals into named functions
    - Replaced nested structures with dictionary dispatch patterns
    - Improved maintainability indices across all modules (target: 50+)
    - Reduced maximum function complexity to meet thresholds

  - **Architecture Improvements**
    - Better separation of concerns throughout the codebase
    - Enhanced modularity and reusability
    - Clear module boundaries and responsibilities
    - Consistent patterns across similar modules

### Fixed
- Type hint issues throughout the codebase
- Test failures after refactoring
- Import path issues after module reorganization

### Technical Improvements
- **Code Quality Metrics**
  - All source code now passes antipasta's own complexity checks
  - Largest files reduced from 900+ lines to under 310 lines
  - Cyclomatic complexity kept within configured thresholds
  - Maintainability index improved across all modules

- **Developer Experience**
  - More intuitive module organization
  - Enhanced code readability and maintainability
  - Better testability through modular design
  - Clearer separation between business logic and presentation

## [1.0.0] - 2025-01-21

### Added
- **Core CLI Commands**
  - `antipasta config generate` - Interactive configuration file generation
  - `antipasta config validate` - Configuration file validation
  - `antipasta config view` - Display configuration in multiple formats (table, JSON, YAML)
  - `antipasta metrics` - Analyze code metrics for specified files
  - `antipasta stats` - Collect and display code metrics statistics with multiple grouping options

- **Metric Analysis**
  - Cyclomatic Complexity analysis via Radon
  - Cognitive Complexity analysis via Complexipy
  - Maintainability Index calculation
  - Halstead metrics (volume, difficulty, effort, time, bugs)
  - Lines of Code metrics (LOC, SLOC, LLOC, comments, blank lines)

- **Configuration System**
  - YAML-based configuration (`.antipasta.yaml`)
  - Language-specific metric thresholds
  - Customizable comparison operators
  - `.gitignore` integration for file filtering
  - Ignore patterns support

- **Statistics Features**
  - Overall statistics across all files
  - Directory-based grouping with depth control
  - Module-based grouping for Python packages
  - Multiple output formats (table, JSON, CSV)
  - Path display styles (relative, parent, full)
  - Metric filtering with prefix shortcuts

- **Developer Experience**
  - Comprehensive test suite (161+ tests)
  - Type hints throughout (Python 3.11+)
  - Modern Python packaging with Hatchling
  - Detailed error messages and helpful warnings
  - Backward compatibility aliases for legacy commands

- **Documentation**
  - Comprehensive README with examples
  - Interactive tutorials in DEMOS/TUTORIAL/
  - Detailed release guide (RELEASE.md)
  - Configuration examples and best practices

### Technical Details
- Built with Click for CLI interface
- Pydantic for configuration validation
- Radon and Complexipy for metric analysis
- Pathspec for gitignore-style pattern matching
- 83% test coverage with pytest

### Notes
- Terminal UI (TUI) feature deferred to post-1.0.0 release
- Initial release focuses on CLI-first experience
- Currently supports Python code analysis (JS/TS support planned)

---

For upgrade instructions and more details, see the [README](README.md).