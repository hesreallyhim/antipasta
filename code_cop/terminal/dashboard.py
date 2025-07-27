"""Terminal Dashboard Application for code-cop."""

from typing import Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static

from code_cop.terminal.data_bridge import DashboardDataBridge


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
                    yield Static("📁 File Explorer", classes="panel-title")
                    yield Static("Loading files...", id="file-tree-content")

                # Right side - Main content area
                with Vertical(id="main-content"):
                    # Top - Metrics overview
                    with Container(classes="metrics-overview", id="metrics-panel"):
                        yield Static("📊 Metrics Overview", classes="panel-title")
                        yield Static("Analyzing...", id="metrics-content")

                    # Bottom panels
                    with Horizontal():
                        # Heatmap visualization
                        with Container(classes="heatmap", id="heatmap-panel"):
                            yield Static("🔥 Complexity Heatmap", classes="panel-title")
                            yield Static("Generating heatmap...", id="heatmap-content")

                        # Detail view
                        with Container(classes="detail-view", id="detail-panel"):
                            yield Static("📋 Detail View", classes="panel-title")
                            yield Static("Select a file to view details", id="detail-content")

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

            # Update metrics overview
            metrics_content = self.query_one("#metrics-content", Static)
            metrics_summary = self.data_bridge.get_metrics_summary()

            complexity_dist = metrics_summary.get("complexity_distribution", {})
            metrics_text = f"""📊 Analysis complete!

Files analyzed: {summary['total_files']}
🔴 Critical (>20): {complexity_dist.get('critical', 0)}
🟠 High (11-20): {complexity_dist.get('high', 0)}
🟡 Medium (6-10): {complexity_dist.get('medium', 0)}
🟢 Low (≤5): {complexity_dist.get('low', 0)}

Total violations: {summary['total_violations']}"""
            metrics_content.update(metrics_text)

            # Update file tree
            file_tree_content = self.query_one("#file-tree-content", Static)
            tree_data = self.data_bridge.get_file_tree()
            tree_text = self._render_file_tree(tree_data)
            file_tree_content.update(tree_text)

            # Update heatmap
            heatmap_content = self.query_one("#heatmap-content", Static)
            heatmap_data = self.data_bridge.get_heatmap_data()
            heatmap_text = self._render_heatmap(heatmap_data[:5])  # Top 5 directories
            heatmap_content.update(heatmap_text)

        except NoMatches:
            self.log.error("Could not find UI elements to update")
        except Exception as e:
            self.notify(f"Error refreshing metrics: {e}", severity="error")

    def _render_file_tree(self, tree: dict, level: int = 0) -> str:
        """Render file tree as text."""
        lines = []
        indent = "  " * level

        if tree["type"] == "directory" and tree["children"]:
            for name, node in sorted(tree["children"].items()):
                if node["type"] == "directory":
                    lines.append(f"{indent}▼ {name}/")
                    lines.append(self._render_file_tree(node, level + 1))
                else:
                    # File with complexity indicator
                    complexity = node.get("complexity", 0)
                    if complexity > 20:
                        indicator = "🔴"
                    elif complexity > 10:
                        indicator = "🟠"
                    elif complexity > 5:
                        indicator = "🟡"
                    else:
                        indicator = "🟢"

                    violations = node.get("violations", 0)
                    suffix = f" ({violations} issues)" if violations > 0 else ""
                    lines.append(f"{indent}• {name} {indicator}{suffix}")

        return "\n".join(lines)

    def _render_heatmap(self, data: list[dict]) -> str:
        """Render heatmap data as text."""
        if not data:
            return "No data to display"

        lines = []
        max_complexity = max(item["avg_complexity"] for item in data)

        for item in data:
            path = item["path"] if item["path"] != "." else "root"
            avg_complexity = item["avg_complexity"]
            percentage = (avg_complexity / max_complexity * 100) if max_complexity > 0 else 0

            # Create bar
            bar_length = int(percentage / 10)
            bar = "█" * bar_length + "░" * (10 - bar_length)

            lines.append(f"{path:<20} {bar} {percentage:.0f}% ({item['files']} files)")

        return "\n".join(lines)

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts."""
        # Vim-style navigation
        if event.key == "j":
            self.action_focus_next()
        elif event.key == "k":
            self.action_focus_previous()


if __name__ == "__main__":
    # For testing the dashboard directly
    app = TerminalDashboard()
    app.run()