"""Tests for configuration loading and validation."""

from pathlib import Path

from pydantic import ValidationError
import pytest

from antipasta.core.model.config import (
    AntipastaConfig,
    ComparisonOperator,
    DefaultsConfig,
    LanguageConfig,
    MetricConfig,
    NarrativeConfig,
)
from antipasta.core.model.metrics import MetricType
from antipasta.core.model.presets import PRESET_DEFINITIONS, PresetName


def _contains_callable(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_callable(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_callable(item) for item in value)
    return callable(value)


class TestMetricConfig:
    """Tests for MetricConfig model."""

    def test_valid_metric_config(self) -> None:
        """Test creating a valid metric configuration."""
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10,
            comparison=ComparisonOperator.LE,
        )
        assert config.type == MetricType.CYCLOMATIC_COMPLEXITY
        assert config.threshold == 10
        assert config.comparison == ComparisonOperator.LE
        assert config.enabled is True

    def test_negative_threshold_fails(self) -> None:
        """Test that negative thresholds are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MetricConfig(
                type=MetricType.CYCLOMATIC_COMPLEXITY,
                threshold=-1,
                comparison=ComparisonOperator.LE,
            )
        assert "Threshold must be non-negative" in str(exc_info.value)

    def test_default_enabled(self) -> None:
        """Test that metrics are enabled by default."""
        config = MetricConfig(
            type=MetricType.CYCLOMATIC_COMPLEXITY,
            threshold=10,
            comparison=ComparisonOperator.LE,
        )
        assert config.enabled is True


class TestLanguageConfig:
    """Tests for LanguageConfig model."""

    def test_valid_language_config(self) -> None:
        """Test creating a valid language configuration."""
        config = LanguageConfig(
            name="python",
            extensions=[".py", ".pyw"],
            metrics=[
                MetricConfig(
                    type=MetricType.CYCLOMATIC_COMPLEXITY,
                    threshold=10,
                    comparison=ComparisonOperator.LE,
                )
            ],
        )
        assert config.name == "python"
        assert config.extensions == [".py", ".pyw"]
        assert len(config.metrics) == 1

    def test_extension_without_dot_fails(self) -> None:
        """Test that extensions without dots are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LanguageConfig(
                name="python",
                extensions=["py"],  # Missing dot
                metrics=[],
            )
        assert "Extension must start with dot" in str(exc_info.value)


class TestDefaultsConfig:
    """Tests for DefaultsConfig model."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = DefaultsConfig()
        assert config.max_cyclomatic_complexity == 10
        assert config.min_maintainability_index == 50
        assert config.max_halstead_volume == 1000
        assert config.max_halstead_difficulty == 10
        assert config.max_halstead_effort == 10000
        assert config.max_cognitive_complexity == 15

    def test_negative_value_fails(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DefaultsConfig(max_cyclomatic_complexity=-1)
        # Check for Pydantic's error message about the constraint
        assert "greater than or equal to 1" in str(exc_info.value)


class TestAntipastaConfig:
    """Tests for AntipastaConfig model."""

    def test_generate_default(self) -> None:
        """Test generating default configuration."""
        config = AntipastaConfig.generate_default()
        assert isinstance(config.defaults, DefaultsConfig)
        assert len(config.languages) == 1
        assert config.languages[0].name == "python"
        assert len(config.languages[0].metrics) == 6
        assert len(config.ignore_patterns) == 3

    def test_get_language_config(self) -> None:
        """Test retrieving language-specific configuration."""
        config = AntipastaConfig.generate_default()
        python_config = config.get_language_config("python")
        assert python_config is not None
        assert python_config.name == "python"

        # Test case insensitive lookup
        python_config2 = config.get_language_config("Python")
        assert python_config2 is not None
        assert python_config2.name == "python"

        # Test non-existent language
        js_config = config.get_language_config("javascript")
        assert js_config is None

    def test_from_yaml_valid(self, tmp_path: Path) -> None:
        """Test loading valid YAML configuration."""
        yaml_content = """
defaults:
  max_cyclomatic_complexity: 15
  min_maintainability_index: 40

languages:
  - name: python
    extensions:
      - .py
    metrics:
      - type: cyclomatic_complexity
        threshold: 15
        comparison: "<="
