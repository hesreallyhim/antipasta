"""Tests for ignore pattern input in generate-config command."""

from pathlib import Path
import tempfile

from click.testing import CliRunner

from antipasta.cli.config.config_generate import generate
from antipasta.core.config import AntipastaConfig


class TestIgnorePatternInput:
    """Test the new ignore pattern input behavior."""

    def test_multiple_patterns_one_at_a_time(self) -> None:
        """Test entering multiple patterns one at a time."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "multi-pattern.yaml"

            user_input = "\n".join(
                [
                    "10",  # cyclomatic
                    "15",  # cognitive
                    "50",  # maintainability
                    "n",  # no advanced
                    "y",  # Python
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "*.pyc",  # first additional pattern
                    "__pycache__/**",  # second additional pattern
                    "*.log",  # third additional pattern
                    "",  # empty to finish
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            if result.exit_code != 0:
                print(f"Error output: {result.output}")
                print(f"Exception: {result.exception}")
            assert result.exit_code == 0
            assert "Enter additional patterns to ignore" in result.output
            assert "✓ Added: *.pyc" in result.output
            assert "✓ Added: __pycache__/**" in result.output
            assert "✓ Added: *.log" in result.output
            assert "Total patterns to ignore: 6" in result.output  # 3 defaults + 3 custom

            config = AntipastaConfig.from_yaml(output_file)
            assert "**/test_*.py" in config.ignore_patterns  # default
            assert "*.pyc" in config.ignore_patterns
            assert "__pycache__/**" in config.ignore_patterns
            assert "*.log" in config.ignore_patterns

    def test_no_default_patterns(self) -> None:
        """Test declining default test patterns."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "no-defaults.yaml"

            user_input = "\n".join(
                [
                    "10",  # cyclomatic
                    "15",  # cognitive
                    "50",  # maintainability
                    "n",  # no advanced
                    "y",  # Python
                    "y",  # use gitignore
                    "n",  # NO default test patterns
                    "build/**",  # only custom pattern
                    "",  # empty to finish
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "Include default test file patterns?" in result.output
            assert "✓ Added: build/**" in result.output
            assert "Total patterns to ignore: 1" in result.output

            config = AntipastaConfig.from_yaml(output_file)
            assert len(config.ignore_patterns) == 1
            assert "build/**" in config.ignore_patterns
            assert "**/test_*.py" not in config.ignore_patterns

    def test_no_patterns_at_all(self) -> None:
        """Test having no ignore patterns at all."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "no-patterns.yaml"

            user_input = "\n".join(
                [
                    "10",  # cyclomatic
                    "15",  # cognitive
                    "50",  # maintainability
                    "n",  # no advanced
                    "y",  # Python
                    "y",  # use gitignore
                    "n",  # no default test patterns
                    "",  # no custom patterns either
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "ℹ️  No ignore patterns configured" in result.output

            config = AntipastaConfig.from_yaml(output_file)
            assert len(config.ignore_patterns) == 0

    def test_pattern_display_feedback(self) -> None:
        """Test that patterns are displayed with confirmation."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "feedback.yaml"

            user_input = "\n".join(
                [
                    "10",  # cyclomatic
                    "15",  # cognitive
                    "50",  # maintainability
                    "n",  # no advanced
                    "y",  # Python
                    "y",  # use gitignore
                    "y",  # use default test patterns
                    "*.tmp",  # one custom pattern
                    "",  # finish
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0
            assert "✓ Added default test patterns" in result.output
            assert "✓ Added: *.tmp" in result.output
            assert "Total patterns to ignore: 4" in result.output

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is properly handled in patterns."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "whitespace.yaml"

            user_input = "\n".join(
                [
                    "10",  # cyclomatic
                    "15",  # cognitive
                    "50",  # maintainability
                    "n",  # no advanced
                    "y",  # Python
                    "y",  # use gitignore
                    "n",  # no default test patterns
                    "  *.spaces  ",  # pattern with leading/trailing spaces
                    "*.tabs\t",  # pattern with trailing tab
                    "",  # finish
                ]
            )

            result = runner.invoke(generate, ["--output", str(output_file)], input=user_input)

            assert result.exit_code == 0

            config = AntipastaConfig.from_yaml(output_file)
            # Should be trimmed
            assert "*.spaces" in config.ignore_patterns
            assert "*.tabs" in config.ignore_patterns
            # Should not have whitespace
            assert "  *.spaces  " not in config.ignore_patterns
