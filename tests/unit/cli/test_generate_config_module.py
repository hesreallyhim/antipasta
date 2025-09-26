"""Unit tests for the config_generate module."""

from pathlib import Path
import tempfile
from typing import cast
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner
import pytest

from antipasta.cli.config.config_generate import generate
from antipasta.cli.config.config_generate.file_operations import save_config as _save_config
from antipasta.cli.config.config_generate.language_config import (
    create_javascript_config as _create_javascript_config,
    create_python_config as _create_python_config,
)
from antipasta.cli.config.config_generate.validation import (
    prompt_with_validation,
    validate_with_pydantic,
)
from antipasta.core.config import (
    AntipastaConfig,
    ComparisonOperator,
    DefaultsConfig,
    LanguageConfig,
    MetricConfig,
)
from antipasta.core.metrics import MetricType


class TestValidateWithPydantic:
    """Test validate_with_pydantic function."""

    def test_valid_cyclomatic_complexity(self) -> None:
        """Test valid cyclomatic complexity values."""
        assert validate_with_pydantic("cyclomatic_complexity", "10") == 10
        assert validate_with_pydantic("cyclomatic_complexity", "1") == 1
        assert validate_with_pydantic("cyclomatic_complexity", "50") == 50

    def test_cyclomatic_below_minimum(self) -> None:
        """Test cyclomatic complexity below minimum raises error."""
        with pytest.raises(click.BadParameter, match="Value must be >= 1"):
            validate_with_pydantic("cyclomatic_complexity", "0")

    def test_cyclomatic_above_maximum(self) -> None:
        """Test cyclomatic complexity above maximum raises error."""
        with pytest.raises(click.BadParameter, match="Value must be <= 50"):
            validate_with_pydantic("cyclomatic_complexity", "51")

    def test_maintainability_index_range(self) -> None:
        """Test maintainability index validation."""
        assert validate_with_pydantic("maintainability_index", "0") == 0
        assert validate_with_pydantic("maintainability_index", "50.5") == 50.5
        assert validate_with_pydantic("maintainability_index", "100") == 100

        with pytest.raises(click.BadParameter, match="Value must be <= 100"):
            validate_with_pydantic("maintainability_index", "101")

    def test_non_numeric_value(self) -> None:
        """Test non-numeric value raises error."""
        with pytest.raises(click.BadParameter, match="Must be a valid number"):
            validate_with_pydantic("cyclomatic_complexity", "abc")


class TestHalsteadValidation:
    """Test Halstead metric validation with Pydantic."""

    def test_halstead_volume_range(self) -> None:
        """Test Halstead volume validation."""
        assert validate_with_pydantic("halstead_volume", "0") == 0
        assert validate_with_pydantic("halstead_volume", "50000.5") == 50000.5
        assert validate_with_pydantic("halstead_volume", "100000") == 100000

        with pytest.raises(click.BadParameter, match="Value must be <= 100000"):
            validate_with_pydantic("halstead_volume", "100001")

    def test_halstead_difficulty_range(self) -> None:
        """Test Halstead difficulty validation."""
        assert validate_with_pydantic("halstead_difficulty", "0") == 0
        assert validate_with_pydantic("halstead_difficulty", "10.5") == 10.5
        assert validate_with_pydantic("halstead_difficulty", "100") == 100

        with pytest.raises(click.BadParameter, match="Value must be <= 100"):
            validate_with_pydantic("halstead_difficulty", "101")

    def test_halstead_effort_range(self) -> None:
        """Test Halstead effort validation."""
        assert validate_with_pydantic("halstead_effort", "0") == 0
        assert validate_with_pydantic("halstead_effort", "500000") == 500000
        assert validate_with_pydantic("halstead_effort", "1000000") == 1000000

        with pytest.raises(click.BadParameter, match="Value must be <= 1000000"):
            validate_with_pydantic("halstead_effort", "1000001")


class TestPromptWithValidation:
    """Test prompt_with_validation function."""

    @patch("click.prompt")
    @patch("click.echo")
    def test_valid_input_first_try(self, mock_echo: MagicMock, mock_prompt: MagicMock) -> None:
        """Test valid input on first attempt."""
        mock_prompt.return_value = "10"

        def validator(v: str) -> int:
            return int(v)

        result = prompt_with_validation("Enter number", default=5, validator=validator)

        assert result == 10
        mock_prompt.assert_called_once_with("Enter number", default=5, show_default=True)
        mock_echo.assert_not_called()

    @patch("click.prompt")
    @patch("click.echo")
    def test_invalid_then_valid_input(self, mock_echo: MagicMock, mock_prompt: MagicMock) -> None:
        """Test invalid input followed by valid input."""
        mock_prompt.side_effect = ["abc", "10"]

        def validator(v: str) -> int:
            try:
                return int(v)
            except ValueError:
                raise click.BadParameter("Invalid number") from None

        result = prompt_with_validation("Enter number", default=5, validator=validator)

        assert result == 10
        assert mock_prompt.call_count == 2
        assert any("Invalid input" in str(call) for call in mock_echo.call_args_list)

    @patch("click.prompt")
    @patch("click.echo")
    def test_with_help_text(self, mock_echo: MagicMock, mock_prompt: MagicMock) -> None:
        """Test prompt with help text."""
        mock_prompt.return_value = "10"

        def validator(v: str) -> int:
            return int(v)

        result = prompt_with_validation(
            "Enter number", default=5, validator=validator, help_text="This is help text"
        )

        assert result == 10
        mock_echo.assert_called_once_with("  This is help text")


