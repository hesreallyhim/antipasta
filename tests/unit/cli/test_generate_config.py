"""Tests for the generate-config CLI command."""

from pathlib import Path
import tempfile
from unittest.mock import patch

from click.testing import CliRunner

from antipasta.cli.config.config_generate import generate
from antipasta.core.config import AntipastaConfig


class TestGenerateConfigCommand:
    """Test the generate-config command."""

    def test_non_interactive_generates_default_config(self) -> None:
        """Test that non-interactive mode generates a valid default config."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test-config.yaml"

            result = runner.invoke(generate, ["--non-interactive", "--output", str(output_file)])

            assert result.exit_code == 0
            assert output_file.exists()
            assert "✅ Configuration saved to" in result.output

            # Validate the generated file
            config = AntipastaConfig.from_yaml(output_file)
            assert config.defaults.max_cyclomatic_complexity == 10
            assert config.defaults.max_cognitive_complexity == 15
            assert config.defaults.min_maintainability_index == 50
            assert len(config.languages) == 1
            assert config.languages[0].name == "python"

    def test_non_interactive_overwrites_existing_file(self) -> None:
        """Test that non-interactive mode overwrites existing files without prompting."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "existing-config.yaml"
            output_file.write_text("existing content\n")

            result = runner.invoke(generate, ["--non-interactive", "--output", str(output_file)])

            assert result.exit_code == 0
            assert "✅ Configuration saved to" in result.output

            # Verify file was overwritten
            content = output_file.read_text()
            assert "existing content" not in content
            assert "# antipasta configuration file" in content

    def test_interactive_mode_with_defaults(self) -> None:
        """Test interactive mode accepting all defaults."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "interactive-config.yaml"

            # Simulate user input: accept all defaults
            user_input = "\n".join(
                [
                    "10",  # max cyclomatic complexity
                    "15",  # max cognitive complexity
                    "50",  # min maintainability index
                    "n",  # no advanced metrics
                    "y",  # include Python
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "",  # no additional patterns (press Enter to continue)
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "Welcome to antipasta configuration generator!" in result.output
            assert output_file.exists()

            # Validate the generated file
            config = AntipastaConfig.from_yaml(output_file)
            assert config.defaults.max_cyclomatic_complexity == 10
            assert config.defaults.max_cognitive_complexity == 15

    def test_interactive_mode_with_custom_values(self) -> None:
        """Test interactive mode with custom threshold values."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "custom-config.yaml"

            # Simulate user input: custom values
            user_input = "\n".join(
                [
                    "20",  # max cyclomatic complexity
                    "25",  # max cognitive complexity
                    "40",  # min maintainability index
                    "y",  # yes to advanced metrics
                    "2000",  # max halstead volume
                    "15",  # max halstead difficulty
                    "20000",  # max halstead effort
                    "y",  # include Python
                    "n",  # don't use gitignore
                    "n",  # don't use default test patterns
                    "*.pyc",  # first custom pattern
                    "__pycache__",  # second custom pattern
                    "",  # empty to finish patterns
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert output_file.exists()

            # Validate custom values
            config = AntipastaConfig.from_yaml(output_file)
            assert config.defaults.max_cyclomatic_complexity == 20
            assert config.defaults.max_cognitive_complexity == 25
            assert config.defaults.min_maintainability_index == 40
            assert config.defaults.max_halstead_volume == 2000
            assert config.defaults.max_halstead_difficulty == 15
            assert config.defaults.max_halstead_effort == 20000
            assert len(config.languages) == 1  # Only Python now, JS coming soon
            assert config.use_gitignore is False
            assert "*.pyc" in config.ignore_patterns
            assert "__pycache__" in config.ignore_patterns

    def test_interactive_mode_file_exists_abort(self) -> None:
        """Test that interactive mode aborts when user declines to overwrite."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "existing.yaml"
            output_file.write_text("existing content\n")

            # Simulate user input: decline overwrite
            user_input = "\n".join(
                [
                    "10",  # max cyclomatic complexity
                    "15",  # max cognitive complexity
                    "50",  # min maintainability index
                    "n",  # no advanced metrics
                    "y",  # include Python
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "",  # no additional patterns
                    "n",  # don't overwrite
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "File already exists. Overwrite?" in result.output
            assert "Aborted." in result.output

            # Verify file wasn't changed
            content = output_file.read_text()
            assert content == "existing content\n"

    def test_interactive_mode_file_exists_overwrite(self) -> None:
        """Test that interactive mode overwrites when user confirms."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "existing.yaml"
            output_file.write_text("old content\n")

            # Simulate user input: confirm overwrite
            user_input = "\n".join(
                [
                    "10",  # max cyclomatic complexity
                    "15",  # max cognitive complexity
                    "50",  # min maintainability index
                    "n",  # no advanced metrics
                    "y",  # include Python
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "",  # no additional patterns
                    "y",  # yes, overwrite
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "✅ Configuration saved to" in result.output

            # Verify file was overwritten
            content = output_file.read_text()
            assert "old content" not in content
            assert "# antipasta configuration file" in content

    def test_default_output_path(self) -> None:
        """Test that default output path is .antipasta.yaml."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(generate, ["--non-interactive"])

            assert result.exit_code == 0
            assert Path(".antipasta.yaml").exists()
            assert "✅ Configuration saved to .antipasta.yaml" in result.output

    def test_generated_config_has_helpful_comments(self) -> None:
        """Test that generated config includes helpful comments."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "commented-config.yaml"

            result = runner.invoke(generate, ["--non-interactive", "--output", str(output_file)])

            assert result.exit_code == 0

            content = output_file.read_text()
            assert "# antipasta configuration file" in content
            assert "# Generated by: antipasta config generate" in content
            assert "# Default thresholds for all languages" in content
            assert "# Language-specific configurations" in content
            assert "# Halstead metrics (advanced)" in content
            assert "# Files and patterns to ignore during analysis" in content
            assert "# Whether to use .gitignore file for excluding files" in content

    def test_javascript_coming_soon_message(self) -> None:
        """Test that JavaScript/TypeScript shows 'coming soon' message."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "config.yaml"

            # Try to configure without Python (to see JS message clearly)
            user_input = "\n".join(
                [
                    "10",  # max cyclomatic complexity
                    "15",  # max cognitive complexity
                    "50",  # min maintainability index
                    "n",  # no advanced metrics
                    "y",  # yes Python (at least one language needed)
                    # No JavaScript prompt anymore - just shows "coming soon"
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "",  # no additional patterns
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "JavaScript/TypeScript (coming soon)" in result.output

            # Verify only Python is configured
            config = AntipastaConfig.from_yaml(output_file)
            assert len(config.languages) == 1
            assert config.languages[0].name == "python"

    def test_permission_error_handling(self) -> None:
        """Test that permission errors are handled gracefully."""
        runner = CliRunner()
        with patch("io.open", side_effect=PermissionError("Permission denied")):
            result = runner.invoke(
                generate, ["--non-interactive", "--output", "/protected/config.yaml"]
            )

            assert result.exit_code == 1
            assert "❌ Error saving configuration: Permission denied" in result.output

    def test_interactive_mode_invalid_values_reprompt(self) -> None:
        """Test that invalid values trigger re-prompt."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test-config.yaml"

            # First attempt invalid, then valid values
            user_input = "\n".join(
                [
                    "-5",  # Invalid: negative cyclomatic
                    "10",  # Valid cyclomatic
                    "200",  # Invalid: cognitive > 100
                    "15",  # Valid cognitive
                    "150",  # Invalid: maintainability > 100
                    "50",  # Valid maintainability
                    "n",  # No advanced metrics
                    "y",  # Include Python
                    "y",  # Use gitignore
                    "y",  # Use default test patterns
                    "",  # No additional patterns
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert "Invalid input" in result.output
            assert "Please try again" in result.output
            assert result.exit_code == 0
            assert output_file.exists()

    def test_shows_metric_ranges_in_prompts(self) -> None:
        """Test that metric prompts show valid ranges."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test-ranges.yaml"

            # Just provide one invalid input to see the prompts
            user_input = "\n".join(
                [
                    "q",  # Invalid input to trigger error and see range
                    "10",  # Then valid input
                    "15",
                    "50",
                    "n",
                    "y",
                    "n",
                    "y",
                    "y",  # Use default test patterns
                    "",  # No additional patterns
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert "Range: 1-50" in result.output  # Cyclomatic
            assert "Range: 1-100" in result.output  # Cognitive
            assert "Range: 0-100" in result.output  # Maintainability

    def test_advanced_metrics_validation(self) -> None:
        """Test validation of advanced Halstead metrics."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test-halstead.yaml"

            # Test invalid Halstead metric values
            user_input = "\n".join(
                [
                    "10",  # Valid cyclomatic
                    "15",  # Valid cognitive
                    "50",  # Valid maintainability
                    "y",  # Yes to advanced metrics
                    "-100",  # Invalid: negative volume
                    "1000",  # Valid volume
                    "0",  # Invalid: difficulty too low
                    "10",  # Valid difficulty
                    "-5000",  # Invalid: negative effort
                    "10000",  # Valid effort
                    "y",  # Include Python
                    "y",  # Use gitignore
                    "y",  # Use default test patterns
                    "",  # No additional patterns
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert (
                "Range: 0-100000" in result.output or "0.0-100000.0" in result.output
            )  # Volume range
            assert (
                "Range: 0-100" in result.output or "0.0-100.0" in result.output
            )  # Difficulty range
            assert (
                "Range: 0-1000000" in result.output or "0.0-1000000.0" in result.output
            )  # Effort range
            assert "Invalid input" in result.output
            assert result.exit_code == 0
