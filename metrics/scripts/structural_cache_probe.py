"""Probe: extraction vs derivation cost for whole-program structural metrics.

Context (2026-07-04): written while designing the caching strategy for
directory-wide metrics (Module Tree Shape, import layering, dependency
cycles — docs/design/structural-metrics-caching.md). The strategy splits
every structural metric into a per-file EXTRACTION (parse imports — cacheable
in the existing content-addressed store) and a whole-program DERIVATION
(assemble graph, count fan-out, find strongly connected components —
recomputed each run). This probe measures both halves on real corpora to
verify the claim that derivation is orders of magnitude cheaper than
extraction, i.e. that caching extraction alone makes warm structural runs
effectively free.

Run: venv/bin/python metrics/scripts/structural_cache_probe.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import time


def extract_imports(source: str) -> list[str]:
    """Layer 1 (per-file, content-pure): raw imported module names.

    Deliberately UNRESOLVED: relative imports (``from . import x``) resolve
    differently depending on the file's location, so resolution belongs to
    the derivation layer — extraction must stay path-independent to be
    content-addressable (same lesson as the complexipy file_name leak).
    """
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            names.append(prefix + (node.module or ""))
    return names


def assemble_and_scc(
    facts: dict[str, list[str]], module_of: dict[str, str]
) -> tuple[int, int, int]:
    """Layer 2 (whole-program, cheap): graph assembly + Tarjan SCC."""
    known = set(module_of.values())
    graph: dict[str, set[str]] = {m: set() for m in known}
    edge_count = 0
    for path, imports in facts.items():
        source_module = module_of[path]
        for target in imports:
            resolved = target.lstrip(".")
            while resolved and resolved not in known:
                resolved = resolved.rpartition(".")[0]
            if resolved and resolved != source_module and resolved not in graph[source_module]:
                graph[source_module].add(resolved)
                edge_count += 1

    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    scc_sizes: list[int] = []

    def strongconnect(node: str) -> None:
        indices[node] = lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for neighbor in graph[node]:
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[node] = min(lowlink[node], indices[neighbor])
        if lowlink[node] == indices[node]:
            size = 0
            while True:
                member = stack.pop()
                on_stack.discard(member)
                size += 1
                if member == node:
                    break
            scc_sizes.append(size)

    import sys

    sys.setrecursionlimit(100_000)
    for node in graph:
        if node not in indices:
            strongconnect(node)

    cycles = sum(1 for size in scc_sizes if size > 1)
    return len(graph), edge_count, cycles


def main() -> None:
    corpora = {
        "antipasta src": (Path("src"), sorted(Path("src/antipasta").rglob("*.py"))),
        "bench corpus": (
            Path("/tmp/antipasta-bench"),
            sorted(Path("/tmp/antipasta-bench").rglob("*.py")),
        ),
    }
    for label, (root, files) in corpora.items():
        if not files:
            print(f"{label}: corpus missing, skipped")
            continue
        sources = {str(p): p.read_text(errors="replace") for p in files}
        module_of = {
            str(p): str(p.relative_to(root).with_suffix("")).replace("/", ".") for p in files
        }

        t = time.perf_counter()
        facts = {path: extract_imports(source) for path, source in sources.items()}
        t_extract = time.perf_counter() - t

        t = time.perf_counter()
        iterations = 50
        for _ in range(iterations):
            nodes, edges, cycles = assemble_and_scc(facts, module_of)
        t_derive = (time.perf_counter() - t) / iterations

        ratio = t_extract / t_derive if t_derive else float("inf")
        print(
            f"{label}: {len(files)} files | extraction (parse): {t_extract * 1000:.1f} ms"
            f" | derivation (assemble+SCC): {t_derive * 1000:.2f} ms"
            f" | ratio: {ratio:.0f}x | graph: {nodes} nodes, {edges} edges, {cycles} cycles"
        )


if __name__ == "__main__":
    main()
