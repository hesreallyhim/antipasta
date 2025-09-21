"""Terminal UI components for antipasta dashboard."""

__all__ = ["TerminalDashboard", "setup_cleanup_handlers", "disable_mouse_tracking"]

from antipasta.terminal.cleanup import disable_mouse_tracking, setup_cleanup_handlers
from antipasta.terminal.dashboard import TerminalDashboard
