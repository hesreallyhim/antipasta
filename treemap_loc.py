#!/usr/bin/env python3
"""
Interactive treemap of a Python codebase by lines of code (Radon).

- Hierarchy: dir → subdir → ... → filename
- Metric: --metric {sloc,loc,lloc}  (default: sloc)
- Saves/opens an interactive HTML: treemap_loc.html

Requires:  pip install plotly pandas radon
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.io as pio
from radon.raw import analyze as radon_analyze  # SLOC/LOC/LLOC, comments, blanks, etc.

DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    ".eggs",
    "dist",
    "build",
}
PY_SUFFIXES = {".py"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate an interactive treemap of a Python tree by lines of code (Radon)."
    )
    p.add_argument("--root", type=str, default=".", help="Root directory to scan (default: .)")
    p.add_argument(
        "--metric",
        type=str,
        default="sloc",
        choices=["sloc", "loc", "lloc"],
        help="Radon metric to visualize (default: sloc)",
    )
    p.add_argument(
        "--min-lines",
        type=int,
        default=0,
        help="Ignore files with metric below this value (default: 0).",
    )
    p.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="Directory or file *names* to exclude (exact name match).",
    )
    p.add_argument(
        "--follow-symlinks", action="store_true", help="Follow symlinks (off by default)."
    )
    p.add_argument(
        "--max-depth", type=int, default=0, help="Max directory depth to include (0 = unlimited)."
    )
    p.add_argument("--output", type=str, default="treemap_loc.html", help="Output HTML path.")
    return p.parse_args()


def iter_python_files(
    root: Path,
    *,
    excludes: set[str],
    follow_symlinks: bool,
    max_depth: int,
) -> Iterable[tuple[Path, int]]:
    """Yield (file_path, depth) for Python files under root with filters applied."""
    root = root.resolve()
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    name = entry.name
                    if name in excludes:
                        continue
                    try:
                        if entry.is_symlink() and not follow_symlinks:
                            continue
                        if entry.is_dir(follow_symlinks=follow_symlinks):
                            if max_depth == 0 or depth + 1 < max_depth:
                                stack.append((Path(entry.path), depth + 1))
                        elif (
                            entry.is_file(follow_symlinks=follow_symlinks)
                            and Path(name).suffix in PY_SUFFIXES
                        ):
                            yield (Path(entry.path), depth)
                    except OSError:
                        continue
        except (NotADirectoryError, PermissionError, FileNotFoundError):
            continue


def metric_from_radon(text: str, which: str) -> int:
    """
    Compute raw metrics using radon.raw.analyze and select one of:
      - 'loc'  : total lines of code (includes blanks/comments)
      - 'sloc' : source lines of code
      - 'lloc' : logical lines of code
    """
    try:
        rm = radon_analyze(text)
        if which == "loc":
            return int(rm.loc)
        if which == "lloc":
            return int(rm.lloc)
        return int(rm.sloc)
    except Exception:
        return 0


def build_rows(
    root: Path, files: Iterable[tuple[Path, int]], which: str, min_lines: int
) -> pd.DataFrame:
    """Create rows for each Python file and retain directory parts."""
    rows: list[dict[str, Any]] = []

    for fpath, _depth in files:
        try:
            text = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        value = metric_from_radon(text, which)
        if value < min_lines:
            continue
        rel = fpath.relative_to(root)
        parts = list(rel.parts)
        rows.append(
            {
                "parts": parts[:-1],
                "name": parts[-1],
                "value": value,
                "full_path": str(rel),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["name", "value", "full_path"])

    return pd.DataFrame(rows)


def build_tree_dataframe(df: pd.DataFrame, root: Path) -> pd.DataFrame:
    """Create a dataframe suitable for Plotly treemap with directory aggregation."""

    dir_totals: dict[tuple[str, ...], int] = defaultdict(int)
    total_value = int(df["value"].sum())

    for parts, value in zip(df["parts"], df["value"], strict=False):
        for i in range(1, len(parts) + 1):
            dir_totals[tuple(parts[:i])] += int(value)

    root_label = root.name or str(root)
    root_id = root_label or "[root]"

    nodes: list[dict[str, Any]] = [
        {
            "id": root_id,
            "label": root_label or str(root),
            "parent": "",
            "value": total_value,
            "full_path": ".",
            "is_dir": True,
        }
    ]

    for path_tuple, value in sorted(dir_totals.items()):
        node_id = "/".join(path_tuple)
        parent_id = root_id if len(path_tuple) == 1 else "/".join(path_tuple[:-1])
        nodes.append(
            {
                "id": node_id,
                "label": path_tuple[-1],
                "parent": parent_id,
                "value": value,
                "full_path": node_id,
                "is_dir": True,
            }
        )

    for _, row in df.iterrows():
        parts = row["parts"]
        parent_id = root_id if not parts else "/".join(parts)
        nodes.append(
            {
                "id": row["full_path"],
                "label": row["name"],
                "parent": parent_id,
                "value": int(row["value"]),
                "full_path": row["full_path"],
                "is_dir": False,
            }
        )

    return pd.DataFrame(nodes)


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: root not found or not a directory: {root}", file=sys.stderr)
        return 2

    excludes = set(args.exclude) | DEFAULT_EXCLUDES

    py_files = list(
        iter_python_files(
            root,
            excludes=excludes,
            follow_symlinks=args.follow_symlinks,
            max_depth=args.max_depth,
        )
    )
    df = build_rows(root, py_files, which=args.metric, min_lines=args.min_lines)

    if df.empty:
        print("No Python files matched the criteria.", file=sys.stderr)
        return 1

    tree_df = build_tree_dataframe(df, root)

    title_metric = args.metric.upper()
    fig = px.treemap(
        tree_df,
        ids="id",
        names="label",
        parents="parent",
        values="value",
        branchvalues="total",
        hover_data={"full_path": True, "is_dir": True},
        title=f"Python {title_metric} Treemap — {root}",
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>path=%{customdata[0]}<br>"
        + title_metric
        + "=%{value}<extra></extra>"
    )

    out_path = Path(args.output).resolve()
    pio.write_html(fig, file=str(out_path), auto_open=True, include_plotlyjs="cdn")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
