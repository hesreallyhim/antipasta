"""Command palette widget for quick actions and navigation."""

from typing import Any, List, Optional, Tuple

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Static


class CommandItem(Message):
    """Message sent when a command is selected."""

    def __init__(self, command: str, action: str) -> None:
        """Initialize the command item message.

        Args:
            command: The command text
            action: The action to execute
        """
        super().__init__()
        self.command = command
        self.action = action


class CommandPalette(Container):
    """Command palette for quick actions."""

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
        width: 100%;
        height: 100%;
        background: $surface 50%;
        layer: overlay;
    }

    CommandPalette > Vertical {
        width: 50%;
        max-width: 60;
        height: 50%;
        max-height: 20;
        background: $panel;
        border: thick $primary;
        padding: 1;
    }

    CommandPalette Input {
        dock: top;
        margin-bottom: 1;
        background: #1e1e1e;
    }

    CommandPalette .results {
        height: 1fr;
        overflow-y: scroll;
        background: #1e1e1e;
        padding: 0 1;
    }

    CommandPalette .result-item {
        padding: 1 2;
        margin: 0;
    }

    CommandPalette .result-item:hover {
        background: $accent 30%;
    }

    CommandPalette .selected {
        background: $accent 50%;
        text-style: bold;
    }

    CommandPalette .command-name {
        color: $text;
    }

    CommandPalette .command-description {
        color: #888888;
        margin-left: 2;
    }

    CommandPalette .no-results {
        text-align: center;
        color: #666666;
        padding: 2;
    }
    """

    search_query = reactive("")
    selected_index = reactive(0)

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the command palette."""
        super().__init__(**kwargs)
        self.commands = self._get_available_commands()
        self.filtered_commands: List[Tuple[str, str, str]] = []

    def _get_available_commands(self) -> List[Tuple[str, str, str]]:
        """Get list of available commands.

        Returns:
            List of (name, action, description) tuples
        """
        return [
            # Navigation commands
            ("Go to File", "goto_file", "Open file by name"),
            ("Go to Function", "goto_function", "Navigate to function"),
            ("Go to Line", "goto_line", "Jump to line number"),
            # View commands
            ("Show Overview", "view_overview", "Switch to overview view"),
            ("Show Heatmap", "view_heatmap", "Switch to heatmap view"),
            ("Show Trends", "view_trends", "Switch to trends view"),
            ("Show Details", "view_details", "Switch to details view"),
            ("Show Functions", "view_functions", "Switch to functions view"),
            # Analysis commands
            ("Refresh Metrics", "refresh", "Re-analyze all files"),
            ("Force Refresh", "force_refresh", "Clear cache and re-analyze"),
            ("Analyze File", "analyze_file", "Analyze specific file"),
            ("Analyze Directory", "analyze_directory", "Analyze specific directory"),
            # Filter commands
            ("Filter by Complexity", "filter_complexity", "Set complexity threshold"),
            ("Filter by Type", "filter_type", "Filter by metric type"),
            ("Clear Filters", "clear_filters", "Remove all filters"),
            ("Save Filter Preset", "save_filter", "Save current filter settings"),
            # Export commands
            ("Export View", "export_current", "Export current view"),
            ("Export All Data", "export_all", "Export all metrics data"),
            ("Export Report", "export_report", "Generate full report"),
            ("Copy Metrics", "copy_metrics", "Copy metrics to clipboard"),
            # Settings commands
            ("Toggle Vim Mode", "toggle_vim", "Enable/disable vim navigation"),
            ("Change Theme", "cycle_theme", "Cycle through themes"),
            ("Theme Menu", "theme_menu", "Open theme selector"),
            ("Save Session", "save_session", "Save current session"),
            # Help commands
            ("Show Help", "show_help", "Display keyboard shortcuts"),
            ("About", "about", "Show version and info"),
            ("Documentation", "docs", "Open documentation"),
            # File operations
            ("Open File", "open_file", "Open selected file in editor"),
            ("Open Directory", "open_directory", "Open directory in file manager"),
            ("Copy Path", "copy_path", "Copy file path to clipboard"),
            ("Reveal in Finder", "reveal_file", "Show file in file manager"),
        ]

    def compose(self) -> ComposeResult:
        """Compose the command palette."""
        with Vertical():
            yield Input(
                placeholder="Type a command...",
                id="command-input",
            )
            yield Container(
                Static("", id="results-container"),
                classes="results",
            )

    def on_mount(self) -> None:
        """Initialize when mounted."""
        # Focus the input
        self.query_one("#command-input", Input).focus()
        # Show all commands initially
        self._update_results()

    @on(Input.Changed, "#command-input")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self.search_query = event.value
        self.selected_index = 0
        self._update_results()

    @on(Input.Submitted, "#command-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if self.filtered_commands and 0 <= self.selected_index < len(self.filtered_commands):
            name, action, _ = self.filtered_commands[self.selected_index]
            self.post_message(CommandItem(name, action))
            self.remove()

    def _update_results(self) -> None:
        """Update the results display."""
        # Filter commands based on search query
        query = self.search_query.lower()
        if query:
            self.filtered_commands = [
                (name, action, desc)
                for name, action, desc in self.commands
                if query in name.lower() or query in desc.lower()
            ]
        else:
            self.filtered_commands = self.commands

        # Build results display
        results_container = self.query_one("#results-container", Static)

        if not self.filtered_commands:
            results_container.update(
                "[dim]No commands found[/dim]",
            )
            return

        # Create result items
        results = []
        for i, (name, _, desc) in enumerate(self.filtered_commands):
            is_selected = i == self.selected_index
            item_class = "selected" if is_selected else ""
            prefix = "▶ " if is_selected else "  "

            results.append(f"[{item_class}]{prefix}[bold]{name}[/bold] [dim]{desc}[/dim][/]")

        results_container.update("\n".join(results))

    def on_key(self, event: Any) -> None:
        """Handle key events."""
        if event.key == "escape":
            self.remove()
        elif event.key == "up" or (event.key == "k" and event.ctrl):
            self._move_selection(-1)
        elif event.key == "down" or (event.key == "j" and event.ctrl):
            self._move_selection(1)
        elif event.key == "enter":
            # Trigger submission
            if self.filtered_commands and 0 <= self.selected_index < len(self.filtered_commands):
                name, action, _ = self.filtered_commands[self.selected_index]
                self.post_message(CommandItem(name, action))
                self.remove()

    def _move_selection(self, delta: int) -> None:
        """Move the selection up or down.

        Args:
            delta: Direction to move (-1 for up, 1 for down)
        """
        if self.filtered_commands:
            new_index = self.selected_index + delta
            new_index = max(0, min(new_index, len(self.filtered_commands) - 1))
            if new_index != self.selected_index:
                self.selected_index = new_index
                self._update_results()

    def _fuzzy_match(self, query: str, text: str) -> bool:
        """Perform fuzzy matching.

        Args:
            query: Search query
            text: Text to match against

        Returns:
            True if query fuzzy matches text
        """
        query = query.lower()
        text = text.lower()

        # Simple substring match for now
        # TODO: Implement proper fuzzy matching algorithm
        return query in text
