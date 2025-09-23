"""Pydantic models for metric thresholds with built-in validation.

This module provides constrained type definitions for all metric types,
ensuring consistent validation across config files and CLI overrides.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Constrained type definitions for each metric
# These serve as the single source of truth for validation rules

CyclomaticComplexity = Annotated[
    int, Field(ge=1, le=50, description="Cyclomatic complexity (1-50)")
]

CognitiveComplexity = Annotated[
    int, Field(ge=1, le=100, description="Cognitive complexity (1-100)")
]

MaintainabilityIndex = Annotated[
    float, Field(ge=0, le=100, description="Maintainability index (0-100)")
]

HalsteadVolume = Annotated[float, Field(ge=0, le=100000, description="Halstead volume (0-100000)")]

HalsteadDifficulty = Annotated[
    float, Field(ge=0, le=100, description="Halstead difficulty (0-100)")
]

HalsteadEffort = Annotated[
    float, Field(ge=0, le=1000000, description="Halstead effort (0-1000000)")
]

HalsteadTime = Annotated[float, Field(ge=0, description="Halstead time in seconds")]

HalsteadBugs = Annotated[float, Field(ge=0, description="Estimated bugs")]

LinesOfCode = Annotated[int, Field(ge=0, description="Lines of code")]


class MetricThresholds(BaseModel):
    """Model for validating individual metric thresholds.

    This model is used both for config validation and CLI overrides.
    All fields are optional to support partial updates.
    """

    cyclomatic_complexity: CyclomaticComplexity | None = None
    cognitive_complexity: CognitiveComplexity | None = None
    maintainability_index: MaintainabilityIndex | None = None
    halstead_volume: HalsteadVolume | None = None
    halstead_difficulty: HalsteadDifficulty | None = None
    halstead_effort: HalsteadEffort | None = None
    halstead_time: HalsteadTime | None = None
    halstead_bugs: HalsteadBugs | None = None
    lines_of_code: LinesOfCode | None = None
    logical_lines_of_code: LinesOfCode | None = None
    source_lines_of_code: LinesOfCode | None = None
    comment_lines: LinesOfCode | None = None
    blank_lines: LinesOfCode | None = None

    model_config = ConfigDict(
        # Enable validation on assignment for dynamic updates
        validate_assignment=True,
        # Use enum values for cleaner error messages
        use_enum_values=True,
    )
