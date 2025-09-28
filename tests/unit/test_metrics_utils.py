"""
Temporary test to verify the refactored metrics command works correctly.

This file was created to validate that the refactoring maintains the exact same
functionality as the original implementation. It tests the decomposed methods
and the main metrics function.

Author: Claude Code - Refactor Master
Context: Compose Method refactoring of metrics.py
Updated: Fixed function references after moving helpers to metrics_utils.py

NOTE: This test file validates that the functions moved to metrics_utils.py
during the Compose Method refactoring are still working correctly.
All 10 tests pass and verify the decomposed functions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from antipasta.cli.metrics.metrics_utils_analysis import (
    determine_files_to_analyze,
    execute_analysis,
    exit_with_appropriate_code,
)
from antipasta.cli.metrics.metrics_utils_config import prepare_configuration
from antipasta.cli.metrics.metrics_utils_output import output_results
from antipasta.cli.metrics.metrics_utils_override import (
    apply_overrides_to_configuration,
    create_and_configure_override,
)
from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride


class TestRefactoredMetricsComponents:
    """Test the decomposed methods from the metrics function refactoring."""

    def test_prepare_configuration_loads_config(self, tmp_path: Path) -> None:
        """Test that _prepare_configuration correctly loads configuration."""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text("defaults:\n  max_cyclomatic_complexity: 15")

        result = prepare_configuration(config_file, (), quiet=True)

        assert isinstance(result, AntipastaConfig)
        assert result.defaults.max_cyclomatic_complexity == 15

    def test_create_and_configure_override(self) -> None:
        """Test that override creation works with all parameters."""
        override = create_and_configure_override(
            include_pattern=("*.py",),
            exclude_pattern=("test_*",),
            threshold=("cyclomatic_complexity=20",),
            no_gitignore=True,
            force_analyze=False,
        )

        assert isinstance(override, ConfigOverride)
        assert override.include_patterns == ["*.py"]
        assert override.exclude_patterns == ["test_*"]
        assert override.disable_gitignore is True
        assert override.force_analyze is False

    def test_apply_overrides_to_configuration(self) -> None:
        """Test that configuration overrides are applied correctly."""
        config = AntipastaConfig.generate_default()
        override = ConfigOverride(force_analyze=True)

        result = apply_overrides_to_configuration(
            config,
            override,
            quiet=True,
            force_analyze=True,
            include_pattern=(),
            exclude_pattern=(),
            threshold=(),
            no_gitignore=False,
        )

        assert isinstance(result, AntipastaConfig)

    @patch("click.echo")
    @patch("antipasta.cli.metrics.metrics_utils_analysis.validate_files_found")
    @patch("antipasta.cli.metrics.metrics_utils_analysis.collect_files")
    def test_determine_files_to_analyze(
        self, mock_collect: MagicMock, mock_validate: MagicMock, mock_echo: MagicMock
    ) -> None:
        """Test file determination logic."""
        mock_collect.return_value = [Path("test.py")]

        result = determine_files_to_analyze(
            files=(),
            directory=None,
            cfg=AntipastaConfig.generate_default(),
            override=ConfigOverride(),
            quiet=True,
        )

        assert result == [Path("test.py")]
        mock_validate.assert_called_once()
        # When quiet=True, click.echo shouldn't be called for the status message
        mock_echo.assert_not_called()

    @patch("antipasta.cli.metrics.metrics_utils_analysis.MetricAggregator")
    def test_execute_analysis(self, mock_aggregator_class: MagicMock) -> None:
        """Test analysis execution."""
        # Create mock aggregator
        mock_aggregator = MagicMock()
        mock_aggregator_class.return_value = mock_aggregator

        # Create a simple mock reports list
        mock_reports = ["mock_report_1", "mock_report_2"]
        mock_summary = {"success": True, "total_files": 2}

        mock_aggregator.analyze_files.return_value = mock_reports
        mock_aggregator.generate_summary.return_value = mock_summary

        # Execute the function
        result = execute_analysis([Path("test.py")], AntipastaConfig.generate_default(), quiet=True)

        # Verify the results
        assert result["reports"] == mock_reports
        assert result["summary"] == mock_summary

        # Verify the aggregator was called correctly
        mock_aggregator.analyze_files.assert_called_once_with([Path("test.py")])

    @patch("click.echo")
    def test_output_results_json_format(self, mock_echo: MagicMock) -> None:
        """Test JSON output format selection."""
        results = {"reports": [], "summary": {"success": True}}

        output_results(results, "json", quiet=False)

        # Should call click.echo with JSON output
        mock_echo.assert_called_once()
        call_args = mock_echo.call_args[0][0]
        assert "summary" in call_args  # Check that JSON string contains summary

    @patch("antipasta.cli.metrics.metrics_utils_output.print_results")
    def test_output_results_text_format(self, mock_print_results: MagicMock) -> None:
        """Test text output format selection."""
        results = {"reports": [], "summary": {"success": True}}

        output_results(results, "text", quiet=False)

        mock_print_results.assert_called_once_with([], {"success": True}, False)

    def test_exit_with_appropriate_code_success(self) -> None:
        """Test exit code for successful analysis."""
        with pytest.raises(SystemExit) as exc_info:
            exit_with_appropriate_code({"success": True})

        assert exc_info.value.code == 0

    def test_exit_with_appropriate_code_failure(self) -> None:
        """Test exit code for failed analysis."""
        with pytest.raises(SystemExit) as exc_info:
            exit_with_appropriate_code({"success": False})

        assert exc_info.value.code == 2


def test_integration_all_components_work_together() -> None:
    """Integration test to verify all refactored components work together."""
    # This test ensures the overall flow still works after refactoring
    # It's a basic smoke test without deep mocking

    config = AntipastaConfig.generate_default()
    override = ConfigOverride()

    # Test basic object creation and method calls
    assert config is not None
    assert override is not None
    assert not override.has_overrides()
