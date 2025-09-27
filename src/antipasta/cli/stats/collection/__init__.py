"""Collection utilities for stats command."""

from .analysis import (
    analyze_and_display_file_breakdown,
    analyze_files_with_validation,
)
from .file_collection import (
    collect_and_validate_files,
    collect_files_from_patterns,
    get_default_patterns,
    get_metrics_to_include,
    parse_metrics,
    validate_analyzable_files,
    validate_files_found,
)
from .metrics import (
    add_metric_statistics_to_result,
    collect_overall_stats,
)

__all__ = [
    "analyze_and_display_file_breakdown",
    "analyze_files_with_validation",
    "collect_and_validate_files",
    "collect_files_from_patterns",
    "get_default_patterns",
    "get_metrics_to_include",
    "parse_metrics",
    "validate_analyzable_files",
    "validate_files_found",
    "add_metric_statistics_to_result",
    "collect_overall_stats",
]
