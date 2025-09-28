# Validation Enhancement Plan: Unifying Config and Override Validation with Pydantic

## Current Situation

### Config File Validation (Strong)
Configuration files use Pydantic models with basic validation:

```python
# In DefaultsConfig (config.py)
class DefaultsConfig(BaseModel):
    max_cyclomatic_complexity: float = 10
    min_maintainability_index: float = 50
    max_halstead_volume: float = 1000
    # ... etc

    @model_validator(mode="after")
    def validate_defaults(self) -> DefaultsConfig:
        """Ensure all values are positive."""
        for field_name, value in self.model_dump().items():
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
```

**Current Config Validation:**
- ✅ Type safety (enforced by Pydantic)
- ✅ Non-negative value checks
- ❌ Missing: Metric-specific ranges (e.g., maintainability_index should be 0-100)
- ❌ Missing: Upper bounds for practical limits

### CLI Override Validation (Basic)
Override flags have minimal validation:

```python
# In ConfigOverride.set_threshold() (config_override.py)
def set_threshold(self, metric_type: str, value: float) -> None:
    # Check valid metric type
    try:
        MetricType(metric_type)
    except ValueError:
        raise ValueError(f"Invalid metric type: {metric_type}")

    # Basic range check
    if value < 0:
        raise ValueError(f"Threshold must be non-negative: {value}")

    self.threshold_overrides[metric_type] = value
```

**Current Override Validation:**
- ✅ Valid metric type check
- ✅ Non-negative value check
- ❌ Missing: Upper bound validation
- ❌ Missing: Metric-specific ranges
- ❌ Missing: Type-specific validation (int vs float)

### The Problem
Users can bypass proper validation by using CLI flags:
```bash
# This would fail in config (if we had proper validation):
# min_maintainability_index: 150  # Should be 0-100

# But this currently works via CLI:
antipasta metrics --threshold maintainability_index=150  # No upper bound check!
```

## Proposed Solution: Leverage Pydantic's Field Constraints

Instead of building custom validation infrastructure, we can leverage Pydantic's built-in `Field` constraints to:
- Define min/max ranges declaratively
- Get automatic validation
- Generate JSON schemas with constraints
- Provide clear error messages
- Maintain a single source of truth

## Detailed Implementation Plan

### Phase 1: Create Constrained Type Definitions

Create `src/antipasta/core/metric_models.py`:

```python
"""Pydantic models for metric thresholds with built-in validation."""

from pydantic import BaseModel, Field
from typing import Annotated, Optional

# Define reusable type aliases with constraints
# These serve as our single source of truth for validation rules
CyclomaticComplexity = Annotated[
    int,
    Field(ge=1, le=50, description="Cyclomatic complexity (1-50)")
]

CognitiveComplexity = Annotated[
    int,
    Field(ge=1, le=100, description="Cognitive complexity (1-100)")
]

MaintainabilityIndex = Annotated[
    float,
    Field(ge=0, le=100, description="Maintainability index (0-100)")
]

HalsteadVolume = Annotated[
    float,
    Field(ge=0, le=100000, description="Halstead volume (0-100000)")
]

HalsteadDifficulty = Annotated[
    float,
    Field(ge=0, le=100, description="Halstead difficulty (0-100)")
]

HalsteadEffort = Annotated[
    float,
    Field(ge=0, le=1000000, description="Halstead effort (0-1000000)")
]

HalsteadTime = Annotated[
    float,
    Field(ge=0, description="Halstead time in seconds")
]

HalsteadBugs = Annotated[
    float,
    Field(ge=0, description="Estimated bugs")
]

LinesOfCode = Annotated[
    int,
    Field(ge=0, description="Lines of code")
]


class MetricThresholds(BaseModel):
    """Model for validating individual metric thresholds.

    This model is used both for config validation and CLI overrides.
    All fields are optional to support partial updates.
    """

    cyclomatic_complexity: Optional[CyclomaticComplexity] = None
    cognitive_complexity: Optional[CognitiveComplexity] = None
    maintainability_index: Optional[MaintainabilityIndex] = None
    halstead_volume: Optional[HalsteadVolume] = None
    halstead_difficulty: Optional[HalsteadDifficulty] = None
    halstead_effort: Optional[HalsteadEffort] = None
    halstead_time: Optional[HalsteadTime] = None
    halstead_bugs: Optional[HalsteadBugs] = None
    lines_of_code: Optional[LinesOfCode] = None
    logical_lines_of_code: Optional[LinesOfCode] = None
    source_lines_of_code: Optional[LinesOfCode] = None
    comment_lines: Optional[LinesOfCode] = None
    blank_lines: Optional[LinesOfCode] = None

    class Config:
        # Enable validation on assignment for dynamic updates
        validate_assignment = True
        # Use enum values for cleaner error messages
        use_enum_values = True
```

