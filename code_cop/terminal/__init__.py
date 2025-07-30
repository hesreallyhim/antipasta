"""Terminal UI components for code-cop dashboard."""

__all__ = ["TerminalDashboard", "setup_cleanup_handlers", "disable_mouse_tracking"]

from code_cop.terminal.dashboard import TerminalDashboard
from code_cop.terminal.cleanup import setup_cleanup_handlers, disable_mouse_tracking
