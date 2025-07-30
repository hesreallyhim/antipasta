"""Interactive file tree widget for terminal dashboard."""

from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Tree
from textual.widgets.tree import TreeNode

from code_cop.core.violations import FileReport


class FileSelected(Message):
    """Message sent when a file is selected in the tree."""

    def __init__(self, file_path: str, report: Optional[FileReport] = None) -> None:
        """Initialize the message.

        Args:
            file_path: Path to the selected file
            report: FileReport if available
        """
        super().__init__()
        self.file_path = file_path
        self.report = report


class FileTreeWidget(Widget):
    """Interactive file tree with complexity indicators."""

    COMPONENT_CLASSES = {"file-tree-widget"}

    BINDINGS = [
        Binding("enter", "select_node", "Select", show=True),
        Binding("space", "toggle_node", "Expand/Collapse", show=False),
        Binding("/", "search", "Search"),
        Binding("n", "next_match", "Next match", show=False),
        Binding("N", "prev_match", "Previous match", show=False),
    ]

    tree_data: reactive[dict[str, Any]] = reactive({})
    search_query: reactive[str] = reactive("")

    def __init__(self, tree_data: Optional[dict[str, Any]] = None, **kwargs: Any) -> None:
        """Initialize the file tree widget.

        Args:
            tree_data: Hierarchical tree data from DashboardDataBridge
        """
        super().__init__(**kwargs)
        if tree_data:
            self.tree_data = tree_data
        self._tree: Optional[Tree[dict[str, Any]]] = None
        self._search_matches: list[TreeNode[dict[str, Any]]] = []
        self._current_match_index = 0

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with ScrollableContainer():
            tree = Tree[dict[str, Any]]("Project Files")
            tree.show_root = True  # Show root to ensure content is visible
            tree.guide_depth = 3
            tree.auto_expand = False  # Don't auto-expand on selection
            self._tree = tree
            yield tree

    def on_mount(self) -> None:
        """Initialize the tree when mounted."""
        if self.tree_data:
            self._populate_tree()

    def watch_tree_data(self, old_data: dict[str, Any], new_data: dict[str, Any]) -> None:
        """React to tree data changes."""
        if self._tree and new_data:
            self._populate_tree()

    def _populate_tree(self) -> None:
        """Populate the tree with file data."""
        if not self._tree or not self.tree_data:
            return

        # Clear existing tree
        self._tree.clear()

        # Add root node
        root = self._tree.root
        root.data = self.tree_data
        root.set_label("📁 Project Files")

        # Check if we have any children (files/folders)
        if not self.tree_data.get("children"):
            # No files found - show helpful message
            root.add_leaf("📭 No Python/JS/TS files found")
            root.add_leaf("")
            root.add_leaf("This could be because:")
            root.add_leaf("• The directory has no .py/.js/.ts files")
            root.add_leaf("• All files are in ignored directories")
            root.add_leaf("  (node_modules, venv, __pycache__, etc.)")
            root.add_leaf("• You're in the wrong directory")
            root.add_leaf("")
            root.add_leaf("Try running from a project root with")
            root.add_leaf("Python, JavaScript, or TypeScript files")
            return

        # Recursively add nodes directly to root's children
        children = self.tree_data.get("children", {})

        # Sort children: directories first, then files
        sorted_children = sorted(
            children.items(),
            key=lambda x: (x[1]["type"] != "directory", x[0].lower()),
        )

        for name, child_data in sorted_children:
            label = self._create_node_label(name, child_data)

            if child_data["type"] == "directory":
                child_node = root.add(label, data=child_data, allow_expand=True)
                if child_data.get("children"):
                    self._add_tree_nodes(child_node, child_data)
            else:
                # Files should not be expandable
                child_node = root.add_leaf(label, data=child_data)

        # Expand the first few levels
        root.expand()
        self._expand_to_depth(root, 1)

    def _add_tree_nodes(self, parent: TreeNode[dict[str, Any]], node_data: dict[str, Any]) -> None:
        """Recursively add nodes to the tree."""
        if node_data["type"] == "directory" and "children" in node_data:
            # Sort children: directories first, then files
            children = sorted(
                node_data["children"].items(),
                key=lambda x: (x[1]["type"] != "directory", x[0].lower()),
            )

            for name, child_data in children:
                label = self._create_node_label(name, child_data)

                if child_data["type"] == "directory":
                    child_node = parent.add(label, data=child_data, allow_expand=True)
                    if child_data.get("children"):
                        self._add_tree_nodes(child_node, child_data)
                    else:
                        # Empty directory
                        child_node.add_leaf("(empty)")
                else:
                    # Files should not be expandable
                    parent.add_leaf(label, data=child_data)

    def _create_node_label(self, name: str, node_data: dict[str, Any]) -> str:
        """Create a label for a tree node with indicators."""
        if node_data["type"] == "directory":
            return f"📁 {name}"
        else:
            # File with complexity indicator
            complexity = node_data.get("complexity", 0)
            violations = node_data.get("violations", 0)

            # Choose indicator based on complexity
            if complexity > 20:
                indicator = "🔴"
            elif complexity > 10:
                indicator = "🟠"
            elif complexity > 5:
                indicator = "🟡"
            else:
                indicator = "🟢"

            # Add violation count if any
            suffix = f" ({violations}❗)" if violations > 0 else ""

            return f"📄 {name} {indicator}{suffix}"

    def _expand_to_depth(self, node: TreeNode[dict[str, Any]], depth: int) -> None:
        """Expand tree nodes up to a certain depth."""
        if depth <= 0:
            return

        node.expand()
        for child in node.children:
            if child.allow_expand:
                self._expand_to_depth(child, depth - 1)

    def action_select_node(self) -> None:
        """Handle node selection."""
        if not self._tree:
            return

        node = self._tree.cursor_node
        if node and node.data:
            self.app.log.info(f"Selected node: {node.data.get('name')}, type: {node.data.get('type')}")

            if node.data["type"] == "file":
                # Emit file selected message
                report = node.data.get("report")
                # Use relative path if available, otherwise fall back to name
                file_path = node.data.get("relative_path") or node.data.get("path") or node.data.get("name", "")
                self.post_message(FileSelected(file_path, report))
            elif node.data["type"] == "directory":
                # Toggle expand/collapse
                self.app.log.info(f"Toggling directory: {node.data.get('name')}")
                node.toggle()
            else:
                # Root node or other
                node.toggle()

    def action_toggle_node(self) -> None:
        """Toggle node expansion."""
        if not self._tree:
            return

        node = self._tree.cursor_node
        if node and node.allow_expand:
            node.toggle()

    def action_search(self) -> None:
        """Initiate search mode."""
        # TODO: Implement search dialog
        self.app.notify("Search not yet implemented")

    def action_next_match(self) -> None:
        """Navigate to next search match."""
        if not self._search_matches:
            return

        self._current_match_index = (self._current_match_index + 1) % len(self._search_matches)
        match_node = self._search_matches[self._current_match_index]

        if self._tree:
            self._tree.cursor_line = match_node.line
            self._tree.scroll_to_node(match_node)

    def action_prev_match(self) -> None:
        """Navigate to previous search match."""
        if not self._search_matches:
            return

        self._current_match_index = (self._current_match_index - 1) % len(self._search_matches)
        match_node = self._search_matches[self._current_match_index]

        if self._tree:
            self._tree.cursor_line = match_node.line
            self._tree.scroll_to_node(match_node)

    def update_tree_data(self, tree_data: dict[str, Any]) -> None:
        """Update the tree with new data."""
        self.tree_data = tree_data
