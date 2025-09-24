"""Tests for threshold prefix feature.

Tests the three-letter prefix convenience feature for threshold overrides.
This allows users to use 'cyc=15' instead of 'cyclomatic_complexity=15' etc.
"""

import pytest

from antipasta.core.config_override import ConfigOverride


def test_threshold_prefix_parsing() -> None:
    """Test that three-letter prefixes work for threshold overrides."""
    override = ConfigOverride()

    # Test cyclomatic_complexity prefix
    override.parse_threshold_string("cyc=20")
    assert override.threshold_overrides["cyclomatic_complexity"] == 20

    # Test cognitive_complexity prefix
    override.parse_threshold_string("cog=15")
    assert override.threshold_overrides["cognitive_complexity"] == 15

    # Test maintainability_index prefix
    override.parse_threshold_string("mai=60")
    assert override.threshold_overrides["maintainability_index"] == 60

    # Test halstead_volume prefix
    override.parse_threshold_string("vol=1000")
    assert override.threshold_overrides["halstead_volume"] == 1000

    # Test halstead_difficulty prefix
    override.parse_threshold_string("dif=30")
    assert override.threshold_overrides["halstead_difficulty"] == 30

    # Test halstead_effort prefix
    override.parse_threshold_string("eff=10000")
    assert override.threshold_overrides["halstead_effort"] == 10000


def test_full_names_still_work() -> None:
    """Test that full metric names still work alongside prefixes."""
    override = ConfigOverride()

    # Full names should still work
    override.parse_threshold_string("cyclomatic_complexity=25")
    assert override.threshold_overrides["cyclomatic_complexity"] == 25

    override.parse_threshold_string("cognitive_complexity=18")
    assert override.threshold_overrides["cognitive_complexity"] == 18

    override.parse_threshold_string("maintainability_index=55")
    assert override.threshold_overrides["maintainability_index"] == 55


def test_mixed_prefixes_and_full_names() -> None:
    """Test mixing prefixes and full names in the same override object."""
    override = ConfigOverride()

    # Mix prefixes and full names
    override.parse_threshold_string("cyc=20")
    override.parse_threshold_string("cognitive_complexity=15")
    override.parse_threshold_string("mai=60")
    override.parse_threshold_string("halstead_volume=1000")

    assert override.threshold_overrides["cyclomatic_complexity"] == 20
    assert override.threshold_overrides["cognitive_complexity"] == 15
    assert override.threshold_overrides["maintainability_index"] == 60
    assert override.threshold_overrides["halstead_volume"] == 1000


def test_invalid_prefix_passes_through() -> None:
    """Test that invalid prefixes are treated as invalid metric types."""
    override = ConfigOverride()

    # This should fail at the set_threshold step with invalid metric type
    with pytest.raises(ValueError, match="Invalid metric type"):
        override.parse_threshold_string("xyz=10")
