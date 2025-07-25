"""Configuration models and loading for code-cop."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from code_cop.core.metrics import MetricType


class ComparisonOperator(str, Enum):
    """Valid comparison operators for metric thresholds."""

    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "=="
    NE = "!="


class MetricConfig(BaseModel):
    """Configuration for a single metric."""

    type: MetricType
    threshold: float
    comparison: ComparisonOperator = ComparisonOperator.LE
    enabled: bool = True

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Ensure threshold is a positive number."""
        if v < 0:
            raise ValueError("Threshold must be non-negative")
        return v


class LanguageConfig(BaseModel):
    """Configuration for a specific language."""

    name: str
    extensions: list[str] = Field(default_factory=list)
    metrics: list[MetricConfig]

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, v: list[str]) -> list[str]:
        """Ensure extensions start with a dot."""
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"Extension must start with dot: {ext}")
        return v


class DefaultsConfig(BaseModel):
    """Default configuration values."""

    max_cyclomatic_complexity: float = 10
    min_maintainability_index: float = 50
    max_halstead_volume: float = 1000
    max_halstead_difficulty: float = 10
    max_halstead_effort: float = 10000
    max_cognitive_complexity: float = 15

    @model_validator(mode="after")
    def validate_defaults(self) -> DefaultsConfig:
        """Ensure all values are positive."""
        for field_name, value in self.model_dump().items():
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        return self


class CodeCopConfig(BaseModel):
    """Main configuration model."""

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    languages: list[LanguageConfig] = Field(default_factory=list)
    ignore_patterns: list[str] = Field(default_factory=list)
    use_gitignore: bool = Field(default=True)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> CodeCopConfig:
        """Load configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def generate_default(cls) -> CodeCopConfig:
        """Generate default configuration with sensible values."""
        return cls(
            defaults=DefaultsConfig(),
            languages=[
                LanguageConfig(
                    name="python",
                    extensions=[".py"],
                    metrics=[
                        MetricConfig(
                            type=MetricType.CYCLOMATIC_COMPLEXITY,
                            threshold=10,
                            comparison=ComparisonOperator.LE,
                        ),
                        MetricConfig(
                            type=MetricType.MAINTAINABILITY_INDEX,
                            threshold=50,
                            comparison=ComparisonOperator.GE,
                        ),
                        MetricConfig(
                            type=MetricType.HALSTEAD_VOLUME,
                            threshold=1000,
                            comparison=ComparisonOperator.LE,
                        ),
                        MetricConfig(
                            type=MetricType.HALSTEAD_DIFFICULTY,
                            threshold=10,
                            comparison=ComparisonOperator.LE,
                        ),
                        MetricConfig(
                            type=MetricType.HALSTEAD_EFFORT,
                            threshold=10000,
                            comparison=ComparisonOperator.LE,
                        ),
                        MetricConfig(
                            type=MetricType.COGNITIVE_COMPLEXITY,
                            threshold=15,
                            comparison=ComparisonOperator.LE,
                            enabled=False,  # Disabled by default since it requires complexipy
                        ),
                    ],
                ),
            ],
            ignore_patterns=["**/test_*.py", "**/*_test.py", "**/tests/**"],
        )

    def to_yaml(self, path: Union[str, Path]) -> None:
        """Save configuration to YAML file."""
        path = Path(path)
        # Convert to dict and ensure enums are serialized as strings
        data = self.model_dump(exclude_none=True, mode="json")
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get_language_config(self, language: str) -> Optional[LanguageConfig]:
        """Get configuration for a specific language."""
        for lang_config in self.languages:
            if lang_config.name.lower() == language.lower():
                return lang_config
        return None