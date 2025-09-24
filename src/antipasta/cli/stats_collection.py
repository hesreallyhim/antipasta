"""Statistics collection coordination for the stats command."""

from .stats_directory import collect_directory_stats
from .stats_metrics import collect_overall_stats
from .stats_module import collect_module_stats

# Re-export the main collection functions for backward compatibility
__all__ = [
    "collect_overall_stats",
    "collect_directory_stats",
    "collect_module_stats",
]
