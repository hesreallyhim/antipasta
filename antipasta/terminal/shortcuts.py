"""Keyboard shortcut management for the terminal dashboard."""

from dataclasses import dataclass
from typing import Dict, List

from textual.binding import Binding


@dataclass
class Shortcut:
    """Represents a keyboard shortcut."""

    key: str
    action: str
    description: str
    category: str = "General"
    vim_mode: bool = False
    show_in_footer: bool = True


class ShortcutManager:
    """Manages keyboard shortcuts and vim-style navigation."""

    def __init__(self) -> None:
        """Initialize the shortcut manager."""
        self.vim_mode = False
        self.shortcuts: Dict[str, Shortcut] = {}
        self._init_shortcuts()

    def _init_shortcuts(self) -> None:
        """Initialize default shortcuts."""
        # General shortcuts
        self.add_shortcut("q", "quit", "Quit", "General")
        self.add_shortcut("ctrl+c", "quit", "Quit", "General", show_in_footer=False)
        self.add_shortcut("?", "show_help", "Help", "General")
        self.add_shortcut("r", "refresh", "Refresh", "General")
        self.add_shortcut(
            "ctrl+r", "force_refresh", "Force Refresh", "General", show_in_footer=False
        )
        self.add_shortcut(":", "command_palette", "Command", "General")
        self.add_shortcut(
            "ctrl+p", "command_palette", "Command Palette", "General", show_in_footer=False
        )

        # Navigation shortcuts
        self.add_shortcut("tab", "focus_next", "Next Panel", "Navigation", show_in_footer=False)
        self.add_shortcut(
            "shift+tab", "focus_previous", "Previous Panel", "Navigation", show_in_footer=False
        )
        self.add_shortcut("ctrl+h", "focus_left", "Focus Left", "Navigation", show_in_footer=False)
        self.add_shortcut(
            "ctrl+l", "focus_right", "Focus Right", "Navigation", show_in_footer=False
        )
        self.add_shortcut("ctrl+j", "focus_down", "Focus Down", "Navigation", show_in_footer=False)
        self.add_shortcut("ctrl+k", "focus_up", "Focus Up", "Navigation", show_in_footer=False)

        # Vim-style navigation (activated in vim mode)
        self.add_shortcut("h", "move_left", "Left", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut("j", "move_down", "Down", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut("k", "move_up", "Up", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut("l", "move_right", "Right", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut("g g", "move_top", "Top", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut("G", "move_bottom", "Bottom", "Vim", vim_mode=True, show_in_footer=False)
        self.add_shortcut(
            "ctrl+u", "page_up", "Page Up", "Vim", vim_mode=True, show_in_footer=False
        )
        self.add_shortcut(
            "ctrl+d", "page_down", "Page Down", "Vim", vim_mode=True, show_in_footer=False
        )

        # View shortcuts
        self.add_shortcut("1", "view_overview", "Overview", "Views")
        self.add_shortcut("2", "view_heatmap", "Heatmap", "Views")
        self.add_shortcut("3", "view_trends", "Trends", "Views")
        self.add_shortcut("4", "view_details", "Details", "Views")
        self.add_shortcut("5", "view_functions", "Functions", "Views")
        self.add_shortcut("0", "view_all", "All Views", "Views")

        # Filter shortcuts
        self.add_shortcut("/", "search", "Search", "Filters")
        self.add_shortcut("f", "filter", "Filter", "Filters")
        self.add_shortcut("F", "clear_filters", "Clear Filters", "Filters")
        self.add_shortcut(
            "ctrl+f", "filter_complexity", "Filter Complexity", "Filters", show_in_footer=False
        )

        # Actions
        self.add_shortcut("space", "toggle_expand", "Toggle", "Actions")
        self.add_shortcut("enter", "select", "Select", "Actions")
        self.add_shortcut("o", "open_file", "Open File", "Actions")
        self.add_shortcut("O", "open_directory", "Open Directory", "Actions")
        self.add_shortcut("c", "copy_path", "Copy Path", "Actions")
        self.add_shortcut("C", "copy_metrics", "Copy Metrics", "Actions")

        # Export shortcuts
        self.add_shortcut("e", "export_current", "Export View", "Export")
        self.add_shortcut("E", "export_all", "Export All", "Export")
        self.add_shortcut("ctrl+s", "save_session", "Save Session", "Export", show_in_footer=False)

        # Theme shortcuts
        self.add_shortcut("t", "cycle_theme", "Theme", "Display")
        self.add_shortcut("T", "theme_menu", "Theme Menu", "Display")
        self.add_shortcut("v", "toggle_vim", "Vim Mode", "Display")

    def add_shortcut(
        self,
        key: str,
        action: str,
        description: str,
        category: str = "General",
        vim_mode: bool = False,
        show_in_footer: bool = True,
    ) -> None:
        """Add a keyboard shortcut.

        Args:
            key: Key combination
            action: Action identifier
            description: Human-readable description
            category: Category for grouping
            vim_mode: Whether this shortcut is only active in vim mode
            show_in_footer: Whether to show in footer
        """
        self.shortcuts[key] = Shortcut(
            key=key,
            action=action,
            description=description,
            category=category,
            vim_mode=vim_mode,
            show_in_footer=show_in_footer,
        )

    def get_bindings(self) -> List[Binding]:
        """Get Textual bindings for active shortcuts.

        Returns:
            List of Binding objects
        """
        bindings = []
        for shortcut in self.shortcuts.values():
            # Skip vim-only shortcuts if not in vim mode
            if shortcut.vim_mode and not self.vim_mode:
                continue

            # Skip non-vim shortcuts in vim mode if they conflict
            if self.vim_mode and not shortcut.vim_mode and shortcut.key in "hjkl":
                continue

            bindings.append(
                Binding(
                    key=shortcut.key,
                    action=shortcut.action,
                    description=shortcut.description,
                    show=shortcut.show_in_footer,
                )
            )
        return bindings

    def get_shortcuts_by_category(self) -> Dict[str, List[Shortcut]]:
        """Get shortcuts grouped by category.

        Returns:
            Dictionary mapping categories to shortcuts
        """
        categorized: Dict[str, List[Shortcut]] = {}
        for shortcut in self.shortcuts.values():
            # Skip vim-only shortcuts if not in vim mode
            if shortcut.vim_mode and not self.vim_mode:
                continue

            if shortcut.category not in categorized:
                categorized[shortcut.category] = []
            categorized[shortcut.category].append(shortcut)

        # Sort shortcuts within each category
        for shortcuts in categorized.values():
            shortcuts.sort(key=lambda s: s.key)

        return categorized

    def toggle_vim_mode(self) -> bool:
        """Toggle vim mode on/off.

        Returns:
            New vim mode state
        """
        self.vim_mode = not self.vim_mode
        return self.vim_mode

    def is_vim_shortcut(self, key: str) -> bool:
        """Check if a key is a vim-mode shortcut.

        Args:
            key: Key to check

        Returns:
            True if the key is a vim-mode shortcut
        """
        shortcut = self.shortcuts.get(key)
        return shortcut is not None and shortcut.vim_mode

    def get_help_text(self) -> str:
        """Generate help text for all shortcuts.

        Returns:
            Formatted help text
        """
        lines = ["# Keyboard Shortcuts", ""]

        if self.vim_mode:
            lines.append("🔹 Vim Mode: ON")
        else:
            lines.append("🔸 Vim Mode: OFF")
        lines.append("")

        categorized = self.get_shortcuts_by_category()
        for category, shortcuts in categorized.items():
            lines.append(f"## {category}")
            lines.append("")

            for shortcut in shortcuts:
                key_display = shortcut.key.replace("ctrl+", "^")
                lines.append(f"  {key_display:<15} {shortcut.description}")

            lines.append("")

        return "\n".join(lines)
