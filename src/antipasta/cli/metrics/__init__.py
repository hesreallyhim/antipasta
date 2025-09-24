"""Metrics CLI module for antipasta."""

# Re-export main metrics command
from .metrics import metrics

# Re-export utility functions for external use
from .metrics_utils_analysis import (
    determine_files_to_analyze,
    execute_analysis,
    exit_with_appropriate_code,
)
from .metrics_utils_collection import collect_files
from .metrics_utils_config import load_configuration, prepare_configuration
from .metrics_utils_output import output_results, print_results
from .metrics_utils_override import (
    apply_overrides_to_configuration,
    create_and_configure_override,
    display_override_status_messages,
    handle_threshold_parsing_error,
)

__all__ = [
    # Main command
    "metrics",
    # Analysis functions
    "determine_files_to_analyze",
    "execute_analysis",
    "exit_with_appropriate_code",
    # Collection functions
    "collect_files",
    # Config functions
    "load_configuration",
    "prepare_configuration",
    # Output functions
    "output_results",
    "print_results",
    # Override functions
    "apply_overrides_to_configuration",
    "create_and_configure_override",
    "display_override_status_messages",
    "handle_threshold_parsing_error",
]
