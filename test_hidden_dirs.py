#!/usr/bin/env python3
"""Test script to check file discovery including hidden directories."""

import sys
from pathlib import Path


def test_file_discovery(project_path: str) -> None:
    """Test file discovery with different approaches."""
    path = Path(project_path).absolute()
    print(f"Testing file discovery in: {path}")
    print("=" * 60)

    # List all directories (including hidden)
    all_dirs = list(path.iterdir())
    visible_dirs = [
        d for d in all_dirs if d.is_dir() and not d.name.startswith(".")
    ]
    hidden_dirs = [
        d for d in all_dirs if d.is_dir() and d.name.startswith(".")
    ]

    print("\nDirectory summary:")
    print(f"  Total directories: {len([d for d in all_dirs if d.is_dir()])}")
    print(f"  Visible directories: {len(visible_dirs)}")
    print(f"  Hidden directories: {len(hidden_dirs)}")

    if hidden_dirs:
        print("\nHidden directories found:")
        for d in hidden_dirs[:10]:
            print(f"  - {d.name}")

    # Test different glob patterns
    patterns = ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"]

    print("\nSearching for files with glob (doesn't include hidden dirs):")
    for pattern in patterns:
        files = list(path.glob(f"**/{pattern}"))
        if files:
            print(f"  {pattern}: {len(files)} files")

    print("\nSearching for files with rglob (includes hidden dirs):")
    for pattern in patterns:
        files = list(path.rglob(pattern))
        if files:
            print(f"  {pattern}: {len(files)} files")
            # Show some examples
            for f in files[:3]:
                print(f"    - {f.relative_to(path)}")

    # Check specific hidden directories
    print("\nChecking specific hidden directories for code files:")
    for hidden_dir in hidden_dirs:
        py_files = list(hidden_dir.rglob("*.py"))
        js_files = list(hidden_dir.rglob("*.js"))
        ts_files = list(hidden_dir.rglob("*.ts"))

        total = len(py_files) + len(js_files) + len(ts_files)
        if total > 0:
            print(f"  {hidden_dir.name}: {total} code files")
            if py_files:
                print(f"    Python: {len(py_files)}")
            if js_files:
                print(f"    JavaScript: {len(js_files)}")
            if ts_files:
                print(f"    TypeScript: {len(ts_files)}")


if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    test_file_discovery(project_path)
