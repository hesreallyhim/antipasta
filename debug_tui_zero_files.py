#!/usr/bin/env python3
"""Debug why TUI shows 0 files."""

from pathlib import Path
from code_cop.terminal.data_bridge import DashboardDataBridge
from code_cop.core.config import CodeCopConfig
from code_cop.core.detector import LanguageDetector

print("=== Debugging TUI Zero Files Issue ===\n")

# Test 1: Direct file collection
print("1. Testing data bridge file collection:")
bridge = DashboardDataBridge(".")
files = bridge.collect_files()
print(f"   Data bridge found: {len(files)} files")
if files:
    print(f"   First few: {[str(f.name) for f in files[:3]]}")

# Test 2: Check config
print("\n2. Testing config:")
config = bridge.config
print(f"   use_gitignore: {config.use_gitignore}")
print(f"   ignore_patterns: {config.ignore_patterns}")

# Test 3: Test the CLI's file collection method
print("\n3. Testing CLI file collection (like metrics command):")
detector = LanguageDetector(ignore_patterns=config.ignore_patterns)
if config.use_gitignore:
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        detector.add_gitignore(gitignore_path)
        print("   Loaded .gitignore")

# Collect files like the CLI does
patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
cli_files = []
for pattern in patterns:
    for f in Path(".").glob(pattern):
        if not detector.should_ignore(f):
            cli_files.append(f)
print(f"   CLI method found: {len(cli_files)} files")
if cli_files:
    print(f"   First few: {[str(f.name) for f in cli_files[:3]]}")

# Test 4: Direct glob without filtering
print("\n4. Testing raw glob:")
raw_py_files = list(Path(".").glob("**/*.py"))
print(f"   Raw glob found: {len(raw_py_files)} .py files")

# Test 5: Check analysis
print("\n5. Testing analysis:")
if files:
    reports, summary = bridge.analyze_all()
    print(f"   Analysis reports: {len(reports)}")
    print(f"   Summary total_files: {summary.get('total_files', 0)}")
else:
    print("   No files to analyze!")

# Test 6: Check if the issue is in the UI update
print("\n6. Checking metrics summary:")
if files:
    metrics_summary = bridge.get_metrics_summary()
    print(f"   Metrics summary: {metrics_summary}")