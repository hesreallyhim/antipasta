#!/usr/bin/env python3
"""Emergency terminal reset script."""

import sys
import os
import termios
import tty


def reset_terminal():
    """Reset terminal to a clean state."""
    try:
        # Reset all terminal modes
        sys.stdout.write("\033c")  # Reset terminal
        sys.stdout.write("\033[?1000l")  # Disable mouse tracking
        sys.stdout.write("\033[?1003l")  # Disable any motion tracking
        sys.stdout.write("\033[?1015l")  # Disable urxvt mouse mode
        sys.stdout.write("\033[?1006l")  # Disable SGR mouse mode
        sys.stdout.write("\033[?1002l")  # Disable cell motion tracking
        sys.stdout.write("\033[?1005l")  # Disable UTF-8 mouse mode
        sys.stdout.write("\033[?25h")    # Show cursor
        sys.stdout.write("\033[?47l")    # Switch to normal screen buffer
        sys.stdout.write("\033[?1049l")  # Disable alternate screen buffer
        sys.stdout.write("\033[0m")      # Reset colors
        sys.stdout.write("\033[?7h")     # Enable line wrap
        sys.stdout.write("\033[?1h")     # Normal cursor keys
        sys.stdout.write("\033[?1004l")  # Disable focus events
        sys.stdout.flush()

        # Reset terminal attributes
        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
            if hasattr(termios, 'tcgetattr'):
                try:
                    # Get current attributes
                    old_attrs = termios.tcgetattr(fd)
                    # Reset to sane defaults
                    tty.setcbreak(fd)
                    termios.tcsetattr(fd, termios.TCSANOW, old_attrs)
                except Exception:
                    pass

        print("Terminal reset complete.")

    except Exception as e:
        print(f"Error resetting terminal: {e}")


if __name__ == "__main__":
    reset_terminal()