class TestGenerateConfigCommand:
    """Test config_generate command."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_non_interactive_mode(self) -> None:
        """Test non-interactive generation with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            result = self.runner.invoke(
                generate, ["--output", str(output_path), "--non-interactive"]
            )

            assert result.exit_code == 0
            assert output_path.exists()
            assert "Configuration saved to" in result.output

            # Verify the file contains valid YAML
            config = AntipastaConfig.from_yaml(output_path)
            assert config.defaults.max_cyclomatic_complexity == 10
            assert len(config.languages) > 0

    @patch("click.confirm")
    @patch("click.prompt")
    def test_interactive_mode_minimal(
        self, mock_prompt: MagicMock, mock_confirm: MagicMock
    ) -> None:
        """Test interactive mode with minimal selections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            # Mock responses for interactive prompts
            mock_prompt.side_effect = [
                "10",  # cyclomatic complexity
                "15",  # cognitive complexity
                "50",  # maintainability index
                "",  # no additional patterns
            ]

            mock_confirm.side_effect = [
                False,  # no advanced metrics
                True,  # include Python
                # False,  # no JavaScript
                True,  # use gitignore
                False,  # no test defaults
                # File doesn't exist, so no overwrite prompt
            ]

            result = self.runner.invoke(generate, ["--output", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()
            assert "Configuration saved to" in result.output

    @patch("click.confirm")
    @patch("click.prompt")
    def test_interactive_mode_full(self, mock_prompt: MagicMock, mock_confirm: MagicMock) -> None:
        """Test interactive mode with all options."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            # Mock responses for interactive prompts
            mock_prompt.side_effect = [
                "10",  # cyclomatic complexity
                "15",  # cognitive complexity
                "50",  # maintainability index
                "1000",  # halstead volume
                "10",  # halstead difficulty
                "10000",  # halstead effort
                "**/vendor/**",  # additional pattern
                "",  # end patterns
            ]

            mock_confirm.side_effect = [
                True,  # advanced metrics
                True,  # include Python
                # True,  # include JavaScript
                True,  # use gitignore
                True,  # use test defaults
            ]

            result = self.runner.invoke(generate, ["--output", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()

            # Verify config content
            config = AntipastaConfig.from_yaml(output_path)
            assert config.defaults.max_halstead_volume == 1000
            assert len(config.languages) == 1  # Python (JS not supported yet)
            assert "**/vendor/**" in config.ignore_patterns

    @patch("click.confirm")
    def test_file_exists_no_overwrite(self, mock_confirm: MagicMock) -> None:
        """Test when file exists and user chooses not to overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"
            output_path.write_text("existing content")

            # Mock non-interactive mode but file exists
            mock_confirm.return_value = False  # Don't overwrite

            with patch("click.prompt") as mock_prompt:
                mock_prompt.side_effect = ["10", "15", "50", ""]
                mock_confirm.side_effect = [
                    False,  # no advanced
                    True,  # Python
                    # False,  # no JS
                    True,  # gitignore
                    False,  # no test defaults
                    False,  # Don't overwrite existing file
                ]

                result = self.runner.invoke(generate, ["--output", str(output_path)])

                assert result.exit_code == 0
                assert "Aborted" in result.output


class TestCreateLanguageConfigs:
    """Test language configuration creation functions."""

    def test_create_python_config(self) -> None:
        """Test Python configuration creation."""
        defaults = {
            "max_cyclomatic_complexity": 10,
            "max_cognitive_complexity": 15,
            "min_maintainability_index": 50,
            "max_halstead_volume": 1000,
            "max_halstead_difficulty": 10,
            "max_halstead_effort": 10000,
        }

        config = _create_python_config(defaults)

        assert config["name"] == "python"
        assert ".py" in config["extensions"]
        assert len(config["metrics"]) == 6

        # Check all metric types are present
        metric_types = [m["type"] for m in config["metrics"]]
        assert "cyclomatic_complexity" in metric_types
        assert "cognitive_complexity" in metric_types
        assert "maintainability_index" in metric_types
        assert "halstead_volume" in metric_types
        assert "halstead_difficulty" in metric_types
        assert "halstead_effort" in metric_types

        # Check thresholds match defaults
        cyclo_metric = next(m for m in config["metrics"] if m["type"] == "cyclomatic_complexity")
        assert cyclo_metric["threshold"] == 10
        assert cyclo_metric["comparison"] == "<="

    def test_create_javascript_config(self) -> None:
        """Test JavaScript/TypeScript configuration creation."""
        defaults = {
            "max_cyclomatic_complexity": 10,
            "max_cognitive_complexity": 15,
            "min_maintainability_index": 50,  # Not used for JS
        }

        config = _create_javascript_config(defaults)

        assert config["name"] == "javascript"
        assert ".js" in config["extensions"]
        assert ".ts" in config["extensions"]
        assert ".jsx" in config["extensions"]
        assert ".tsx" in config["extensions"]
        assert len(config["metrics"]) == 2  # Only cyclomatic and cognitive

        # Check metric types
        metric_types = [m["type"] for m in config["metrics"]]
        assert "cyclomatic_complexity" in metric_types
        assert "cognitive_complexity" in metric_types

        # Verify Halstead metrics are not included
        assert "halstead_volume" not in metric_types


class TestSaveConfig:
    """Test configuration saving functionality."""

    def test_save_config_success(self) -> None:
        """Test successful configuration save."""
        config = AntipastaConfig.generate_default()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            with patch("click.echo") as mock_echo:
                _save_config(config, output_path)

                assert output_path.exists()
                content = output_path.read_text()

                # Check file content
                assert "# antipasta configuration file" in content
                assert "defaults:" in content
                assert "languages:" in content
                assert "ignore_patterns:" in content
                assert "use_gitignore:" in content

                # Check success message
                assert any("Configuration saved" in str(call) for call in mock_echo.call_args_list)

    def test_save_config_with_custom_values(self) -> None:
        config = AntipastaConfig(
            defaults=DefaultsConfig(
                max_cyclomatic_complexity=5,
                max_cognitive_complexity=10,
                min_maintainability_index=70,
            ),
            languages=cast(
                list[LanguageConfig],
                [
                    {
                        "name": "python",
                        "extensions": [".py"],
                        "metrics": [
                            {"type": "cyclomatic_complexity", "threshold": 5, "comparison": "<="}
                        ],
                    }
                ],
            ),
            ignore_patterns=["**/tests/**", "**/vendor/**"],
            use_gitignore=False,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            _save_config(config, output_path)

            content = output_path.read_text()
            assert "max_cyclomatic_complexity: 5" in content
            assert "**/tests/**" in content
            assert "**/vendor/**" in content
            assert "use_gitignore: false" in content

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    @patch("click.echo")
    def test_save_config_error(self, mock_echo: MagicMock, mock_file: MagicMock) -> None:
        """Test error handling during save."""
        config = AntipastaConfig.generate_default()
        output_path = Path("/invalid/path/test.yaml")

        with pytest.raises(SystemExit) as exc_info:
            _save_config(config, output_path)

        assert exc_info.value.code == 1
        assert any("Error saving configuration" in str(call) for call in mock_echo.call_args_list)

    def test_save_config_empty_patterns(self) -> None:
        """Test saving config with no ignore patterns."""
        config = AntipastaConfig(
            defaults=DefaultsConfig(
                max_cyclomatic_complexity=10,
                max_cognitive_complexity=15,
                min_maintainability_index=50,
            ),
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[
                        MetricConfig(
                            type=MetricType.CYCLOMATIC_COMPLEXITY,
                            threshold=10,
                            comparison=ComparisonOperator.LE,
                        )
                    ],
                )
            ],
            ignore_patterns=[],
            use_gitignore=True,
        )
        # config = AntipastaConfig(**config_dict)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            _save_config(config, output_path)

            content = output_path.read_text()
            assert "ignore_patterns: []" in content


class TestInteractiveEdgeCases:
    """Test edge cases in interactive mode."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("click.confirm")
    @patch("click.prompt")
    def test_keyboard_interrupt(self, mock_prompt: MagicMock, mock_confirm: MagicMock) -> None:
        """Test handling keyboard interrupt during prompts."""
        mock_prompt.side_effect = KeyboardInterrupt()

        result = self.runner.invoke(generate)

        # Should exit gracefully
        assert result.exit_code != 0

    @patch("click.confirm")
    @patch("click.prompt")
    def test_validation_error_in_config(
        self, mock_prompt: MagicMock, mock_confirm: MagicMock
    ) -> None:
        """Test handling validation errors when creating config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.yaml"

            # Mock invalid responses that will cause validation error
            mock_prompt.side_effect = [
                "-10",  # Invalid negative cyclomatic complexity
                "15",
                "50",
                "",
            ]

            mock_confirm.side_effect = [
                False,  # no advanced
                True,  # Python
                False,  # no JS
                True,  # gitignore
                False,  # no test defaults
            ]

            with patch("click.echo"):
                result = self.runner.invoke(generate, ["--output", str(output_path)])

            # Should handle the validation gracefully
            # The validator should catch this before config creation
            assert result.exit_code != 0
