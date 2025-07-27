"""Focus management for terminal dashboard widgets."""

from typing import List, Optional

from textual.widget import Widget


class FocusManager:
    """Manages focus state and navigation between widgets."""

    def __init__(self):
        """Initialize the focus manager."""
        self.focus_history: List[str] = []
        self.focus_groups: dict[str, List[str]] = {
            "main": ["file-tree-widget", "metrics-widget"],
            "bottom": ["heatmap-widget", "detail-widget"],
        }
        self.current_group = "main"
        self.current_index = 0

    def record_focus(self, widget_id: str) -> None:
        """Record widget focus in history.

        Args:
            widget_id: ID of the focused widget
        """
        # Don't duplicate consecutive entries
        if not self.focus_history or self.focus_history[-1] != widget_id:
            self.focus_history.append(widget_id)
            # Keep history limited
            if len(self.focus_history) > 10:
                self.focus_history.pop(0)

    def get_previous_focus(self) -> Optional[str]:
        """Get the previously focused widget ID.

        Returns:
            Widget ID or None
        """
        if len(self.focus_history) >= 2:
            return self.focus_history[-2]
        return None

    def get_next_in_group(self, current_id: str, direction: int = 1) -> Optional[str]:
        """Get next widget in the current focus group.

        Args:
            current_id: Current widget ID
            direction: 1 for next, -1 for previous

        Returns:
            Next widget ID or None
        """
        for group, widgets in self.focus_groups.items():
            if current_id in widgets:
                current_idx = widgets.index(current_id)
                next_idx = (current_idx + direction) % len(widgets)
                return widgets[next_idx]
        return None

    def get_directional_target(self, current_id: str, direction: str) -> Optional[str]:
        """Get target widget for directional navigation.

        Args:
            current_id: Current widget ID
            direction: One of 'up', 'down', 'left', 'right'

        Returns:
            Target widget ID or None
        """
        # Define spatial relationships
        spatial_map = {
            "file-tree-widget": {
                "right": "metrics-widget",
                "down": "heatmap-widget",
            },
            "metrics-widget": {
                "left": "file-tree-widget",
                "down": "heatmap-widget",
            },
            "heatmap-widget": {
                "up": "file-tree-widget",
                "right": "detail-widget",
            },
            "detail-widget": {
                "up": "metrics-widget",
                "left": "heatmap-widget",
            },
        }

        if current_id in spatial_map:
            return spatial_map[current_id].get(direction)
        return None

    def get_all_focusable_widgets(self) -> List[str]:
        """Get all focusable widget IDs in order.

        Returns:
            List of widget IDs
        """
        all_widgets = []
        for widgets in self.focus_groups.values():
            all_widgets.extend(widgets)
        return all_widgets


class FocusIndicator:
    """Visual focus indicator styles."""

    FOCUSED = """
        border: thick $accent;
        border-title-align: center;
        border-title-color: $accent;
    """

    UNFOCUSED = """
        border: round #424242;
        border-title-align: center;
        border-title-color: #666666;
    """

    @staticmethod
    def apply_focus_style(widget: Widget, focused: bool) -> None:
        """Apply focus styling to a widget.

        Args:
            widget: Widget to style
            focused: Whether widget is focused
        """
        if hasattr(widget, "border_title"):
            if focused:
                widget.styles.border = ("thick", "$accent")
                widget.border_title = f"[ {widget.border_title or ''} ]"
            else:
                widget.styles.border = ("round", "#424242")
                widget.border_title = widget.border_title or ""
