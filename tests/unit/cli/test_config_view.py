"""Tests for the config view command."""

import json
from pathlib import Path
import tempfile

from click.testing import CliRunner
import yaml

from antipasta.cli.config.config_view import view


class TestConfigViewCommand:
    """Test the config view command."""

    def test_view_valid_config_summary(self) -> None:
        """Test viewing a valid configuration in summary format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10
  min_maintainability_index: 50
  max_cognitive_complexity: 15

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="

ignore_patterns:
  - "**/test_*.py"
  - "**/*_test.py"
use_gitignore: true
"""
            )

            result = runner.invoke(view, ["--path", str(config_file)])

            assert result.exit_code == 0
            assert f"Configuration: {config_file}" in result.output
            assert "Status: ✅ Valid" in result.output
            assert "THRESHOLDS" in result.output
            assert "Cyclomatic Complexity" in result.output
            assert "≤ 10" in result.output
            assert "LANGUAGES" in result.output
            assert "Python (.py)" in result.output
            assert "✓ 1 metrics configured" in result.output
            assert "IGNORE PATTERNS (2)" in result.output
            assert "Using .gitignore: Yes" in result.output

    def test_view_nonexistent_config(self) -> None:
        """Test viewing a nonexistent configuration file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "does-not-exist.yaml"

            result = runner.invoke(view, ["--path", str(nonexistent)])

            assert result.exit_code == 1
            assert "Configuration file not found" in result.output
            assert "Run 'antipasta config generate'" in result.output

    def test_view_invalid_config_with_validation(self) -> None:
        """Test viewing an invalid configuration with validation enabled."""
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

            result = runner.invoke(view, ["--path", str(config_file)])

            assert result.exit_code == 0  # Still shows output
            assert "Status: ❌ Invalid" in result.output
            assert "Configuration has validation errors" in result.output

    def test_view_raw_format(self) -> None:
        """Test viewing configuration in raw format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            content = """# Test config
defaults:
  max_cyclomatic_complexity: 10
"""
            config_file.write_text(content)

            result = runner.invoke(view, ["--path", str(config_file), "--format", "raw"])

            assert result.exit_code == 0
            assert result.output.strip() == content.strip()

    def test_view_json_format(self) -> None:
        """Test viewing configuration in JSON format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
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
        enabled: true

ignore_patterns: []
use_gitignore: false
"""
            )

            result = runner.invoke(view, ["--path", str(config_file), "--format", "json"])

            assert result.exit_code == 0
            # Parse JSON to verify it's valid
            data = json.loads(result.output)
            assert data["defaults"]["max_cyclomatic_complexity"] == 10
            assert data["languages"][0]["name"] == "python"
            assert data["use_gitignore"] is False

    def test_view_yaml_format(self) -> None:
        """Test viewing configuration in YAML format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10

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

            result = runner.invoke(view, ["--path", str(config_file), "--format", "yaml"])

            assert result.exit_code == 0
            # Parse YAML to verify it's valid
            data = yaml.safe_load(result.output)
            assert data["defaults"]["max_cyclomatic_complexity"] == 10
            assert data["languages"][0]["name"] == "python"

    def test_view_table_format(self) -> None:
        """Test viewing configuration in table format."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
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

            result = runner.invoke(view, ["--path", str(config_file), "--format", "table"])

            assert result.exit_code == 0
            assert "ANTIPASTA CONFIGURATION" in result.output
            assert "DEFAULT THRESHOLDS" in result.output
            assert "LANGUAGES" in result.output
            assert "python: 1 metrics, 1 extensions" in result.output
            assert "javascript: 1 metrics, 2 extensions" in result.output
            assert "IGNORE PATTERNS (2)" in result.output
            assert "╔" in result.output  # Box drawing characters
            assert "║" in result.output
            assert "╚" in result.output

    def test_view_no_languages_config(self) -> None:
        """Test viewing configuration with no languages configured."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "minimal.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 10

languages: []
ignore_patterns: []
use_gitignore: false
"""
            )

            result = runner.invoke(view, ["--path", str(config_file)])

            assert result.exit_code == 0
            assert "No languages configured" in result.output
            assert "Using .gitignore: No" in result.output

    def test_view_many_ignore_patterns(self) -> None:
        """Test viewing configuration with many ignore patterns."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            patterns = [f"pattern_{i}" for i in range(10)]
            config_file.write_text(
                f"""
defaults:
  max_cyclomatic_complexity: 10

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "<="

ignore_patterns: {json.dumps(patterns)}
use_gitignore: true
"""
            )

            result = runner.invoke(view, ["--path", str(config_file), "--format", "table"])

            assert result.exit_code == 0
            assert "IGNORE PATTERNS (10)" in result.output
            assert "pattern_0" in result.output
            assert "... and 5 more" in result.output

    def test_view_no_validate_flag(self) -> None:
        """Test viewing configuration with --no-validate flag."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "invalid.yaml"
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: -5  # Invalid

languages: []
"""
            )

            result = runner.invoke(view, ["--path", str(config_file), "--no-validate"])

            assert result.exit_code == 0
            assert "Status: ❌ Invalid" in result.output
            # But no validation errors shown with --no-validate
            assert "Configuration has validation errors" not in result.output

    def test_view_default_config_file(self) -> None:
        """Test that view defaults to .antipasta.yaml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create .antipasta.yaml in the current directory
            config_file = Path(".antipasta.yaml")
            config_file.write_text(
                """
defaults:
  max_cyclomatic_complexity: 15

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 15
        comparison: "<="

ignore_patterns: []
use_gitignore: true
"""
            )

            # Run view without --path argument
            result = runner.invoke(view)

            assert result.exit_code == 0
            assert "Configuration: .antipasta.yaml" in result.output
            assert "Status: ✅ Valid" in result.output
            assert "≤ 15" in result.output
