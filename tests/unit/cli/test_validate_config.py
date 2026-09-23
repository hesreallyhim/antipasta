"""Tests for the config validate command."""

from pathlib import Path
import tempfile

from click.testing import CliRunner

from antipasta.cli.config.config_validate import validate


class TestValidateConfigCommand:
    """Test the config validate subcommand."""

    def test_validate_valid_config(self) -> None:
        """Test validating a valid configuration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "valid.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="

ignore_patterns: []
use_gitignore: true
"""
            )

            result = runner.invoke(validate, [str(config_file)])

            assert result.exit_code == 0
            assert "✅ Configuration file is valid" in result.output
            assert "Languages: 1" in result.output
            assert "python: 1 metrics" in result.output

    def test_validate_preset_config(self) -> None:
        """Test validating a preset-only configuration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "preset.yaml"
            config_file.write_text("preset: compact\nprofile: relaxed\n")

            result = runner.invoke(validate, [str(config_file)])

            assert result.exit_code == 0
            assert "Preset: compact (relaxed)" in result.output
            assert "Languages: 3" in result.output

    def test_validate_invalid_config(self) -> None:
        """Test validating an invalid configuration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "invalid.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: -5  # Invalid: negative value

languages:
  - name: python
    metrics:
      - type: invalid_metric_type
        threshold: 10
"""
            )

            result = runner.invoke(validate, [str(config_file)])

            assert result.exit_code == 1
            assert "❌ Configuration validation failed" in result.output
            assert "Validation errors:" in result.output

    def test_validate_default_file(self) -> None:
        """Validate discovers the current project layer when no path is supplied."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create .antipasta.yaml in the current directory
            config_file = Path(".antipasta.yaml")
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="

ignore_patterns: []
use_gitignore: true
"""
            )

            # Run validate without arguments
            result = runner.invoke(validate)

            assert result.exit_code == 0
            assert "✅ Configuration layers are valid" in result.output
            assert ".antipasta.yaml: loaded" in result.output

    def test_validate_nonexistent_default_file(self) -> None:
        """Missing optional configuration files still leave valid built-in defaults."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Don't create .antipasta.yaml
            result = runner.invoke(validate)

            assert result.exit_code == 0
            assert "Configuration layers are valid" in result.output
            assert "absent (optional)" in result.output

    def test_validate_malformed_yaml(self) -> None:
        """Test validating a malformed YAML file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "malformed.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
    bad_indentation: this will fail
languages:
  - name: python
"""
            )

            result = runner.invoke(validate, [str(config_file)])

            assert result.exit_code == 1
            assert "❌ Error loading configuration" in result.output

    def test_validate_with_multiple_languages(self) -> None:
        """Test validating config with multiple languages."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "multi-lang.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="
  - name: javascript
    extensions:
      - .js
      - .jsx
    metrics:
      - type: cyclomatic_complexity
        threshold: 15
        comparison: "<="

ignore_patterns:
  - "**/test_*.py"
  - "**/*.test.js"
use_gitignore: true
"""
            )

            result = runner.invoke(validate, [str(config_file)])

            assert result.exit_code == 0
            assert "Languages: 2" in result.output
            assert "python: 1 metrics" in result.output
            assert "javascript: 1 metrics" in result.output
            assert "Ignore patterns: 2" in result.output
