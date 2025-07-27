"""Detail view panel widget for terminal dashboard."""

from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, DataTable

from code_cop.core.violations import FileReport


class DetailViewWidget(Widget):
    """File and function detail display widget."""

    COMPONENT_CLASSES = {"detail-view-widget"}

    file_report: reactive[Optional[FileReport]] = reactive(None)
    selected_file: reactive[str] = reactive("")

    def __init__(self, **kwargs) -> None:
        """Initialize the detail view widget."""
        super().__init__(**kwargs)
        self._function_table: Optional[DataTable] = None

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Container(classes="detail-container"):
            yield Static("📋 File Details", classes="detail-title")

            with ScrollableContainer(classes="detail-scroll"):
                # File info section
                with Container(classes="file-info"):
                    yield Static("No file selected", id="file-name", classes="file-name")
                    yield Static("", id="file-path", classes="file-path")

                # Metrics summary
                with Container(classes="metrics-summary"):
                    yield Static("Metrics", classes="section-title")
                    yield Static("", id="metrics-text", classes="metrics-content")

                # Function breakdown
                with Container(classes="function-breakdown"):
                    yield Static("Function Complexity", classes="section-title")
                    table = DataTable(show_cursor=False)
                    table.add_columns("Function", "CC", "Cognitive", "Lines")
                    self._function_table = table
                    yield table

                # Violations section
                with Container(classes="violations-section"):
                    yield Static("Violations", classes="section-title")
                    yield Container(id="violations-list", classes="violations-list")

    def on_mount(self) -> None:
        """Initialize the widget when mounted."""
        if self.file_report:
            self._update_display()

    def watch_file_report(self, old_report: Optional[FileReport], new_report: Optional[FileReport]) -> None:
        """React to file report changes."""
        self._update_display()

    def _update_display(self) -> None:
        """Update the display with current file report."""
        if not self.file_report:
            self._show_empty_state()
            return

        # Update file info
        file_name = self.file_report.file_path.name
        file_path = str(self.file_report.file_path)

        self.query_one("#file-name", Static).update(f"📄 {file_name}")
        self.query_one("#file-path", Static).update(file_path)

        # Update metrics summary
        metrics_lines = self._format_metrics(self.file_report.metrics)
        self.query_one("#metrics-text", Static).update(metrics_lines)

        # Update function table
        self._update_function_table()

        # Update violations
        self._update_violations()

    def _show_empty_state(self) -> None:
        """Show empty state when no file is selected."""
        self.query_one("#file-name", Static).update("No file selected")
        self.query_one("#file-path", Static).update("Select a file from the tree to view details")
        self.query_one("#metrics-text", Static).update("")

        if self._function_table:
            self._function_table.clear()

        violations_list = self.query_one("#violations-list", Container)
        violations_list.remove_children()
        violations_list.mount(Static("No violations", classes="no-violations"))

    def _format_metrics(self, metrics: dict[str, Any] | list[Any]) -> str:
        """Format metrics for display."""
        lines = []

        if isinstance(metrics, dict):
            # Handle dict format
            for key, value in metrics.items():
                if value is not None:
                    metric_name = key.replace("_", " ").title()
                    if isinstance(value, float):
                        lines.append(f"• {metric_name}: {value:.2f}")
                    else:
                        lines.append(f"• {metric_name}: {value}")
        elif isinstance(metrics, list):
            # Handle list of MetricResult objects
            for metric in metrics:
                if hasattr(metric, "type") and hasattr(metric, "value"):
                    metric_name = metric.type.value.replace("_", " ").title()
                    if metric.value is not None:
                        if isinstance(metric.value, float):
                            lines.append(f"• {metric_name}: {metric.value:.2f}")
                        else:
                            lines.append(f"• {metric_name}: {metric.value}")

        return "\n".join(lines) if lines else "No metrics available"

    def _update_function_table(self) -> None:
        """Update the function complexity table."""
        if not self._function_table or not self.file_report:
            return

        self._function_table.clear()

        # Check if we have function-level data
        # This would come from detailed analysis - for now, show aggregate
        if hasattr(self.file_report, "function_metrics"):
            # If we have function-level metrics
            for func_data in getattr(self.file_report, "function_metrics", []):
                self._function_table.add_row(
                    func_data.get("name", "Unknown"),
                    str(func_data.get("cyclomatic_complexity", "-")),
                    str(func_data.get("cognitive_complexity", "-")),
                    str(func_data.get("lines", "-"))
                )
        else:
            # Show aggregate data
            if isinstance(self.file_report.metrics, dict):
                cc = self.file_report.metrics.get("cyclomatic_complexity", "-")
                cog = self.file_report.metrics.get("cognitive_complexity", "-")
                loc = self.file_report.metrics.get("loc", "-")

                self._function_table.add_row(
                    "File Total",
                    str(cc) if cc != "-" else "-",
                    str(cog) if cog != "-" else "-",
                    str(loc) if loc != "-" else "-"
                )

    def _update_violations(self) -> None:
        """Update the violations list."""
        violations_list = self.query_one("#violations-list", Container)
        violations_list.remove_children()

        if not self.file_report or not self.file_report.violations:
            violations_list.mount(Static("✅ No violations found", classes="no-violations"))
            return

        # Group violations by type
        violations_by_type: dict[str, list[Any]] = {}
        for violation in self.file_report.violations:
            metric_type = violation.metric_type.value
            if metric_type not in violations_by_type:
                violations_by_type[metric_type] = []
            violations_by_type[metric_type].append(violation)

        # Display violations
        for metric_type, violations in violations_by_type.items():
            # Type header
            type_name = metric_type.replace("_", " ").title()
            violations_list.mount(Static(f"❌ {type_name}", classes="violation-type"))

            # Individual violations
            for violation in violations:
                location = ""
                if violation.line_number:
                    location = f"Line {violation.line_number}"
                if violation.function_name:
                    location += f" ({violation.function_name})"

                violation_text = f"  • {location}: {violation.value:.2f} (threshold: {violation.comparison.value} {violation.threshold})"
                violations_list.mount(Static(violation_text, classes="violation-item"))

    def update_file_report(self, file_report: Optional[FileReport], file_path: str = "") -> None:
        """Update the widget with a new file report."""
        self.file_report = file_report
        self.selected_file = file_path