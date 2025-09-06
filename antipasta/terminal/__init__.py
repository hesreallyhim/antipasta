"""Terminal UI components for code-cop dashboard."""

__all__ = ["TerminalDashboard", "setup_cleanup_handlers", "disable_mouse_tracking"]

from antipasta.terminal.dashboard import TerminalDashboard
from antipasta.terminal.cleanup import setup_cleanup_handlers, disable_mouse_tracking
