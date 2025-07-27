"""Terminal Dashboard Application for code-cop."""

from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static

from code_cop.terminal.data_bridge import DashboardDataBridge
from code_cop.terminal.widgets import (
    DetailViewWidget,
    DirectorySelected,
    FileSelected,
    FileTreeWidget,
    HeatmapWidget,
    MetricsOverviewWidget,
)


class TerminalDashboard(App):
    """Main terminal dashboard application."""

    CSS_PATH = "dashboard.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
        Binding("?", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("shift+tab", "focus_previous", "Previous Panel", show=False),
        Binding("1", "view_overview", "Overview"),
        Binding("2", "view_heatmap", "Heatmap"),
        Binding("3", "view_trends", "Trends"),
        Binding("4", "view_details", "Details"),
    ]

    def __init__(self, project_path: Optional[str] = None):
        """Initialize the dashboard.

        Args:
            project_path: Path to the project to analyze
        """
        super().__init__()
        self.project_path = project_path or "."
        self.current_view = "overview"
        self.data_bridge = DashboardDataBridge(self.project_path)

    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header(show_clock=True)

        with Container():
            with Horizontal():
                # Left panel - File tree
                with Vertical(classes="file-tree", id="file-tree-panel"):
                    yield FileTreeWidget(id="file-tree-widget")

                # Right side - Main content area
                with Vertical(id="main-content"):
                    # Top - Metrics overview
                    yield MetricsOverviewWidget(
                        id="metrics-widget",
                        classes="metrics-overview"
                    )

                    # Bottom panels
                    with Horizontal():
                        # Heatmap visualization
                        yield HeatmapWidget(
                            id="heatmap-widget",
                            classes="heatmap"
                        )

                        # Detail view
                        yield DetailViewWidget(
                            id="detail-widget",
                            classes="detail-view"
                        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard when mounted."""
        self.title = f"Code-Cop Dashboard - {self.project_path}"
        self.sub_title = "Code Quality Metrics Visualization"

        # Start initial analysis
        self.refresh_metrics()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_help(self) -> None:
        """Show help information."""
        # TODO: Implement help dialog
        self.notify("Help: Use number keys to switch views, 'r' to refresh, 'q' to quit")

    def action_refresh(self) -> None:
        """Refresh the metrics."""
        self.notify("Refreshing metrics...")
        self.refresh_metrics()

    def action_view_overview(self) -> None:
        """Switch to overview view."""
        self.current_view = "overview"
        self.notify("Switched to Overview")

    def action_view_heatmap(self) -> None:
        """Switch to heatmap view."""
        self.current_view = "heatmap"
        self.notify("Switched to Heatmap")

    def action_view_trends(self) -> None:
        """Switch to trends view."""
        self.current_view = "trends"
        self.notify("Switched to Trends")

    def action_view_details(self) -> None:
        """Switch to details view."""
        self.current_view = "details"
        self.notify("Switched to Details")

    def refresh_metrics(self) -> None:
        """Refresh metrics from the core engine."""
        try:
            # Analyze the project
            reports, summary = self.data_bridge.analyze_all()

            # Update metrics overview widget
            metrics_widget = self.query_one("#metrics-widget", MetricsOverviewWidget)
            metrics_summary = self.data_bridge.get_metrics_summary()
            metrics_widget.update_metrics(metrics_summary)

            # Update file tree widget
            file_tree_widget = self.query_one("#file-tree-widget", FileTreeWidget)
            tree_data = self.data_bridge.get_file_tree()
            file_tree_widget.update_tree_data(tree_data)

            # Update heatmap widget
            heatmap_widget = self.query_one("#heatmap-widget", HeatmapWidget)
            heatmap_data = self.data_bridge.get_heatmap_data()
            heatmap_widget.update_heatmap(heatmap_data)

        except NoMatches:
            self.log.error("Could not find UI elements to update")
        except Exception as e:
            self.notify(f"Error refreshing metrics: {e}", severity="error")

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts."""
        # Vim-style navigation
        if event.key == "j":
            self.action_focus_next()
        elif event.key == "k":
            self.action_focus_previous()

    def on_file_selected(self, message: FileSelected) -> None:
        """Handle file selection from the file tree."""
        # Update detail view with selected file
        detail_widget = self.query_one("#detail-widget", DetailViewWidget)
        detail_widget.update_file_report(message.report, message.file_path)

        # Show notification
        self.notify(f"Selected: {message.file_path}")

    def on_directory_selected(self, message: DirectorySelected) -> None:
        """Handle directory selection from the heatmap."""
        # Could navigate file tree to this directory or show details
        self.notify(f"Selected directory: {message.directory_path}")


if __name__ == "__main__":
    # For testing the dashboard directly
    app = TerminalDashboard()
    app.run()