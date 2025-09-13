"""Terminal cleanup utilities for antipasta TUI."""

import atexit
import signal
import sys
from typing import Any


def disable_mouse_tracking() -> None:
    """Disable all mouse tracking modes."""
    try:
        # Send escape sequences to disable mouse tracking
        sys.stdout.write("\033[?1000l")  # Disable mouse tracking
        sys.stdout.write("\033[?1003l")  # Disable any motion tracking
        sys.stdout.write("\033[?1015l")  # Disable urxvt mouse mode
        sys.stdout.write("\033[?1006l")  # Disable SGR mouse mode
        sys.stdout.write("\033[?1002l")  # Disable cell motion tracking
        sys.stdout.write("\033[?1005l")  # Disable UTF-8 mouse mode
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.write("\033[?47l")  # Switch to normal screen buffer
        sys.stdout.write("\033[?1049l")  # Disable alternate screen buffer
        sys.stdout.write("\033[?1004l")  # Disable focus events
        sys.stdout.write("\033[0m")  # Reset all attributes
        sys.stdout.write("\033[2J")  # Clear screen
        sys.stdout.write("\033[H")  # Move cursor to home
        sys.stdout.flush()

        # Also try to reset via tput if available
        import subprocess

        try:
            subprocess.run(["tput", "rmcup"], capture_output=True)
            subprocess.run(["tput", "cnorm"], capture_output=True)
        except Exception:
            pass
    except Exception:
        pass


def reset_terminal() -> None:
    """Reset terminal to a clean state."""
    try:
        # Reset terminal
        sys.stdout.write("\033c")  # Reset terminal
        sys.stdout.flush()
    except Exception:
        pass


def setup_cleanup_handlers() -> None:
    """Set up cleanup handlers for proper terminal restoration."""
    # Register cleanup on normal exit
    atexit.register(disable_mouse_tracking)

    # Register cleanup on signals
    def signal_handler(signum: int, frame: Any) -> None:
        """Handle signals and clean up."""
        disable_mouse_tracking()
        sys.exit(0)

    # Handle common termination signals
    for sig in [signal.SIGINT, signal.SIGTERM]:
        try:
            signal.signal(sig, signal_handler)
        except Exception:
            pass