### Phase 2: Update DefaultsConfig to Use Constrained Types

Modify `src/antipasta/core/config.py`:

```python
from pydantic import BaseModel, Field
from antipasta.core.metric_models import (
    CyclomaticComplexity,
    CognitiveComplexity,
    MaintainabilityIndex,
    HalsteadVolume,
    HalsteadDifficulty,
    HalsteadEffort
)

class DefaultsConfig(BaseModel):
    """Default configuration values with automatic validation.

    All validation is handled by Pydantic Field constraints,
    no custom validators needed.
    """

    # Reuse the constrained types - validation is automatic!
    max_cyclomatic_complexity: CyclomaticComplexity = 10
    max_cognitive_complexity: CognitiveComplexity = 15
    min_maintainability_index: MaintainabilityIndex = 50
    max_halstead_volume: HalsteadVolume = 1000
    max_halstead_difficulty: HalsteadDifficulty = 10
    max_halstead_effort: HalsteadEffort = 10000

    # Remove the custom validator - Pydantic handles it all!
    # The @model_validator is no longer needed
```

### Phase 3: Update ConfigOverride to Use Pydantic Validation

Modify `src/antipasta/core/config_override.py`:

```python
from dataclasses import dataclass, field
from typing import Any
from pydantic import ValidationError

from antipasta.core.metric_models import MetricThresholds
from antipasta.core.metrics import MetricType


@dataclass
class ConfigOverride:
    """Runtime configuration overrides with Pydantic validation."""

    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    disable_gitignore: bool = False
    force_analyze: bool = False

    # Use Pydantic model internally for validation
    _threshold_model: MetricThresholds = field(
        default_factory=MetricThresholds,
        init=False,
        repr=False
    )

    @property
    def threshold_overrides(self) -> dict[str, float]:
        """Get threshold overrides as a dict (for compatibility)."""
        return {
            k: v for k, v in self._threshold_model.model_dump().items()
            if v is not None
        }

    def set_threshold(self, metric_type: str, value: float) -> None:
        """Set a metric threshold override with Pydantic validation.

        Args:
            metric_type: Type of metric (must be valid MetricType value)
            value: Threshold value (auto-validated by Pydantic)

        Raises:
            ValueError: If metric type invalid or value out of range
        """
        # First check if metric type is valid
        try:
            MetricType(metric_type)
        except ValueError:
            valid_metrics = [m.value for m in MetricType]
            raise ValueError(
                f"Invalid metric type: '{metric_type}'. "
                f"Valid types: {', '.join(sorted(valid_metrics))}"
            )

        # Use Pydantic for validation
        try:
            # This triggers Pydantic validation automatically
            setattr(self._threshold_model, metric_type, value)
        except ValidationError as e:
            # Convert Pydantic error to user-friendly message
            raise ValueError(self._format_validation_error(metric_type, e))

    def _format_validation_error(self, metric_type: str, error: ValidationError) -> str:
        """Convert Pydantic ValidationError to user-friendly message."""
        for err in error.errors():
            if metric_type in str(err.get('loc', ())):
                # Extract constraint information from error
                err_type = err.get('type', '')
                ctx = err.get('ctx', {})

                if 'greater_than_equal' in err_type:
                    return f"{metric_type} must be >= {ctx.get('ge', 0)}"
                elif 'less_than_equal' in err_type:
                    return f"{metric_type} must be <= {ctx.get('le', 'max')}"
                elif 'greater_than' in err_type:
                    return f"{metric_type} must be > {ctx.get('gt', 0)}"
                elif 'less_than' in err_type:
                    return f"{metric_type} must be < {ctx.get('lt', 'max')}"
                elif err_type == 'int_type':
                    return f"{metric_type} must be an integer, got {value}"
                elif err_type == 'int_parsing':
                    return f"{metric_type} must be a valid integer"
                else:
                    return f"Invalid value for {metric_type}: {err.get('msg', 'validation failed')}"

        # Fallback
        return f"Invalid value for {metric_type}"

    def parse_threshold_string(self, threshold_str: str) -> None:
        """Parse a threshold override string in format 'metric_type=value'.

        Args:
            threshold_str: String like 'cyclomatic_complexity=15'

        Raises:
            ValueError: If string format is invalid or validation fails
        """
        if '=' not in threshold_str:
            raise ValueError(
                f"Invalid threshold format: '{threshold_str}'. "
                f"Expected format: 'metric_type=value'"
            )

        metric_type, value_str = threshold_str.split('=', 1)
        metric_type = metric_type.strip()

        try:
            value = float(value_str.strip())
        except ValueError:
            raise ValueError(
                f"Invalid threshold value: '{value_str}'. Must be a number"
            )

        # This will use Pydantic validation
        self.set_threshold(metric_type, value)
```

