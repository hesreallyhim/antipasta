"""View configuration command - compatibility wrapper.

This module provides backward compatibility by re-exporting
the view command from the refactored module structure.
"""

from antipasta.cli.config.config_view.main import view

__all__ = ["view"]