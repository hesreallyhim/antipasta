"""Tests for the validate-config CLI command."""

from pathlib import Path

from click.testing import CliRunner

from antipasta.cli.main import cli


class TestValidateConfigCommand:
    """Tests for validate-config command."""

    def test_validate_valid_config(self, tmp_path: Path) -> None:
        """Test validating a valid configuration file."""
        config_content = """
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
"""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config", str(config_file)])

        assert result.exit_code == 0
        assert "Configuration file is valid" in result.output
        assert "Configuration summary:" in result.output
        assert "Languages: 1" in result.output

    def test_validate_invalid_config(self, tmp_path: Path) -> None:
        """Test validating an invalid configuration file."""
        config_content = """
defaults:
  max_cyclomatic_complexity: -5  # Invalid: negative value

languages:
  - name: python
    extensions:
      - py  # Invalid: missing dot
    metrics:
      - type: cyclomatic_complexity
        threshold: 10
        comparison: "invalid"  # Invalid comparison operator
"""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config", str(config_file)])

        assert result.exit_code == 1
        assert "Configuration validation failed" in result.output
        assert "Validation errors:" in result.output

    def test_validate_missing_file(self, tmp_path: Path) -> None:
        """Test validating a non-existent file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config", "non_existent.yaml"])

        assert result.exit_code == 2  # Click returns 2 for missing files
        assert "does not exist" in result.output.lower()

    def test_validate_malformed_yaml(self, tmp_path: Path) -> None:
        """Test validating a malformed YAML file."""
        config_content = """
defaults:
  max_cyclomatic_complexity: 10
  - invalid yaml syntax
"""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate-config", str(config_file)])

        assert result.exit_code == 1
        assert "Error loading configuration" in result.output
