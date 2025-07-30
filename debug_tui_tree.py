#!/usr/bin/env python3
"""Debug TUI tree issue."""

import sys
from pathlib import Path
from code_cop.terminal.data_bridge import DashboardDataBridge
import json


def debug_tree_issue(project_path: str = "."):
    """Debug why tree is not showing files."""
    print(f"Debugging TUI tree for: {Path(project_path).absolute()}")
    print("=" * 70)

    # Create data bridge
    bridge = DashboardDataBridge(project_path)

    # Analyze and get tree data
    reports, summary = bridge.analyze_all()
    print(f"\nAnalysis complete:")
    print(f"  Total reports: {len(reports)}")
    print(f"  Total files in summary: {summary.get('total_files', 0)}")

    # Get tree data
    tree_data = bridge.get_file_tree()

    print(f"\nTree data structure:")
    print(f"  Root type: {tree_data.get('type')}")
    print(f"  Root name: {tree_data.get('name')}")
    print(f"  Has children: {'children' in tree_data}")

    if 'children' in tree_data:
        children = tree_data['children']
        print(f"  Number of root children: {len(children)}")

        # Show first few children
        for i, (name, child) in enumerate(list(children.items())[:5]):
            print(f"\n  Child {i+1}:")
            print(f"    Name: {name}")
            print(f"    Type: {child.get('type')}")
            if child.get('type') == 'directory':
                print(f"    Has children: {len(child.get('children', {}))}")
            else:
                print(f"    Complexity: {child.get('complexity')}")
                print(f"    Violations: {child.get('violations')}")

    # Save full tree data for inspection
    with open('debug_tree_data.json', 'w') as f:
        # Convert reports to serializable format
        serializable_tree = json.dumps(tree_data, default=str, indent=2)
        f.write(serializable_tree)

    print(f"\nFull tree data saved to: debug_tree_data.json")


if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    debug_tree_issue(project_path)