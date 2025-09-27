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
    """
    Construct a dataframe with columns:
      - level_0, level_1, ..., 'name' (leaf filename)
      - value (chosen metric)
      - full_path
    """
    rows: list[dict[str, Any]] = []
    max_parts = 1

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
        max_parts = max(max_parts, len(parts))
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

    # Normalize hierarchy columns
    for i in range(max_parts - 1):  # exclude the file leaf
        for r in rows:
            r[f"level_{i}"] = r["parts"][i] if i < len(r["parts"]) else None

    return pd.DataFrame(rows).drop(columns=["parts"])


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

    level_cols = sorted(
        [c for c in df.columns if c.startswith("level_")], key=lambda c: int(c.split("_")[1])
    )
    path_cols = level_cols + ["name"]

    title_metric = args.metric.upper()
    fig = px.treemap(
        df,
        path=path_cols,
        values="value",
        title=f"Python {title_metric} Treemap — {root}",
        hover_data={"full_path": True, "value": True, **dict.fromkeys(level_cols, False)},
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