### Phase 4: Extract Help Text from Pydantic Schema

Create `src/antipasta/cli/validation_utils.py`:

```python
"""Utilities for extracting validation info from Pydantic schemas."""

from typing import Optional, Tuple
from antipasta.core.metric_models import MetricThresholds


def get_metric_constraints(metric_type: str) -> Tuple[Optional[float], Optional[float]]:
    """Get min/max constraints for a metric from Pydantic schema.

    Returns:
        Tuple of (min_value, max_value), either can be None
    """
    schema = MetricThresholds.model_json_schema()
    properties = schema.get('properties', {})

    if metric_type in properties:
        prop_schema = properties[metric_type]

        # Handle anyOf schemas (used for Optional fields)
        if 'anyOf' in prop_schema:
            # Find the non-null schema
            for sub_schema in prop_schema['anyOf']:
                if sub_schema.get('type') != 'null':
                    prop_schema = sub_schema
                    break

        min_val = prop_schema.get('minimum')
        max_val = prop_schema.get('maximum')

        # Also check for exclusive bounds
        if min_val is None:
            min_val = prop_schema.get('exclusiveMinimum')
        if max_val is None:
            max_val = prop_schema.get('exclusiveMaximum')

        return (min_val, max_val)

    return (None, None)


def get_metric_help_text(metric_type: str) -> str:
    """Get help text for a metric including its valid range."""
    schema = MetricThresholds.model_json_schema()
    properties = schema.get('properties', {})

    if metric_type in properties:
        prop_schema = properties[metric_type]

        # Handle anyOf schemas
        if 'anyOf' in prop_schema:
            for sub_schema in prop_schema['anyOf']:
                if sub_schema.get('type') != 'null':
                    prop_schema = sub_schema
                    break

        description = prop_schema.get('description', '')

        # Extract range from schema
        min_val, max_val = get_metric_constraints(metric_type)

        range_parts = []
        if min_val is not None:
            range_parts.append(f">= {min_val}")
        if max_val is not None:
            range_parts.append(f"<= {max_val}")

        if range_parts:
            range_text = " and ".join(range_parts)
            return f"{description} (valid: {range_text})"

        return description if description else f"Metric: {metric_type}"

    return f"Metric: {metric_type}"


def format_validation_error_for_cli(e: Exception) -> str:
    """Format validation errors for CLI display."""
    error_msg = str(e)

    # Make error messages more user-friendly
    if "Invalid metric type" in error_msg:
        # The error already lists valid types
        return error_msg
    elif "must be" in error_msg:
        # Range errors are already clear
        return error_msg
    else:
        return f"Validation error: {error_msg}"
```

### Phase 5: Update Config Generation to Use Constraints

Modify `src/antipasta/cli/config_generate.py`:

