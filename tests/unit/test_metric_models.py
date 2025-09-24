"""Test metric models and Pydantic validation."""

from pydantic import ValidationError
import pytest

from antipasta.core.metric_models import MetricThresholds


class TestMetricThresholds:
    """Test metric threshold validation via Pydantic."""

    def test_valid_thresholds(self) -> None:
        """Test valid threshold values."""
        thresholds = MetricThresholds(
            cyclomatic_complexity=10,
            cognitive_complexity=50,
            maintainability_index=75.5,
            halstead_volume=5000.0,
        )
        assert thresholds.cyclomatic_complexity == 10
        assert thresholds.cognitive_complexity == 50
        assert thresholds.maintainability_index == 75.5
        assert thresholds.halstead_volume == 5000.0

    def test_cyclomatic_complexity_constraints(self) -> None:
        """Test cyclomatic complexity must be 1-50."""
        # Valid boundaries
        MetricThresholds(cyclomatic_complexity=1)  # min
        MetricThresholds(cyclomatic_complexity=50)  # max

        # Invalid - below minimum
        with pytest.raises(ValidationError) as exc_info:
            MetricThresholds(cyclomatic_complexity=0)
        errors = exc_info.value.errors()
        assert any("greater_than_equal" in str(e) for e in errors)

        # Invalid - above maximum
        with pytest.raises(ValidationError) as exc_info:
            MetricThresholds(cyclomatic_complexity=51)
        errors = exc_info.value.errors()
        assert any("less_than_equal" in str(e) for e in errors)

    def test_cognitive_complexity_constraints(self) -> None:
        """Test cognitive complexity must be 1-100."""
        # Valid boundaries
        MetricThresholds(cognitive_complexity=1)  # min
        MetricThresholds(cognitive_complexity=100)  # max

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(cognitive_complexity=0)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(cognitive_complexity=101)

    def test_maintainability_index_constraints(self) -> None:
        """Test maintainability index must be 0-100."""
        # Valid boundaries
        MetricThresholds(maintainability_index=0)  # min
        MetricThresholds(maintainability_index=100)  # max
        MetricThresholds(maintainability_index=50.5)  # float

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(maintainability_index=-1)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(maintainability_index=101)

    def test_halstead_volume_constraints(self) -> None:
        """Test Halstead volume must be 0-100000."""
        # Valid boundaries
        MetricThresholds(halstead_volume=0)  # min
        MetricThresholds(halstead_volume=100000)  # max
        MetricThresholds(halstead_volume=5000.5)  # float

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_volume=-1)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_volume=100001)

    def test_halstead_difficulty_constraints(self) -> None:
        """Test Halstead difficulty must be 0-100."""
        # Valid boundaries
        MetricThresholds(halstead_difficulty=0)  # min
        MetricThresholds(halstead_difficulty=100)  # max
        MetricThresholds(halstead_difficulty=10.5)  # float

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_difficulty=-1)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_difficulty=101)

    def test_halstead_effort_constraints(self) -> None:
        """Test Halstead effort must be 0-1000000."""
        # Valid boundaries
        MetricThresholds(halstead_effort=0)  # min
        MetricThresholds(halstead_effort=1000000)  # max
        MetricThresholds(halstead_effort=10000.5)  # float

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_effort=-1)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_effort=1000001)

    def test_lines_of_code_constraints(self) -> None:
        """Test lines of code must be >= 0."""
        # Valid values
        MetricThresholds(lines_of_code=0)
        MetricThresholds(lines_of_code=1000)
        MetricThresholds(logical_lines_of_code=500)
        MetricThresholds(source_lines_of_code=750)
        MetricThresholds(comment_lines=250)
        MetricThresholds(blank_lines=100)

        # Invalid - negative values
        with pytest.raises(ValidationError):
            MetricThresholds(lines_of_code=-1)

        with pytest.raises(ValidationError):
            MetricThresholds(logical_lines_of_code=-1)

    def test_integer_type_coercion(self) -> None:
        """Test that integer fields coerce compatible floats."""
        # Pydantic will coerce float to int if it's a whole number
        thresholds = MetricThresholds(cyclomatic_complexity=10.0)  # type: ignore[arg-type]
        assert thresholds.cyclomatic_complexity == 10
        assert isinstance(thresholds.cyclomatic_complexity, int)

        # Same for lines of code
        thresholds = MetricThresholds(lines_of_code=100.0)  # type: ignore[arg-type]
        assert thresholds.lines_of_code == 100
        assert isinstance(thresholds.lines_of_code, int)

    def test_optional_fields(self) -> None:
        """Test that all fields are optional."""
        # Empty model should be valid
        thresholds = MetricThresholds()
        assert thresholds.cyclomatic_complexity is None
        assert thresholds.maintainability_index is None
        assert thresholds.halstead_volume is None

        # Partial model should be valid
        thresholds = MetricThresholds(cyclomatic_complexity=10)
        assert thresholds.cyclomatic_complexity == 10
        assert thresholds.cognitive_complexity is None

    def test_validate_assignment(self) -> None:
        """Test that assignment validation works."""
        thresholds = MetricThresholds()

        # Valid assignment
        thresholds.cyclomatic_complexity = 25
        assert thresholds.cyclomatic_complexity == 25

        # Invalid assignment (validate_assignment=True)
        with pytest.raises(ValidationError):
            thresholds.cyclomatic_complexity = 100

        with pytest.raises(ValidationError):
            thresholds.maintainability_index = -5

    def test_model_dump(self) -> None:
        """Test model serialization."""
        thresholds = MetricThresholds(cyclomatic_complexity=10, maintainability_index=75.5)

        data = thresholds.model_dump()
        assert data["cyclomatic_complexity"] == 10
        assert data["maintainability_index"] == 75.5
        # Optional fields should be None
        assert data["cognitive_complexity"] is None
        assert data["halstead_volume"] is None

    def test_model_dump_exclude_none(self) -> None:
        """Test model serialization excluding None values."""
        thresholds = MetricThresholds(cyclomatic_complexity=10, maintainability_index=75.5)

        data = thresholds.model_dump(exclude_none=True)
        assert data == {"cyclomatic_complexity": 10, "maintainability_index": 75.5}
        # None values should not be included
        assert "cognitive_complexity" not in data
        assert "halstead_volume" not in data

    def test_schema_generation(self) -> None:
        """Test that JSON schema includes constraints."""
        schema = MetricThresholds.model_json_schema()

        # Check that properties exist
        assert "properties" in schema
        props = schema["properties"]

        # Check cyclomatic_complexity constraints
        cc_prop = props["cyclomatic_complexity"]
        if "anyOf" in cc_prop:
            # Find the non-null schema
            for sub_schema in cc_prop["anyOf"]:
                if sub_schema.get("type") == "integer":
                    assert sub_schema.get("minimum") == 1
                    assert sub_schema.get("maximum") == 50
                    break
        else:
            assert cc_prop.get("minimum") == 1
            assert cc_prop.get("maximum") == 50

        # Check maintainability_index constraints
        mi_prop = props["maintainability_index"]
        if "anyOf" in mi_prop:
            # Find the non-null schema
            for sub_schema in mi_prop["anyOf"]:
                if sub_schema.get("type") == "number":
                    assert sub_schema.get("minimum") == 0
                    assert sub_schema.get("maximum") == 100
                    break
        else:
            assert mi_prop.get("minimum") == 0
            assert mi_prop.get("maximum") == 100

    def test_halstead_time_and_bugs_no_upper_limit(self) -> None:
        """Test that Halstead time and bugs have no upper limit."""
        # These should accept very large values
        thresholds = MetricThresholds(halstead_time=1000000, halstead_bugs=10000)
        assert thresholds.halstead_time == 1000000
        assert thresholds.halstead_bugs == 10000

        # But still must be non-negative
        with pytest.raises(ValidationError):
            MetricThresholds(halstead_time=-1)

        with pytest.raises(ValidationError):
            MetricThresholds(halstead_bugs=-1)
