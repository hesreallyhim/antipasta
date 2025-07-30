#!/usr/bin/env python3
"""Debug script to test file collection and tree building."""

from pathlib import Path
import sys
from code_cop.terminal.data_bridge import DashboardDataBridge
import json


def debug_file_collection(project_path: str = "."):
    """Debug file collection and tree building."""
    print(f"Analyzing project: {Path(project_path).absolute()}")

    # Create data bridge
    bridge = DashboardDataBridge(project_path)

    # Collect files
    files = bridge.collect_files()
    print(f"\nFound {len(files)} files:")
    for f in files[:10]:  # Show first 10 files
        print(f"  - {f.relative_to(Path(project_path))}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more files")

    # Analyze files
    print("\nAnalyzing files...")
    reports, summary = bridge.analyze_all()
    print(f"Successfully analyzed {len(reports)} files")

    # Get tree data
    print("\nBuilding file tree...")
    tree_data = bridge.get_file_tree()

    # Pretty print tree structure
    def print_tree(node, indent=""):
        if node["type"] == "directory":
            name = node.get("name", "?")
            print(f"{indent}📁 {name}/")
            children = node.get("children", {})
            for child_name, child_data in sorted(children.items()):
                print_tree(child_data, indent + "  ")
        else:
            name = node.get("name", "?")
            complexity = node.get("complexity", 0)
            violations = node.get("violations", 0)
            print(f"{indent}📄 {name} (complexity: {complexity}, violations: {violations})")

    print("\nFile tree structure:")
    print_tree(tree_data)

    # Debug empty tree
    if not tree_data.get("children"):
        print("\n⚠️  WARNING: Tree has no children!")
        print("\nDebugging empty tree:")

        # Check current directory
        print(f"Current directory: {Path.cwd()}")
        print(f"Project path: {Path(project_path).absolute()}")

        # List Python files in directory
        py_files = list(Path(project_path).glob("**/*.py"))
        print(f"\nPython files found: {len(py_files)}")
        for f in py_files[:5]:
            print(f"  - {f}")

        # Check if files are being ignored
        ignore_dirs = {"node_modules", "venv", "__pycache__", ".git", "dist", "build"}
        ignored_count = 0
        for f in py_files:
            if any(part in f.parts for part in ignore_dirs):
                ignored_count += 1
        print(f"Files ignored due to directory filters: {ignored_count}")


if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    debug_file_collection(project_path)