```python
from antipasta.cli.validation_utils import get_metric_constraints
from antipasta.core.metric_models import MetricThresholds
from pydantic import ValidationError


def validate_with_pydantic(metric_type: str, value: str) -> float:
    """Validate a metric value using Pydantic model."""
    try:
        num = float(value)
        # Use Pydantic validation
        MetricThresholds(**{metric_type: num})
        return num
    except ValidationError as e:
        # Extract first error message
        if e.errors():
            err = e.errors()[0]
            err_type = err.get('type', '')
            ctx = err.get('ctx', {})

            if 'greater_than_equal' in err_type:
                raise click.BadParameter(f"Value must be >= {ctx.get('ge', 0)}")
            elif 'less_than_equal' in err_type:
                raise click.BadParameter(f"Value must be <= {ctx.get('le', 'max')}")
            elif err_type == 'int_type':
                raise click.BadParameter(f"Must be an integer")

        raise click.BadParameter(str(e))
    except ValueError:
        raise click.BadParameter("Must be a valid number")


# Update prompts to show actual constraints
max_cyclomatic = prompt_with_validation(
    "Maximum cyclomatic complexity per function",
    default=10,
    validator=lambda v: validate_with_pydantic('cyclomatic_complexity', v),
    help_text=get_metric_help_text('cyclomatic_complexity')
)
```

### Phase 6: Update CLI Error Handling

Modify `src/antipasta/cli/metrics.py`:

```python
from antipasta.cli.validation_utils import format_validation_error_for_cli

# In the metrics command
for threshold in thresholds:
    try:
        overrides.parse_threshold_string(threshold)
    except ValueError as e:
        click.echo(f"❌ Error: {format_validation_error_for_cli(e)}", err=True)

        # If it's a range error, we could show the valid range
        if '=' in threshold:
            metric_type = threshold.split('=')[0].strip()
            help_text = get_metric_help_text(metric_type)
            if help_text:
                click.echo(f"   ℹ️  {help_text}", err=True)

        ctx.exit(1)
```

### Phase 7: Comprehensive Tests

Create `tests/unit/test_metric_models.py`:

```python
"""Test metric models and Pydantic validation."""

import pytest
from pydantic import ValidationError

from antipasta.core.metric_models import MetricThresholds


class TestMetricThresholds:
    """Test metric threshold validation via Pydantic."""

    def test_valid_thresholds(self):
        """Test valid threshold values."""
        thresholds = MetricThresholds(
            cyclomatic_complexity=10,
            cognitive_complexity=50,
            maintainability_index=75.5,
            halstead_volume=5000.0
        )
        assert thresholds.cyclomatic_complexity == 10
        assert thresholds.cognitive_complexity == 50
        assert thresholds.maintainability_index == 75.5
        assert thresholds.halstead_volume == 5000.0

    def test_cyclomatic_complexity_constraints(self):
        """Test cyclomatic complexity must be 1-50."""
        # Valid boundaries
        MetricThresholds(cyclomatic_complexity=1)   # min
        MetricThresholds(cyclomatic_complexity=50)  # max

        # Invalid - below minimum
        with pytest.raises(ValidationError) as exc_info:
            MetricThresholds(cyclomatic_complexity=0)
        errors = exc_info.value.errors()
        assert any('greater_than_equal' in str(e) for e in errors)

        # Invalid - above maximum
        with pytest.raises(ValidationError) as exc_info:
            MetricThresholds(cyclomatic_complexity=51)
        errors = exc_info.value.errors()
        assert any('less_than_equal' in str(e) for e in errors)

    def test_maintainability_index_constraints(self):
        """Test maintainability index must be 0-100."""
        # Valid boundaries
        MetricThresholds(maintainability_index=0)    # min
        MetricThresholds(maintainability_index=100)  # max
        MetricThresholds(maintainability_index=50.5) # float

        # Invalid - below minimum
        with pytest.raises(ValidationError):
            MetricThresholds(maintainability_index=-1)

        # Invalid - above maximum
        with pytest.raises(ValidationError):
            MetricThresholds(maintainability_index=101)

    def test_integer_type_enforcement(self):
        """Test that integer fields enforce type."""
        # Pydantic will coerce float to int if possible
        thresholds = MetricThresholds(cyclomatic_complexity=10.0)
        assert thresholds.cyclomatic_complexity == 10
        assert isinstance(thresholds.cyclomatic_complexity, int)

        # But will reject non-integer floats based on config
        # (This behavior depends on Pydantic config)

    def test_optional_fields(self):
        """Test that all fields are optional."""
        # Empty model should be valid
        thresholds = MetricThresholds()
        assert thresholds.cyclomatic_complexity is None
        assert thresholds.maintainability_index is None

        # Partial model should be valid
        thresholds = MetricThresholds(cyclomatic_complexity=10)
        assert thresholds.cyclomatic_complexity == 10
        assert thresholds.cognitive_complexity is None

    def test_validate_assignment(self):
        """Test that assignment validation works."""
        thresholds = MetricThresholds()

        # Valid assignment
        thresholds.cyclomatic_complexity = 25
        assert thresholds.cyclomatic_complexity == 25

        # Invalid assignment (if validate_assignment=True)
        with pytest.raises(ValidationError):
            thresholds.cyclomatic_complexity = 100

    def test_schema_generation(self):
        """Test that JSON schema includes constraints."""
        schema = MetricThresholds.model_json_schema()

        # Navigate to cyclomatic_complexity (handling anyOf for Optional)
        cc_prop = schema['properties']['cyclomatic_complexity']
        if 'anyOf' in cc_prop:
            # Find the non-null schema
            for sub_schema in cc_prop['anyOf']:
                if sub_schema.get('type') == 'integer':
                    cc_schema = sub_schema
                    break
        else:
            cc_schema = cc_prop

        assert cc_schema.get('minimum') == 1
        assert cc_schema.get('maximum') == 50
        assert cc_schema.get('type') == 'integer'
```

