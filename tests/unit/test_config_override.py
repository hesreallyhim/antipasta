"""Unit tests for the ConfigOverride class."""

import pytest

from antipasta.core.config_override import ConfigOverride


class TestConfigOverride:
    """Tests for ConfigOverride functionality."""

    def test_init_empty(self) -> None:
        """Test initialization with no overrides."""
        override = ConfigOverride()
        assert override.include_patterns == []
        assert override.exclude_patterns == []
        assert override.threshold_overrides == {}
        assert override.disable_gitignore is False
        assert override.force_analyze is False
        assert not override.has_overrides()

    def test_init_with_values(self) -> None:
        """Test initialization with override values."""
        override = ConfigOverride(
            include_patterns=["**/tests/**"],
            exclude_patterns=["**/build/**"],
            disable_gitignore=True,
            force_analyze=False,
        )
        # Set threshold using the method
        override.set_threshold("cyclomatic_complexity", 15)

        assert override.include_patterns == ["**/tests/**"]
        assert override.exclude_patterns == ["**/build/**"]
        assert override.threshold_overrides == {"cyclomatic_complexity": 15}
        assert override.disable_gitignore is True
        assert override.force_analyze is False
        assert override.has_overrides()

    def test_add_include_pattern(self) -> None:
        """Test adding include patterns."""
        override = ConfigOverride()
        override.add_include_pattern("**/tests/**")
        assert override.include_patterns == ["**/tests/**"]

        # Test duplicate prevention
        override.add_include_pattern("**/tests/**")
        assert override.include_patterns == ["**/tests/**"]

        # Add different pattern
        override.add_include_pattern("**/docs/**")
        assert override.include_patterns == ["**/tests/**", "**/docs/**"]

    def test_add_exclude_pattern(self) -> None:
        """Test adding exclude patterns."""
        override = ConfigOverride()
        override.add_exclude_pattern("**/build/**")
        assert override.exclude_patterns == ["**/build/**"]

        # Test duplicate prevention
        override.add_exclude_pattern("**/build/**")
        assert override.exclude_patterns == ["**/build/**"]

        # Add different pattern
        override.add_exclude_pattern("**/dist/**")
        assert override.exclude_patterns == ["**/build/**", "**/dist/**"]

    def test_set_threshold_valid(self) -> None:
        """Test setting valid metric thresholds."""
        override = ConfigOverride()
        override.set_threshold("cyclomatic_complexity", 15.0)
        assert override.threshold_overrides["cyclomatic_complexity"] == 15.0

        override.set_threshold("maintainability_index", 40.0)
        assert override.threshold_overrides["maintainability_index"] == 40.0

    def test_set_threshold_invalid_metric(self) -> None:
        """Test setting threshold with invalid metric type."""
        override = ConfigOverride()
        with pytest.raises(ValueError, match="Invalid metric type"):
            override.set_threshold("invalid_metric", 10.0)

    def test_set_threshold_negative_value(self) -> None:
        """Test setting negative threshold value."""
        override = ConfigOverride()
        with pytest.raises(ValueError, match="must be >="):
            override.set_threshold("cyclomatic_complexity", -5.0)

    def test_set_threshold_respects_metric_constraints(self) -> None:
        """Test that set_threshold respects metric-specific constraints."""
        override = ConfigOverride()

        # Cyclomatic complexity should be 1-50
        override.set_threshold("cyclomatic_complexity", 25)
        assert override.threshold_overrides["cyclomatic_complexity"] == 25

        with pytest.raises(ValueError, match="must be <="):
            override.set_threshold("cyclomatic_complexity", 51)

        with pytest.raises(ValueError, match="must be >="):
            override.set_threshold("cyclomatic_complexity", 0)

        # Maintainability index should be 0-100
        override.set_threshold("maintainability_index", 75)
        assert override.threshold_overrides["maintainability_index"] == 75

        with pytest.raises(ValueError, match="must be <="):
            override.set_threshold("maintainability_index", 150)

    def test_parse_threshold_string_valid(self) -> None:
        """Test parsing valid threshold strings."""
        override = ConfigOverride()
        override.parse_threshold_string("cyclomatic_complexity=15")
        assert override.threshold_overrides["cyclomatic_complexity"] == 15

        override.parse_threshold_string("maintainability_index=45.5")
        assert override.threshold_overrides["maintainability_index"] == 45.5

    def test_parse_threshold_string_invalid_format(self) -> None:
        """Test parsing invalid threshold string format."""
        override = ConfigOverride()

        # No equals sign
        with pytest.raises(ValueError, match="Invalid threshold format"):
            override.parse_threshold_string("cyclomatic_complexity")

        # Invalid value
        with pytest.raises(ValueError, match="Invalid threshold value"):
            override.parse_threshold_string("cyclomatic_complexity=abc")

    def test_parse_threshold_string_with_spaces(self) -> None:
        """Test parsing threshold string with spaces."""
        override = ConfigOverride()
        override.parse_threshold_string(" cyclomatic_complexity = 15 ")
        assert override.threshold_overrides["cyclomatic_complexity"] == 15

    def test_has_overrides(self) -> None:
        """Test has_overrides detection."""
        override = ConfigOverride()
        assert not override.has_overrides()

        # Test each type of override
        override.include_patterns.append("test")
        assert override.has_overrides()

        override = ConfigOverride()
        override.exclude_patterns.append("test")
        assert override.has_overrides()

        override = ConfigOverride()
        override.set_threshold("cyclomatic_complexity", 10)
        assert override.has_overrides()

        override = ConfigOverride()
        override.disable_gitignore = True
        assert override.has_overrides()

        override = ConfigOverride()
        override.force_analyze = True
        assert override.has_overrides()

    def test_get_effective_ignore_patterns_normal(self) -> None:
        """Test getting effective ignore patterns in normal mode."""
        base_patterns = ["**/test_*.py", "**/tests/**"]
        override = ConfigOverride(exclude_patterns=["**/build/**", "**/dist/**"])

        effective = override.get_effective_ignore_patterns(base_patterns)
        assert "**/test_*.py" in effective
        assert "**/tests/**" in effective
        assert "**/build/**" in effective
        assert "**/dist/**" in effective

    def test_get_effective_ignore_patterns_force_analyze(self) -> None:
        """Test getting effective ignore patterns with force_analyze."""
        base_patterns = ["**/test_*.py", "**/tests/**"]
        override = ConfigOverride(exclude_patterns=["**/build/**"], force_analyze=True)

        effective = override.get_effective_ignore_patterns(base_patterns)
        assert effective == []  # All patterns ignored when force_analyze is True

    def test_get_effective_ignore_patterns_no_duplicates(self) -> None:
        """Test that duplicate patterns are not added."""
        base_patterns = ["**/tests/**", "**/build/**"]
        override = ConfigOverride(exclude_patterns=["**/build/**", "**/dist/**"])

        effective = override.get_effective_ignore_patterns(base_patterns)
        # Should only have one "**/build/**"
        assert effective.count("**/build/**") == 1
        assert "**/tests/**" in effective
        assert "**/dist/**" in effective

    def test_should_force_include_with_patterns(self) -> None:
        """Test should_force_include with include patterns."""
        override = ConfigOverride(include_patterns=["**/tests/**", "**/*_test.py"])

        assert override.should_force_include("tests/unit/test_config.py")
        assert override.should_force_include("src/module_test.py")
        assert not override.should_force_include("src/module.py")

    def test_should_force_include_force_analyze(self) -> None:
        """Test should_force_include with force_analyze."""
        override = ConfigOverride(force_analyze=True)

        # Everything should be included
        assert override.should_force_include("any/file/path.py")
        assert override.should_force_include("build/output.txt")

    def test_should_force_include_no_patterns(self) -> None:
        """Test should_force_include with no patterns."""
        override = ConfigOverride()

        assert not override.should_force_include("tests/test_file.py")
        assert not override.should_force_include("any/file.py")

    def test_merge_with_config_dict_basic(self) -> None:
        """Test merging overrides with a config dictionary."""
        config_dict = {
            "use_gitignore": True,
            "ignore_patterns": ["**/tests/**"],
            "defaults": {
                "max_cyclomatic_complexity": 10,
                "min_maintainability_index": 50,
            },
            "languages": [
                {
                    "name": "python",
                    "metrics": [
                        {"type": "cyclomatic_complexity", "threshold": 10},
                        {"type": "maintainability_index", "threshold": 50},
                    ],
                }
            ],
        }

        override = ConfigOverride(
            exclude_patterns=["**/build/**"],
            disable_gitignore=True,
        )
        override.set_threshold("cyclomatic_complexity", 15)

        merged = override.merge_with_config_dict(config_dict)

        # Check gitignore was disabled
        assert merged["use_gitignore"] is False

        # Check patterns were merged
        assert "**/tests/**" in merged["ignore_patterns"]
        assert "**/build/**" in merged["ignore_patterns"]

        # Check thresholds were updated
        assert merged["defaults"]["max_cyclomatic_complexity"] == 15
        assert merged["languages"][0]["metrics"][0]["threshold"] == 15

    def test_merge_with_config_dict_force_analyze(self) -> None:
        """Test merging with force_analyze clears ignore patterns."""
        config_dict = {
            "ignore_patterns": ["**/tests/**", "**/build/**"],
            "use_gitignore": True,
        }

        override = ConfigOverride(force_analyze=True)
        merged = override.merge_with_config_dict(config_dict)

        # Ignore patterns should be cleared
        assert merged["ignore_patterns"] == []
        # Gitignore should remain as configured
        assert merged["use_gitignore"] is True

    def test_merge_with_config_dict_all_threshold_types(self) -> None:
        """Test merging all types of threshold overrides."""
        config_dict = {
            "defaults": {
                "max_cyclomatic_complexity": 10,
                "max_cognitive_complexity": 15,
                "min_maintainability_index": 50,
                "max_halstead_volume": 1000,
                "max_halstead_difficulty": 10,
                "max_halstead_effort": 10000,
            }
        }

        override = ConfigOverride()
        override.set_threshold("cyclomatic_complexity", 20)
        override.set_threshold("cognitive_complexity", 25)
        override.set_threshold("maintainability_index", 30)
        override.set_threshold("halstead_volume", 2000)
        override.set_threshold("halstead_difficulty", 20)
        override.set_threshold("halstead_effort", 20000)

        merged = override.merge_with_config_dict(config_dict)

        assert merged["defaults"]["max_cyclomatic_complexity"] == 20
        assert merged["defaults"]["max_cognitive_complexity"] == 25
        assert merged["defaults"]["min_maintainability_index"] == 30
        assert merged["defaults"]["max_halstead_volume"] == 2000
        assert merged["defaults"]["max_halstead_difficulty"] == 20
        assert merged["defaults"]["max_halstead_effort"] == 20000
