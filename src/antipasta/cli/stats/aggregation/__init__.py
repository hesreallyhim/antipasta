"""Statistics collection coordination for the stats command."""

from .directory import collect_directory_stats
from .module import collect_module_stats
from ..collection.metrics import collect_overall_stats

# Re-export the main collection functions for backward compatibility
__all__ = [
    "collect_overall_stats",
    "collect_directory_stats",
    "collect_module_stats",
]