"""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text(yaml_content)

        config = AntipastaConfig.from_yaml(config_file)
        assert config.defaults.max_cyclomatic_complexity == 15
        assert config.defaults.min_maintainability_index == 40
        assert len(config.languages) == 1

    def test_from_yaml_file_not_found(self) -> None:
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            AntipastaConfig.from_yaml("non_existent.yaml")

    def test_to_yaml(self, tmp_path: Path) -> None:
        """Test saving configuration to YAML."""
        config = AntipastaConfig.generate_default()
        output_file = tmp_path / "output.yaml"
        config.to_yaml(output_file)

        # Load it back
        loaded_config = AntipastaConfig.from_yaml(output_file)
        assert loaded_config.defaults.max_cyclomatic_complexity == 10
        assert len(loaded_config.languages) == 1

    def test_empty_yaml_uses_defaults(self, tmp_path: Path) -> None:
        """Test that empty YAML file results in default configuration."""
        config_file = tmp_path / ".antipasta.yaml"
        config_file.write_text("")

        config = AntipastaConfig.from_yaml(config_file)
        assert isinstance(config.defaults, DefaultsConfig)
        assert len(config.languages) == 0  # No languages defined
        assert len(config.ignore_patterns) == 0  # No ignore patterns

    def test_preset_definitions_are_declarative_data(self) -> None:
        """Preset definitions should stay data-only, with generic expansion code."""
        assert not _contains_callable(PRESET_DEFINITIONS)

    def test_readable_preset_expands_language_and_narrative_gates(self) -> None:
        """Readable preset materializes local readability and narrative gates."""
        config = AntipastaConfig(preset=PresetName.READABLE)
        python = config.get_language_config("python")

        assert config.preset is PresetName.READABLE
        assert python is not None
        metrics = {metric.type: metric for metric in python.metrics}
        assert metrics[MetricType.COGNITIVE_COMPLEXITY].threshold == 12
        assert metrics[MetricType.FUNCTION_STATEMENTS].threshold == 12
        assert metrics[MetricType.MESSAGE_CHAIN_DEPTH].threshold == 2
        assert config.narrative is not None
        assert config.narrative.name_clarity_floor == 0.65

    def test_profile_scales_preset_thresholds(self) -> None:
        """Profiles tune preset thresholds without changing the preset name."""
        config = AntipastaConfig(preset=PresetName.READABLE, profile="extreme")
        python = config.get_language_config("python")

        assert python is not None
        metrics = {metric.type: metric for metric in python.metrics}
        assert metrics[MetricType.COGNITIVE_COMPLEXITY].threshold == 8
        assert metrics[MetricType.FUNCTION_STATEMENTS].threshold == 8
        assert config.narrative is not None
        assert config.narrative.name_clarity_floor == 0.75

    def test_explicit_language_metric_wins_over_preset(self) -> None:
        """Preset expansion fills missing metrics without replacing explicit ones."""
        config = AntipastaConfig(
            preset=PresetName.READABLE,
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[
                        MetricConfig(
                            type=MetricType.COGNITIVE_COMPLEXITY,
                            threshold=99,
                            comparison=ComparisonOperator.LE,
                        )
                    ],
                )
            ],
        )

        python = config.get_language_config("python")
        javascript = config.get_language_config("javascript")

        assert python is not None
        metrics = {metric.type: metric for metric in python.metrics}
        assert metrics[MetricType.COGNITIVE_COMPLEXITY].threshold == 99
        assert metrics[MetricType.FUNCTION_STATEMENTS].threshold == 12
        assert javascript is None

    def test_explicit_project_block_values_win_over_preset(self) -> None:
        """Preset expansion fills missing project-block fields only."""
        config = AntipastaConfig(
            preset=PresetName.READABLE,
            narrative=NarrativeConfig(name_clarity_floor=0.9),
        )

        assert config.narrative is not None
        assert config.narrative.name_clarity_floor == 0.9
        assert config.narrative.narrator_step_budget == 9

    def test_compact_preset_enables_duplication_config(self) -> None:
        """Compact preset turns on duplication with profile-aware thresholds."""
        config = AntipastaConfig(preset=PresetName.COMPACT, profile="relaxed")

        assert config.duplication is not None
        assert config.duplication.normalize_constants is True
        assert config.duplication.max_ratio == 0.12

    def test_invalid_preset_fails_validation(self) -> None:
        """Unknown preset names are rejected."""
        with pytest.raises(ValidationError):
            AntipastaConfig.model_validate({"preset": "tiny"})
