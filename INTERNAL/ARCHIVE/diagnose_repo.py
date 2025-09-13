#!/usr/bin/env python3
"""Diagnose why a repository might not show files in antipasta TUI."""

from pathlib import Path
import sys
from antipasta.terminal.data_bridge import DashboardDataBridge


def diagnose_repository(repo_path: str = "."):
    """Diagnose repository for antipasta compatibility."""
    path = Path(repo_path).absolute()
    print(f"Diagnosing repository: {path}")
    print("=" * 70)

    # Check if path exists and is a directory
    if not path.exists():
        print(f"❌ ERROR: Path does not exist!")
        return

    if not path.is_dir():
        print(f"❌ ERROR: Path is not a directory!")
        return

    print("✅ Path exists and is a directory")

    # List all files and directories
    all_items = list(path.iterdir())
    dirs = [d for d in all_items if d.is_dir()]
    files = [f for f in all_items if f.is_file()]

    print(f"\nRepository contents:")
    print(f"  Directories: {len(dirs)}")
    print(f"  Files: {len(files)}")

    # Show some directories
    if dirs:
        print(f"\n  Sample directories:")
        for d in sorted(dirs)[:10]:
            print(f"    {'.' if d.name.startswith('.') else ' '} {d.name}/")

    # Check for supported file types
    print(f"\nSearching for supported file types...")

    bridge = DashboardDataBridge(repo_path)
    collected_files = bridge.collect_files()

    print(f"\nFiles collected by antipasta: {len(collected_files)}")

    if collected_files:
        print("\nSample files found:")
        for f in collected_files[:10]:
            print(f"  - {f.relative_to(path)}")
    else:
        print("\n❌ No supported files found!")

        # Check what files exist in the repo
        all_extensions = set()
        for item in path.rglob("*"):
            if item.is_file() and item.suffix:
                all_extensions.add(item.suffix)

        if all_extensions:
            print(f"\nFile extensions found in repository:")
            for ext in sorted(all_extensions)[:20]:
                count = len(list(path.rglob(f"*{ext}")))
                print(f"  {ext}: {count} files")

        print(f"\nantipasta currently supports:")
        print("  - Python: .py")
        print("  - JavaScript: .js, .jsx, .mjs, .cjs")
        print("  - TypeScript: .ts, .tsx")
        print("  - Vue: .vue")
        print("  - Svelte: .svelte")

    # Test tree generation
    print(f"\nGenerating file tree...")
    tree_data = bridge.get_file_tree()

    if tree_data.get("children"):
        print("✅ Tree data generated successfully")
        print(f"   Root has {len(tree_data['children'])} children")
    else:
        print("❌ Tree has no children - this is why the TUI shows empty")

    # Show analysis results
    print(f"\nRunning analysis...")
    reports, summary = bridge.analyze_all()
    print(f"  Reports generated: {len(reports)}")
    print(f"  Analysis summary: {summary.get('total_files', 0)} files")


if __name__ == "__main__":
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    diagnose_repository(repo_path)
