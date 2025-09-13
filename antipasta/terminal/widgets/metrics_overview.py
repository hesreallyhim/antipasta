"""Metrics overview panel widget for terminal dashboard."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ProgressBar, Static


class MetricsOverviewWidget(Widget):
    """Summary statistics widget for metrics overview."""

    COMPONENT_CLASSES = {"metrics-overview-widget"}

    metrics_summary: reactive[dict[str, Any]] = reactive({})

    def __init__(self, metrics_summary: dict[str, Any] | None = None, **kwargs: Any) -> None:
        """Initialize the metrics overview widget.

        Args:
            metrics_summary: Summary data from DashboardDataBridge
        """
        super().__init__(**kwargs)
        if metrics_summary:
            self.metrics_summary = metrics_summary

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Container(classes="metrics-container"):
            # Title
            yield Static("📊 Code Quality Metrics", classes="metrics-title")

            # Main stats grid
            with Horizontal(classes="stats-grid"):
                # Total files
                with Vertical(classes="stat-box"):
                    yield Static("Total Files", classes="stat-label")
                    yield Static("0", id="total-files", classes="stat-value")

                # Success rate
                with Vertical(classes="stat-box"):
                    yield Static("Success Rate", classes="stat-label")
                    yield Static("0%", id="success-rate", classes="stat-value")

                # Total violations
                with Vertical(classes="stat-box"):
                    yield Static("Violations", classes="stat-label")
                    yield Static("0", id="total-violations", classes="stat-value")

            # Complexity distribution
            yield Static("Complexity Distribution", classes="section-title")
            with Container(classes="distribution-container"):
                # Low complexity
                with Horizontal(classes="dist-row"):
                    yield Static("🟢 Low (≤5)", classes="dist-label low-complexity")
                    yield ProgressBar(id="low-bar", total=100, show_eta=False)
                    yield Static("0", id="low-count", classes="dist-count")

                # Medium complexity
                with Horizontal(classes="dist-row"):
                    yield Static("🟡 Medium (6-10)", classes="dist-label medium-complexity")
                    yield ProgressBar(id="medium-bar", total=100, show_eta=False)
                    yield Static("0", id="medium-count", classes="dist-count")

                # High complexity
                with Horizontal(classes="dist-row"):
                    yield Static("🟠 High (11-20)", classes="dist-label high-complexity")
                    yield ProgressBar(id="high-bar", total=100, show_eta=False)
                    yield Static("0", id="high-count", classes="dist-count")

                # Critical complexity
                with Horizontal(classes="dist-row"):
                    yield Static("🔴 Critical (>20)", classes="dist-label critical-complexity")
                    yield ProgressBar(id="critical-bar", total=100, show_eta=False)
                    yield Static("0", id="critical-count", classes="dist-count")

            # Violations by type
            yield Static("Violations by Type", classes="section-title")
            with Container(id="violations-by-type", classes="violations-container"):
                yield Static("No violations found", classes="no-data")

    def on_mount(self) -> None:
        """Initialize the widget when mounted."""
        if self.metrics_summary:
            self._update_display()

    def watch_metrics_summary(
        self, old_summary: dict[str, Any], new_summary: dict[str, Any]
    ) -> None:
        """React to metrics summary changes."""
        self._update_display()

    def _update_display(self) -> None:
        """Update the display with current metrics."""
        if not self.metrics_summary:
            return

        # Update total files
        total_files = self.metrics_summary.get("total_files", 0)
        self.query_one("#total-files", Static).update(str(total_files))

        # Update success rate
        files_with_violations = self.metrics_summary.get("files_with_violations", 0)
        success_rate = (
            ((total_files - files_with_violations) / total_files * 100) if total_files > 0 else 100
        )
        self.query_one("#success-rate", Static).update(f"{success_rate:.1f}%")

        # Update total violations
        total_violations = self.metrics_summary.get("total_violations", 0)
        self.query_one("#total-violations", Static).update(str(total_violations))

        # Update complexity distribution
        complexity_dist = self.metrics_summary.get("complexity_distribution", {})
        total_complexity_files = sum(complexity_dist.values())

        if total_complexity_files > 0:
            # Low complexity
            low_count = complexity_dist.get("low", 0)
            low_pct = (low_count / total_complexity_files) * 100
            self.query_one("#low-bar", ProgressBar).progress = low_pct
            self.query_one("#low-count", Static).update(str(low_count))

            # Medium complexity
            medium_count = complexity_dist.get("medium", 0)
            medium_pct = (medium_count / total_complexity_files) * 100
            self.query_one("#medium-bar", ProgressBar).progress = medium_pct
            self.query_one("#medium-count", Static).update(str(medium_count))

            # High complexity
            high_count = complexity_dist.get("high", 0)
            high_pct = (high_count / total_complexity_files) * 100
            self.query_one("#high-bar", ProgressBar).progress = high_pct
            self.query_one("#high-count", Static).update(str(high_count))

            # Critical complexity
            critical_count = complexity_dist.get("critical", 0)
            critical_pct = (critical_count / total_complexity_files) * 100
            self.query_one("#critical-bar", ProgressBar).progress = critical_pct
            self.query_one("#critical-count", Static).update(str(critical_count))

        # Update violations by type
        violations_by_type = self.metrics_summary.get("violations_by_type", {})
        violations_container = self.query_one("#violations-by-type", Container)
        violations_container.remove_children()

        if violations_by_type:
            for metric_type, count in sorted(
                violations_by_type.items(), key=lambda x: x[1], reverse=True
            ):
                with violations_container, Horizontal(classes="violation-row"):
                    # Format metric type name
                    type_name = metric_type.replace("_", " ").title()
                    violations_container.mount(Static(f"• {type_name}:", classes="violation-type"))
                    violations_container.mount(Static(str(count), classes="violation-count"))
        else:
            violations_container.mount(Static("✓ No violations found", classes="no-violations"))

    def update_metrics(self, metrics_summary: dict[str, Any]) -> None:
        """Update the widget with new metrics summary."""
        self.metrics_summary = metrics_summary


class MetricsSparkline(Widget):
    """A simple sparkline widget for showing trends."""

    def __init__(self, data: list[float], **kwargs: Any) -> None:
        """Initialize the sparkline widget."""
        super().__init__(**kwargs)
        self.data = data

    def render(self) -> str:
        """Render the sparkline."""
        if not self.data:
            return ""

        # Normalize data to 0-7 range for block characters
        min_val = min(self.data)
        max_val = max(self.data)
        range_val = max_val - min_val if max_val != min_val else 1

        blocks = " ▁▂▃▄▅▆▇█"
        sparkline = ""

        for value in self.data:
            normalized = (value - min_val) / range_val
            index = int(normalized * 8)
            sparkline += blocks[index]

        return sparkline
