# Changelog

All notable changes to antipasta will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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