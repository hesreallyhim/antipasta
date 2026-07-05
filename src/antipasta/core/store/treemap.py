"""Treemap node-table construction for the HTML report.

Built in Python on purpose (the mixed-depth-tree fix from
``docs/treemap_loc_fix.md``): the renderer (d3.stratify) must never see a node
whose parent is missing, so this module emits an explicit ``{id, parent,
label}`` table with a single root and every intermediate directory present.
Directory rows additionally carry a hoverable ``aggregate`` rollup (file
count, total tile value, violation count, per-metric subtree maxima) so the
treemap's inner rectangles are data, not just structure.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

#: Root node id used in the treemap node table.
TREEMAP_ROOT_ID = "."


def build_treemap_nodes(
    files: list[dict[str, Any]], *, root_label: str = "root"
) -> list[dict[str, Any]]:
    """Build an explicit treemap node table from per-file snapshot entries.

    Every row is ``{id, parent, label}``; leaf rows additionally carry
    ``value`` (tile area: SLOC, falling back to LOC, falling back to 1) and
    ``file_index`` (index into the snapshot's ``files`` list).  The root node
    has ``parent: None`` and every other node's parent is guaranteed to be
    present in the table — no orphans, no implied directories.
    """
    nodes: list[dict[str, Any]] = [{"id": TREEMAP_ROOT_ID, "parent": None, "label": root_label}]
    known_ids = {TREEMAP_ROOT_ID}
    aggregates: dict[str, dict[str, Any]] = {TREEMAP_ROOT_ID: _empty_aggregate()}

    for index, entry in enumerate(files):
        parts = PurePosixPath(entry["path"]).parts
        parent = TREEMAP_ROOT_ID
        ancestor_ids = [TREEMAP_ROOT_ID]
        for depth in range(len(parts) - 1):
            directory_id = "/".join(parts[: depth + 1])
            if directory_id not in known_ids:
                nodes.append({"id": directory_id, "parent": parent, "label": parts[depth]})
                known_ids.add(directory_id)
                aggregates[directory_id] = _empty_aggregate()
            parent = directory_id
            ancestor_ids.append(directory_id)

        leaf_id = "/".join(parts)
        if leaf_id in known_ids:
            # Duplicate path (should not happen after file de-duplication);
            # skip rather than corrupt the tree.
            continue
        known_ids.add(leaf_id)
        value = _tile_value(entry)
        nodes.append({
            "id": leaf_id,
            "parent": parent,
            "label": parts[-1],
            "value": value,
            "file_index": index,
        })
        for ancestor_id in ancestor_ids:
            _fold_into_aggregate(aggregates[ancestor_id], entry, value)

    for node in nodes:
        aggregate = aggregates.get(node["id"])
        if aggregate is not None:
            node["aggregate"] = aggregate

    return nodes


def _tile_value(entry: dict[str, Any]) -> float:
    """A file's treemap area: SLOC, falling back to LOC, then nloc, then 1."""
    metrics = entry["metrics"]
    value = (
        metrics.get("source_lines_of_code")
        or metrics.get("lines_of_code")
        or metrics.get("nloc")
        or 1.0
    )
    return float(value)


def _empty_aggregate() -> dict[str, Any]:
    return {"files": 0, "value": 0.0, "violations": 0, "metrics_max": {}}


def _fold_into_aggregate(aggregate: dict[str, Any], entry: dict[str, Any], value: float) -> None:
    """Fold one file's snapshot entry into a directory rollup.

    ``metrics_max`` keeps, per metric, the subtree maximum and the file that
    holds it — max is the threshold-meaningful aggregate for a directory.
    """
    aggregate["files"] += 1
    aggregate["value"] += value
    aggregate["violations"] += len(entry.get("violations") or [])
    metrics_max: dict[str, dict[str, Any]] = aggregate["metrics_max"]
    for metric, metric_value in (entry.get("metrics") or {}).items():
        if metric_value is None:
            continue
        current = metrics_max.get(metric)
        if current is None or float(metric_value) > current["value"]:
            metrics_max[metric] = {"value": float(metric_value), "path": entry["path"]}
