"""Heatmap visualization widget for terminal dashboard."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class DirectorySelected(Message):
    """Message sent when a directory is selected in the heatmap."""

    def __init__(self, directory_path: str, stats: dict[str, Any]) -> None:
        """Initialize the message.

        Args:
            directory_path: Path to the selected directory
            stats: Directory statistics
        """
        super().__init__()
        self.directory_path = directory_path
        self.stats = stats


class HeatmapWidget(Widget):
    """Terminal-based heatmap visualization for complexity."""

    COMPONENT_CLASSES = {"heatmap-widget"}

    heatmap_data: reactive[list[dict[str, Any]]] = reactive([])
    selected_index: reactive[int] = reactive(-1)

    def __init__(self, heatmap_data: list[dict[str, Any]] | None = None, **kwargs: Any) -> None:
        """Initialize the heatmap widget.

        Args:
            heatmap_data: Heatmap data from DashboardDataBridge
        """
        super().__init__(**kwargs)
        if heatmap_data:
            self.heatmap_data = heatmap_data
        self._heatmap_items: list[Widget] = []

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Container(classes="heatmap-container"):
            yield Static("🔥 Complexity Heatmap", classes="heatmap-title")
            yield Static("Click on a directory to explore", classes="heatmap-hint")

            with ScrollableContainer(classes="heatmap-scroll"):
                # Initial empty state
                yield Static("No data to display", id="heatmap-empty", classes="no-data")

    def on_mount(self) -> None:
        """Initialize the heatmap when mounted."""
        if self.heatmap_data:
            self._render_heatmap()

    def watch_heatmap_data(
        self, old_data: list[dict[str, Any]], new_data: list[dict[str, Any]]
    ) -> None:
        """React to heatmap data changes."""
        self._render_heatmap()

    def _render_heatmap(self) -> None:
        """Render the heatmap visualization."""
        if not self.heatmap_data:
            return

        # Get the scrollable container
        scroll_container = self.query_one(".heatmap-scroll", ScrollableContainer)

        # Clear existing content
        scroll_container.remove_children()
        self._heatmap_items.clear()

        # Calculate max complexity for scaling
        max_complexity = (
            max(item["avg_complexity"] for item in self.heatmap_data) if self.heatmap_data else 1
        )

        # Create heatmap items
        for i, item in enumerate(self.heatmap_data):
            heatmap_item = self._create_heatmap_item(item, max_complexity, i)
            self._heatmap_items.append(heatmap_item)
            scroll_container.mount(heatmap_item)

    def _create_heatmap_item(
        self, item: dict[str, Any], max_complexity: float, index: int
    ) -> Widget:
        """Create a single heatmap item."""
        path = item["path"] if item["path"] != "." else "root"
        avg_complexity = item["avg_complexity"]
        files_count = item["files"]
        violations = item.get("violations", 0)

        # Calculate heat level (0-10)
        heat_level = int((avg_complexity / max_complexity) * 10) if max_complexity > 0 else 0

        # Create heat bar using block characters
        blocks = ["░", "▒", "▓", "█"]
        bar_segments = []
        for i in range(10):
            if i < heat_level:
                # Choose block based on intensity
                block_index = min(3, int((i / 10) * 4))
                bar_segments.append(blocks[block_index])
            else:
                bar_segments.append("░")

        heat_bar = "".join(bar_segments)

        # Choose color based on complexity
        if avg_complexity > 20:
            color_class = "critical-heat"
            indicator = "🔴"
        elif avg_complexity > 10:
            color_class = "high-heat"
            indicator = "🟠"
        elif avg_complexity > 5:
            color_class = "medium-heat"
            indicator = "🟡"
        else:
            color_class = "low-heat"
            indicator = "🟢"

        # Create the heatmap item container
        container = Container(classes=f"heatmap-item {color_class}")

        # Path and indicator
        with container:
            container.mount(Static(f"{indicator} {path}", classes="heatmap-path"))

            # Stats row
            stats_text = f"{heat_bar} {avg_complexity:.1f} avg | {files_count} files"
            if violations > 0:
                stats_text += f" | {violations} violations"
            container.mount(Static(stats_text, classes="heatmap-stats"))

        # Store data on the widget for click handling
        container._heatmap_data = {"index": index, "item": item}

        return container

    def on_click(self, event: Any) -> None:
        """Handle click events on heatmap items."""
        # Find which item was clicked
        widget = event.widget
        while widget and not hasattr(widget, "data"):
            widget = widget.parent

        if widget and hasattr(widget, "data"):
            data = widget.data
            if "item" in data:
                item = data["item"]
                self.selected_index = data.get("index", -1)
                self.post_message(DirectorySelected(item["path"], item))

                # Update visual selection
                self._update_selection()

    def _update_selection(self) -> None:
        """Update visual selection state."""
        for i, item_widget in enumerate(self._heatmap_items):
            if i == self.selected_index:
                item_widget.add_class("selected")
            else:
                item_widget.remove_class("selected")

    def update_heatmap(self, heatmap_data: list[dict[str, Any]]) -> None:
        """Update the heatmap with new data."""
        self.heatmap_data = heatmap_data


class HeatmapLegend(Widget):
    """Legend for the heatmap visualization."""

    def compose(self) -> ComposeResult:
        """Create the legend layout."""
        with Container(classes="heatmap-legend"):
            yield Static("Complexity Legend:", classes="legend-title")
            with Container(classes="legend-items"):
                yield Static("🟢 Low (≤5)", classes="legend-item low-complexity")
                yield Static("🟡 Medium (6-10)", classes="legend-item medium-complexity")
                yield Static("🟠 High (11-20)", classes="legend-item high-complexity")
                yield Static("🔴 Critical (>20)", classes="legend-item critical-complexity")