Update `tests/unit/test_config_override.py`:

```python
def test_set_threshold_with_pydantic_validation(self):
    """Test that set_threshold uses Pydantic validation."""
    override = ConfigOverride()

    # Valid values
    override.set_threshold("cyclomatic_complexity", 10)
    assert override.threshold_overrides["cyclomatic_complexity"] == 10

    override.set_threshold("maintainability_index", 75.5)
    assert override.threshold_overrides["maintainability_index"] == 75.5

    # Invalid - out of range
    with pytest.raises(ValueError, match="must be <= 100"):
        override.set_threshold("maintainability_index", 150)

    with pytest.raises(ValueError, match="must be >= 1"):
        override.set_threshold("cyclomatic_complexity", 0)

    # Invalid - wrong type (if strict)
    # Note: Pydantic might coerce this, depends on config
```

## Benefits of the Pydantic Approach

1. **Minimal Code**: Leverage Pydantic's robust validation instead of custom code
2. **Single Source of Truth**: Constraints defined once in type annotations
3. **Automatic JSON Schema**: Constraints included in generated schemas
4. **Clear Error Messages**: Pydantic provides detailed validation errors
5. **Type Safety**: Proper type hints and validation
6. **IDE Support**: Better autocomplete and inline documentation
7. **Well-Tested**: Using battle-tested Pydantic validation logic
8. **Maintainable**: Changes to constraints only need updating in one place
9. **Composable**: Constrained types can be reused across models
10. **Documentation**: Constraints are self-documenting via Field descriptions

## Migration Strategy

1. **Phase 1**: Create `metric_models.py` with constrained types ✅
2. **Phase 2**: Update `DefaultsConfig` to use constrained types ✅
3. **Phase 3**: Modify `ConfigOverride` to use Pydantic internally ✅
4. **Phase 4**: Create utilities to extract schema information ✅
5. **Phase 5**: Update config generation to show correct ranges ✅
6. **Phase 6**: Enhance CLI error messages ✅
7. **Phase 7**: Add comprehensive tests ✅

Each phase can be tested independently, minimizing risk.

## Success Criteria

- [x] All metric values validated consistently (config and CLI)
- [x] Validation rules defined in single location
- [x] Clear error messages showing valid ranges
- [x] No duplicate validation code
- [x] Existing tests pass (with updates for new constraints)
- [x] JSON schema includes all constraints
- [x] Config generation shows accurate ranges

## Estimated Effort

- **Code Changes**: ~200 lines added, ~150 lines removed (net simpler)
- **Test Updates**: ~100 lines of test updates
- **Risk**: Low - leveraging well-tested Pydantic functionality
- **Timeline**: 2-3 hours of implementation + testing

This approach is significantly simpler than custom validation and provides better functionality with less code.