"""Loading screen widget for terminal dashboard."""

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.widgets import Static


class LoadingScreen(Static):
    """Loading screen widget shown during initial analysis."""

    DEFAULT_CSS = """
    LoadingScreen {
        width: 100%;
        height: 100%;
        background: $surface;
        layer: overlay;
    }

    LoadingScreen Center {
        width: 100%;
        height: 100%;
    }

    LoadingScreen .loading-content {
        text-align: center;
        padding: 2;
        border: thick $primary;
        background: $panel;
    }

    LoadingScreen .loading-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    LoadingScreen .loading-message {
        color: $text-muted;
    }

    LoadingScreen .loading-spinner {
        color: $accent;
        margin-top: 1;
    }
    """

    def __init__(self, message: str = "Analyzing project...", **kwargs):
        """Initialize loading screen.

        Args:
            message: Loading message to display
        """
        super().__init__(**kwargs)
        self.message = message
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_index = 0

    def compose(self) -> ComposeResult:
        """Create loading screen layout."""
        logo = """╔═══════════════════════════════╗
║     ____ ___  ____  _____     ║
║    / ___/ _ |  _ | ____|    ║
║   | |  | | | | | | |  _|      ║
║   | |__| |_| | |_| | |___     ║
║    ________/|____/|_____|    ║
║            COP                ║
╚═══════════════════════════════╝"""

        with Middle():
            with Center():
                with Static(classes="loading-content"):
                    yield Static(logo, classes="loading-title")
                    yield Static(self._spinner_frames[0], classes="loading-spinner", id="loading-spinner")
                    yield Static(self.message, classes="loading-message", id="loading-message")

    def on_mount(self) -> None:
        """Start spinner animation when mounted."""
        self.set_interval(0.1, self._update_spinner)

    def _update_spinner(self) -> None:
        """Update spinner animation."""
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        spinner = self.query_one("#loading-spinner", Static)
        spinner.update(self._spinner_frames[self._spinner_index])

    def update_message(self, message: str) -> None:
        """Update the loading message."""
        self.message = message
        msg_widget = self.query_one("#loading-message", Static)
        msg_widget.update(message)
