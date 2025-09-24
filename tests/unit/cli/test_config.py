"""Tests for the config command group."""

from pathlib import Path
import tempfile

from click.testing import CliRunner

from antipasta.cli.main import cli


class TestConfigCommandGroup:
    """Test the config command group and subcommands."""

    def test_config_help(self) -> None:
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "--help"])

        assert result.exit_code == 0
        assert "Manage antipasta configuration files" in result.output
        assert "Commands:" in result.output
        assert "generate" in result.output
        assert "validate" in result.output
        assert "view" in result.output

    def test_config_generate_subcommand(self) -> None:
        """Test config generate subcommand works."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test-config.yaml"

            result = runner.invoke(
                cli,
                ["config", "generate", "--output", str(output_file), "--non-interactive"],
            )

            assert result.exit_code == 0
            assert output_file.exists()
            assert "✅ Configuration saved to" in result.output

    def test_config_validate_subcommand(self) -> None:
        """Test config validate subcommand works."""
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

            result = runner.invoke(cli, ["config", "validate", str(config_file)])

            assert result.exit_code == 0
            assert "✅ Configuration file is valid" in result.output

    def test_config_view_subcommand(self) -> None:
        """Test config view subcommand works."""
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

            result = runner.invoke(cli, ["config", "view", "--path", str(config_file)])

            assert result.exit_code == 0
            assert f"Configuration: {config_file}" in result.output
            assert "Status: ✅ Valid" in result.output

    def test_backward_compatibility_generate_config(self) -> None:
        """Test backward compatibility for generate-config command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.yaml"

            result = runner.invoke(
                cli,
                ["generate-config", "--output", str(output_file), "--non-interactive"],
            )

            # Should work but show deprecation warning
            assert result.exit_code == 0
            assert "Warning: This command is deprecated" in result.output
            assert "Please use 'antipasta config generate'" in result.output
            assert output_file.exists()

    def test_backward_compatibility_validate_config(self) -> None:
        """Test backward compatibility for validate-config command."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "valid.yaml"
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

            result = runner.invoke(cli, ["validate-config", str(config_file)])

            # Should work but show deprecation warning
            assert result.exit_code == 0
            assert "Warning: This command is deprecated" in result.output
            assert "Please use 'antipasta config validate'" in result.output
            assert "✅ Configuration file is valid" in result.output

    def test_deprecated_commands_hidden_from_help(self) -> None:
        """Test that deprecated commands are hidden from main help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        # New commands should be visible
        assert "config" in result.output
        assert "metrics" in result.output

        # Old commands should be hidden (not in main help)
        # They should not appear as top-level commands
        help_lines = result.output.split("\n")
        commands_section = False
        for line in help_lines:
            if "Commands:" in line:
                commands_section = True
            elif commands_section and line.strip():
                # Check command names in the Commands section
                # Deprecated commands should not be listed here
                assert not line.strip().startswith("generate-config")
                assert not line.strip().startswith("validate-config")
