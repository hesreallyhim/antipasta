#!/usr/bin/env python3
"""Test folder expansion issue in TUI."""

from pathlib import Path
from code_cop.terminal.data_bridge import DashboardDataBridge

# Test the data bridge directly
bridge = DashboardDataBridge(".")
files = bridge.collect_files()
print(f"Files collected: {len(files)}")

# Analyze
reports, summary = bridge.analyze_all()
print(f"Reports: {len(reports)}")
print(f"Summary: {summary}")

# Get tree
tree = bridge.get_file_tree()
print(f"\nTree root has {len(tree.get('children', {}))} children")

# Check first directory
for name, child in list(tree.get('children', {}).items())[:3]:
    print(f"\n{name}:")
    print(f"  Type: {child.get('type')}")
    print(f"  Has children: {'children' in child}")
    if child.get('type') == 'directory':
        print(f"  Number of children: {len(child.get('children', {}))}")