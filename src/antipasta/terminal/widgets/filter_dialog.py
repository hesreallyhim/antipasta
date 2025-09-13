"""Filter dialog widget for configuring metric filters."""

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, Select, Static, Switch

from antipasta.terminal.filter_manager import Filter, FilterManager, FilterType


class FiltersApplied(Message):
    """Message sent when filters are applied."""

    def __init__(self, filter_manager: FilterManager) -> None:
        """Initialize the message.

        Args:
            filter_manager: The filter manager with applied filters
        """
        super().__init__()
        self.filter_manager = filter_manager


class FilterDialog(Container):
    """Dialog for configuring filters."""

    DEFAULT_CSS = """
    FilterDialog {
        align: center middle;
        width: 100%;
        height: 100%;
        background: $surface 50%;
        layer: overlay;
    }

    FilterDialog > Vertical {
        width: 60%;
        max-width: 80;
        height: 70%;
        max-height: 30;
        background: $panel;
        border: thick $primary;
        padding: 1;
    }

    FilterDialog .dialog-title {
        text-align: center;
        text-style: bold;
        background: $primary;
        color: $text;
        height: 3;
        padding: 1;
        dock: top;
    }

    FilterDialog .filter-content {
        height: 1fr;
        overflow-y: scroll;
        padding: 1;
    }

    FilterDialog .filter-row {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: #1e1e1e;
        border: round #424242;
    }

    FilterDialog .filter-controls {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    FilterDialog .preset-section {
        height: auto;
        margin-bottom: 2;
        padding: 1;
        background: #252525;
        border: round #424242;
    }

    FilterDialog .section-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    FilterDialog .preset-button {
        margin: 0 1 1 0;
        height: 3;
    }

    FilterDialog .dialog-footer {
        height: 3;
        align: center middle;
        dock: bottom;
        margin-top: 1;
    }

    FilterDialog Input {
        width: 15;
        margin: 0 1;
    }

    FilterDialog Select {
        width: 20;
        margin: 0 1;
    }
    """

    def __init__(self, filter_manager: FilterManager | None = None, **kwargs: Any) -> None:
        """Initialize the filter dialog.

        Args:
            filter_manager: Existing filter manager or None to create new
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.filter_manager = filter_manager or FilterManager()
        self.temp_filters: list[Filter] = self.filter_manager.filters.copy()

    def compose(self) -> ComposeResult:
        """Compose the filter dialog."""
        with Vertical():
            yield Static("🔍 Filter Configuration", classes="dialog-title")

            with Container(classes="filter-content"):
                # Preset filters section
                with Container(classes="preset-section"):
                    yield Static("Quick Presets", classes="section-title")
                    with Horizontal():
                        for preset_name, preset in self.filter_manager.presets.items():
                            yield Button(
                                preset.name,
                                variant="primary",
                                classes="preset-button",
                                id=f"preset-{preset_name}",
                            )

                # Active filters
                yield Static("Active Filters", classes="section-title")
                yield Container(id="active-filters-container")

                # Add new filter section
                yield Static("Add New Filter", classes="section-title")
                with Grid(id="new-filter-grid"):
                    yield Label("Type:")
                    yield Select(
                        options=[
                            ("complexity", "Cyclomatic Complexity"),
                            ("maintainability", "Maintainability Index"),
                            ("file_pattern", "File Pattern"),
                            ("violation_type", "Violation Type"),
                        ],
                        id="filter-type-select",
                    )

                    yield Label("Comparison:")
                    yield Select(
                        options=[
                            ("=", "Equals"),
                            ("<", "Less Than"),
                            (">", "Greater Than"),
                            ("<=", "Less or Equal"),
                            (">=", "Greater or Equal"),
                            ("contains", "Contains"),
                        ],
                        id="comparison-select",
                    )

                    yield Label("Value:")
                    yield Input(
                        placeholder="Enter value...",
                        id="filter-value-input",
                    )

                    yield Label("")  # Spacer
                    yield Button("Add Filter", variant="success", id="add-filter-btn")

            with Container(classes="dialog-footer"):
                with Horizontal(classes="filter-controls"):
                    yield Button("Apply", variant="primary", id="apply-filters")
                    yield Button("Clear All", variant="warning", id="clear-filters")
                    yield Button("Cancel", variant="default", id="cancel-filters")

    def on_mount(self) -> None:
        """Initialize when mounted."""
        self._update_filter_display()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id and button_id.startswith("preset-"):
            # Apply preset
            preset_name = button_id.replace("preset-", "")
            if self.filter_manager.apply_preset(preset_name):
                self.temp_filters = self.filter_manager.filters.copy()
                self._update_filter_display()
                self.notify(f"Applied preset: {preset_name}")

        elif button_id == "add-filter-btn":
            self._add_new_filter()

        elif button_id == "apply-filters":
            # Apply filters and close
            self.filter_manager.filters = self.temp_filters.copy()
            self.post_message(FiltersApplied(self.filter_manager))
            self.remove()

        elif button_id == "clear-filters":
            # Clear all filters
            self.temp_filters.clear()
            self._update_filter_display()

        elif button_id == "cancel-filters":
            # Close without applying
            self.remove()

        elif button_id and button_id.startswith("remove-filter-"):
            # Remove specific filter
            try:
                index = int(button_id.replace("remove-filter-", ""))
                if 0 <= index < len(self.temp_filters):
                    del self.temp_filters[index]
                    self._update_filter_display()
            except ValueError:
                pass

    def _add_new_filter(self) -> None:
        """Add a new filter based on form inputs."""
        try:
            type_select = self.query_one("#filter-type-select", Select)
            comparison_select = self.query_one("#comparison-select", Select)
            value_input = self.query_one("#filter-value-input", Input)

            if not value_input.value:
                self.notify("Please enter a value", severity="warning")
                return

            # Parse value based on type
            filter_type = FilterType(type_select.value)
            value_str = value_input.value
            value: Any = value_str

            # Convert numeric values for numeric filters
            if filter_type in [FilterType.COMPLEXITY, FilterType.MAINTAINABILITY]:
                try:
                    value = float(value_str)
                except ValueError:
                    self.notify("Please enter a numeric value", severity="error")
                    return

            # Create and add filter
            new_filter = Filter(
                type=filter_type,
                value=value,
                comparison=str(comparison_select.value) if comparison_select.value else "=",
                enabled=True,
            )

            self.temp_filters.append(new_filter)
            self._update_filter_display()

            # Clear input
            value_input.value = ""

        except Exception as e:
            self.notify(f"Error adding filter: {e}", severity="error")

    def _update_filter_display(self) -> None:
        """Update the display of active filters."""
        container = self.query_one("#active-filters-container", Container)
        container.remove_children()

        if not self.temp_filters:
            container.mount(Static("[dim]No active filters[/dim]", classes="no-filters"))
            return

        # Display each filter
        for i, filter in enumerate(self.temp_filters):
            row_container = Container(classes="filter-row")
            container.mount(row_container)
            with row_container:
                # Filter description
                type_name = filter.type.value.replace("_", " ").title()
                desc = f"{type_name} {filter.comparison} {filter.value}"

                container.mount(
                    Horizontal(
                        Static(desc),
                        Switch(value=filter.enabled, id=f"filter-enabled-{i}"),
                        Button("Remove", variant="error", id=f"remove-filter-{i}"),
                    )
                )

    @on(Switch.Changed)
    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle filter enable/disable toggle."""
        if event.switch.id and event.switch.id.startswith("filter-enabled-"):
            try:
                index = int(event.switch.id.replace("filter-enabled-", ""))
                if 0 <= index < len(self.temp_filters):
                    self.temp_filters[index].enabled = event.value
            except ValueError:
                pass

    def on_key(self, event: Any) -> None:
        """Handle key events."""
        if event.key == "escape":
            self.remove()
