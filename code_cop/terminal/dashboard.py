"""Terminal Dashboard Application for code-cop."""

from typing import Any, Optional, cast

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Footer, Header

from code_cop.terminal.data_bridge import DashboardDataBridge
from code_cop.terminal.filter_manager import FilterManager
from code_cop.terminal.focus_manager import FocusIndicator, FocusManager
from code_cop.terminal.shortcuts import ShortcutManager
from code_cop.terminal.widgets import (
    CommandItem,
    CommandPalette,
    DetailViewWidget,
    DirectorySelected,
    FileSelected,
    FileTreeWidget,
    FilterDialog,
    FiltersApplied,
    HeatmapWidget,
    HelpDialog,
    MetricsOverviewWidget,
)


class TerminalDashboard(App[None]):
    """Main terminal dashboard application."""

    CSS_PATH = "dashboard.tcss"

    def __init__(self, project_path: str | None = None):
        """Initialize the dashboard.

        Args:
            project_path: Path to the project to analyze
        """
        super().__init__()
        self.project_path = project_path or "."
        self.current_view = "overview"
        self.data_bridge = DashboardDataBridge(self.project_path)
        self.shortcut_manager = ShortcutManager()
        self.filter_manager = FilterManager()
        self.focus_manager = FocusManager()
        self.last_key = ""
        self._update_bindings()

    def _update_bindings(self) -> None:
        """Update app bindings from shortcut manager."""
        bindings: list[Binding | tuple[str, str] | tuple[str, str, str]] = cast(
            list[Binding | tuple[str, str] | tuple[str, str, str]],
            self.shortcut_manager.get_bindings()
        )
        type(self).BINDINGS = bindings

    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header(show_clock=True)

        with Container(), Horizontal():
            # Left panel - File tree
            with Vertical(classes="file-tree", id="file-tree-panel"):
                yield FileTreeWidget(id="file-tree-widget")

            # Right side - Main content area
            with Vertical(id="main-content"):
                # Top - Metrics overview
                yield MetricsOverviewWidget(id="metrics-widget", classes="metrics-overview")

                # Bottom panels
                with Horizontal():
                    # Heatmap visualization
                    yield HeatmapWidget(id="heatmap-widget", classes="heatmap")

                    # Detail view
                    yield DetailViewWidget(id="detail-widget", classes="detail-view")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the dashboard when mounted."""
        self.title = f"Code-Cop Dashboard - {self.project_path}"
        self.sub_title = "Code Quality Metrics Visualization"

        # Set up widget titles for focus indicators
        self._setup_widget_titles()

        # Start initial analysis
        self.refresh_metrics()

    def _setup_widget_titles(self) -> None:
        """Set up widget titles for focus indication."""
        try:
            file_tree = self.query_one("#file-tree-widget", FileTreeWidget)
            file_tree.border_title = "Files"

            metrics = self.query_one("#metrics-widget", MetricsOverviewWidget)
            metrics.border_title = "Metrics"

            heatmap = self.query_one("#heatmap-widget", HeatmapWidget)
            heatmap.border_title = "Heatmap"

            detail = self.query_one("#detail-widget", DetailViewWidget)
            detail.border_title = "Details"
        except Exception:
            pass

    async def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_show_help(self) -> None:
        """Show help information."""
        help_text = self.shortcut_manager.get_help_text()
        self.mount(HelpDialog(help_text=help_text))

    def action_refresh(self) -> None:
        """Refresh the metrics."""
        self.notify("Refreshing metrics...")
        self.refresh_metrics()

    def action_force_refresh(self) -> None:
        """Force refresh the metrics (clear cache)."""
        self.notify("Force refreshing metrics...")
        # TODO: Implement cache clearing
        self.refresh_metrics()

    def action_toggle_vim(self) -> None:
        """Toggle vim mode."""
        vim_mode = self.shortcut_manager.toggle_vim_mode()
        self._update_bindings()
        mode_str = "ON" if vim_mode else "OFF"
        self.notify(f"Vim mode: {mode_str}")

    def action_command_palette(self) -> None:
        """Show command palette."""
        self.mount(CommandPalette())

    def action_search(self) -> None:
        """Activate search mode."""
        # TODO: Implement search
        self.notify("Search coming soon!")

    def action_filter(self) -> None:
        """Show filter dialog."""
        self.mount(FilterDialog(self.filter_manager))

    def action_clear_filters(self) -> None:
        """Clear all filters."""
        self.filter_manager.clear_filters()
        self.notify("All filters cleared")
        self.refresh_metrics()

    def action_filter_complexity(self) -> None:
        """Quick filter by complexity."""
        from code_cop.terminal.filter_manager import Filter, FilterType

        # Add a quick complexity filter
        self.filter_manager.add_filter(
            Filter(
                type=FilterType.COMPLEXITY,
                value=10,
                comparison=">",
            )
        )
        self.notify("Filtering files with complexity > 10")
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

    def action_view_functions(self) -> None:
        """Switch to functions view."""
        self.current_view = "functions"
        self.notify("Switched to Functions")

    def action_view_all(self) -> None:
        """Show all views."""
        self.current_view = "all"
        self.notify("Showing all views")

    def action_cycle_theme(self) -> None:
        """Cycle through available themes."""
        # TODO: Implement theme cycling
        self.notify("Theme cycling coming soon!")

    def action_theme_menu(self) -> None:
        """Show theme selection menu."""
        # TODO: Implement theme menu
        self.notify("Theme menu coming soon!")

    def action_export_current(self) -> None:
        """Export current view."""
        # TODO: Implement export
        self.notify("Export coming soon!")

    def action_export_all(self) -> None:
        """Export all data."""
        # TODO: Implement full export
        self.notify("Export all coming soon!")

    def action_save_session(self) -> None:
        """Save current session."""
        # TODO: Implement session saving
        self.notify("Session saving coming soon!")

    def action_open_file(self) -> None:
        """Open selected file in editor."""
        # TODO: Implement file opening
        self.notify("Open file coming soon!")

    def action_open_directory(self) -> None:
        """Open selected directory in file manager."""
        # TODO: Implement directory opening
        self.notify("Open directory coming soon!")

    def action_copy_path(self) -> None:
        """Copy selected path to clipboard."""
        # TODO: Implement clipboard
        self.notify("Copy path coming soon!")

    def action_copy_metrics(self) -> None:
        """Copy metrics to clipboard."""
        # TODO: Implement metrics copying
        self.notify("Copy metrics coming soon!")

    # Vim navigation actions
    def action_move_down(self) -> None:
        """Move focus down (vim j)."""
        focused = self.focused
        if focused and hasattr(focused, "action_cursor_down"):
            focused.action_cursor_down()

    def action_move_up(self) -> None:
        """Move focus up (vim k)."""
        focused = self.focused
        if focused and hasattr(focused, "action_cursor_up"):
            focused.action_cursor_up()

    def action_move_left(self) -> None:
        """Move focus left (vim h)."""
        self.action_focus_previous()

    def action_move_right(self) -> None:
        """Move focus right (vim l)."""
        self.action_focus_next()

    def action_move_top(self) -> None:
        """Move to top (vim gg)."""
        focused = self.focused
        if focused and hasattr(focused, "action_first"):
            focused.action_first()

    def action_move_bottom(self) -> None:
        """Move to bottom (vim G)."""
        focused = self.focused
        if focused and hasattr(focused, "action_last"):
            focused.action_last()

    def action_page_up(self) -> None:
        """Page up (vim ctrl+u)."""
        focused = self.focused
        if focused and hasattr(focused, "action_page_up"):
            focused.action_page_up()

    def action_page_down(self) -> None:
        """Page down (vim ctrl+d)."""
        focused = self.focused
        if focused and hasattr(focused, "action_page_down"):
            focused.action_page_down()

    # Focus navigation actions
    def action_focus_left(self) -> None:
        """Focus panel to the left."""
        self._directional_focus("left")

    def action_focus_right(self) -> None:
        """Focus panel to the right."""
        self._directional_focus("right")

    def action_focus_up(self) -> None:
        """Focus panel above."""
        self._directional_focus("up")

    def action_focus_down(self) -> None:
        """Focus panel below."""
        self._directional_focus("down")

    def _directional_focus(self, direction: str) -> None:
        """Handle directional focus navigation.

        Args:
            direction: One of 'up', 'down', 'left', 'right'
        """
        if self.focused and hasattr(self.focused, "id"):
            current_id = self.focused.id
            if current_id:
                target_id = self.focus_manager.get_directional_target(current_id, direction)
                if target_id:
                    try:
                        target_widget = self.query_one(f"#{target_id}")
                        target_widget.focus()
                    except Exception:
                        pass

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
        # Handle vim-style navigation when in vim mode
        if self.shortcut_manager.vim_mode:
            if event.key == "j":
                self.action_move_down()
            elif event.key == "k":
                self.action_move_up()
            elif event.key == "h":
                self.action_move_left()
            elif event.key == "l":
                self.action_move_right()
            elif event.key == "g" and self.last_key == "g":
                self.action_move_top()
            elif event.key == "G":
                self.action_move_bottom()

        # Track last key for multi-key shortcuts
        self.last_key = event.key

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

    def on_command_item(self, message: CommandItem) -> None:
        """Handle command selection from command palette."""
        # Execute the action
        action_method = f"action_{message.action}"
        if hasattr(self, action_method):
            getattr(self, action_method)()
        else:
            self.notify(f"Command: {message.command} (action: {message.action})")

    def on_filters_applied(self, message: FiltersApplied) -> None:
        """Handle filters being applied."""
        self.filter_manager = message.filter_manager
        summary = self.filter_manager.get_active_filter_summary()
        self.notify(f"Filters applied: {summary}")
        self.refresh_metrics()

    def on_focus(self, event: Any) -> None:
        """Handle focus changes."""
        if hasattr(event.widget, "id"):
            widget_id = event.widget.id
            # Record focus in history
            self.focus_manager.record_focus(widget_id)
            # Apply visual indicators
            self._update_focus_indicators(widget_id)

    def _update_focus_indicators(self, focused_id: str) -> None:
        """Update visual focus indicators.

        Args:
            focused_id: ID of the focused widget
        """
        # Update all focusable widgets
        for widget_id in self.focus_manager.get_all_focusable_widgets():
            try:
                widget = self.query_one(f"#{widget_id}")
                is_focused = widget_id == focused_id
                FocusIndicator.apply_focus_style(widget, is_focused)
            except Exception:
                pass

    def action_toggle_expand(self) -> None:
        """Toggle expand/collapse in focused widget."""
        focused = self.focused
        if focused and hasattr(focused, "toggle"):
            focused.toggle()

    def action_select(self) -> None:
        """Select item in focused widget."""
        focused = self.focused
        if focused and hasattr(focused, "action_select"):
            focused.action_select()


if __name__ == "__main__":
    # For testing the dashboard directly
    app = TerminalDashboard()
    app.run()
