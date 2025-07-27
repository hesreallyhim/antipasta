"""Help dialog widget for displaying keyboard shortcuts."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static


class HelpDialog(Container):
    """Modal dialog for displaying help information."""

    DEFAULT_CSS = """
    HelpDialog {
        align: center middle;
        width: 100%;
        height: 100%;
        background: $surface 50%;
        layer: overlay;
    }

    HelpDialog > Vertical {
        width: 60;
        height: 80%;
        max-height: 40;
        background: $panel;
        border: thick $primary;
        padding: 1;
    }

    HelpDialog .help-title {
        text-align: center;
        text-style: bold;
        background: $primary;
        color: $text;
        height: 3;
        padding: 1;
    }

    HelpDialog .help-content {
        height: 1fr;
        overflow-y: scroll;
        padding: 1;
    }

    HelpDialog .help-footer {
        height: 3;
        align: center middle;
        dock: bottom;
    }

    HelpDialog .category-header {
        text-style: bold;
        color: $primary;
        margin-top: 1;
    }

    HelpDialog .shortcut-row {
        margin-left: 2;
    }

    HelpDialog .shortcut-key {
        color: $accent;
        text-style: bold;
    }
    """

    help_text = reactive("")

    def __init__(self, help_text: str = "", **kwargs):
        """Initialize the help dialog.

        Args:
            help_text: Text to display in the dialog
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        """Compose the help dialog."""
        with Vertical():
            yield Static("⌨️  Keyboard Shortcuts", classes="help-title")
            yield Static(self.help_text, classes="help-content", id="help-content")
            with Container(classes="help-footer"):
                yield Button("Close [ESC]", variant="primary", id="close-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-help":
            self.remove()

    def on_key(self, event) -> None:
        """Handle key press."""
        if event.key == "escape":
            self.remove()

    def watch_help_text(self, help_text: str) -> None:
        """Update the help content when text changes."""
        try:
            content = self.query_one("#help-content", Static)
            content.update(self._format_help_text(help_text))
        except:
            pass

    def _format_help_text(self, text: str) -> str:
        """Format the help text with styling.

        Args:
            text: Raw help text

        Returns:
            Formatted text with markup
        """
        lines = text.split("\n")
        formatted = []

        for line in lines:
            if line.startswith("# "):
                # Main title (already in title bar)
                continue
            elif line.startswith("## "):
                # Category header
                formatted.append(f"[bold]{line[3:]}[/bold]")
            elif line.strip().startswith("🔹") or line.strip().startswith("🔸"):
                # Vim mode indicator
                formatted.append(f"[dim]{line}[/dim]")
            elif "  " in line and line.strip():
                # Shortcut row - split key and description
                parts = line.split(None, 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    desc = parts[1].strip() if len(parts) > 1 else ""
                    formatted.append(f"  [bold cyan]{key:<15}[/] {desc}")
                else:
                    formatted.append(line)
            else:
                formatted.append(line)

        return "\n".join(formatted)