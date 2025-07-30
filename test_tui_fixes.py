#!/usr/bin/env python3
"""Test script to verify TUI fixes."""

import subprocess
import time
import sys


def test_mouse_tracking():
    """Test that mouse tracking is properly disabled after TUI exits."""
    print("Testing mouse tracking cleanup...")

    # Run TUI briefly
    proc = subprocess.Popen(
        [sys.executable, "-m", "code_cop.cli.main", "tui"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Let it start
    time.sleep(1)

    # Send quit command
    proc.stdin.write(b"q")
    proc.stdin.flush()

    # Wait for exit
    proc.wait(timeout=2)

    print("TUI exited. Move your mouse - if you see output, cleanup failed.")
    print("Waiting 3 seconds...")
    time.sleep(3)
    print("Test complete. If no mouse tracking output appeared, the fix worked!")


def test_command_palette():
    """Test command palette markup fix."""
    print("\nTo test command palette:")
    print("1. Run: code-cop tui")
    print("2. Press Ctrl+P to open command palette")
    print("3. Verify no markup errors appear")
    print("4. Press Escape to close palette")
    print("5. Press q to quit")


if __name__ == "__main__":
    print("=== Code-Cop TUI Fix Verification ===\n")

    test_mouse_tracking()
    test_command_palette()