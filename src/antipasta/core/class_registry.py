"""Cross-file class registry: inheritance depth and children counts.

A deriver over the class and import facts: resolves base-class names across
the analyzed set (same-module names directly; imported names via the raw
import facts) and emits, per class, depth-of-inheritance-tree and
number-of-children rows. Unresolved bases (external libraries) contribute
one level of depth and are labeled in details — an approximation, honestly
marked, consistent with the coupling rows.

Depth convention: a class with no bases (or only ``object``) has depth 1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antipasta.core.derivation import DerivationInput
from antipasta.core.metrics import MetricResult, MetricType
from antipasta.core.violations import ProjectReport

_IMPLICIT_ROOTS = frozenset({"object"})
_MAX_DEPTH_GUARD = 64  # cycle backstop; real hierarchies never get close


def derive_class_registry(derivation_input: DerivationInput) -> list[ProjectReport]:
    """One ProjectReport per class: inheritance depth + children count."""
    registry = _build_registry(derivation_input)
    if not registry:
        return []
    children = _count_children(registry)
    reports = []
    for qualified_name in sorted(registry):
        entry = registry[qualified_name]
        depth, unresolved = _depth_of(qualified_name, registry, set())
        reports.append(
            _class_report(qualified_name, entry, depth, unresolved, children)
        )
    return reports


def _build_registry(derivation_input: DerivationInput) -> dict[str, dict[str, Any]]:
    """qualified class name ("module::Class") → class entry with resolvable bases."""
    root = derivation_input.root
    registry: dict[str, dict[str, Any]] = {}
    for file_path, facts in derivation_input.facts_by_file.items():
        module = _module_of(file_path, root)
        if module is None:
            continue
        local_imports = _imported_name_targets(facts)
        for fact in facts:
            if fact.kind != "class":
                continue
            registry[f"{module}::{fact.payload['name']}"] = {
                "module": module,
                "name": fact.payload["name"],
                "lineno": fact.payload["lineno"],
                "bases": fact.payload["bases"],
                "imports": local_imports,
            }
    return registry


def _module_of(file_path: Path, root: Path) -> str | None:
    try:
        relative = file_path.resolve().relative_to(root)
    except ValueError:
        return None
    return str(relative.with_suffix("")).replace("/", ".")


def _imported_name_targets(facts: list[Any]) -> dict[str, str]:
    """Locally bound name → dotted source it came from (raw, unresolved)."""
    targets: dict[str, str] = {}
    for fact in facts:
        if fact.kind != "import":
            continue
        payload = fact.payload
        if payload["names"]:
            prefix = ("." * payload["level"]) + payload["module"]
            for name in payload["names"]:
                targets[name] = f"{prefix}.{name}" if prefix else name
        elif payload["module"]:
            targets[payload["module"].split(".")[0]] = payload["module"]
    return targets


def _resolve_base(
    base: str, entry: dict[str, Any], registry: dict[str, dict[str, Any]]
) -> str | None:
    """Resolve a raw base expression to a registry key, or None if external."""
    simple = base.split("[")[0].strip()  # Generic[...] -> Generic
    same_module = f"{entry['module']}::{simple}"
    if same_module in registry:
        return same_module
    imported = entry["imports"].get(simple.split(".")[0])
    if imported is not None:
        # Suffix match against analyzed modules: "pkg.mod" endswith import tail.
        class_name = simple.split(".")[-1]
        source = imported.lstrip(".")
        for key, candidate in registry.items():
            if candidate["name"] == class_name and candidate["module"].endswith(
                source.rsplit(".", 1)[0] if "." in source else source
            ):
                return key
    return None


def _depth_of(
    qualified_name: str, registry: dict[str, dict[str, Any]], visiting: set[str]
) -> tuple[int, bool]:
    """(inheritance depth, any-base-unresolved). Cycle-safe."""
    if qualified_name in visiting or len(visiting) > _MAX_DEPTH_GUARD:
        return 1, True  # cycle: report shallow, flagged
    entry = registry[qualified_name]
    bases = [base for base in entry["bases"] if base not in _IMPLICIT_ROOTS]
    if not bases:
        return 1, False
    depths = []
    unresolved = False
    for base in bases:
        resolved = _resolve_base(base, entry, registry)
        if resolved is None:
            depths.append(2)  # external parent: one level below an unknown root
            unresolved = True
        else:
            parent_depth, parent_unresolved = _depth_of(
                resolved, registry, visiting | {qualified_name}
            )
            depths.append(parent_depth + 1)
            unresolved = unresolved or parent_unresolved
    return max(depths), unresolved


def _count_children(registry: dict[str, dict[str, Any]]) -> dict[str, int]:
    children: dict[str, int] = dict.fromkeys(registry, 0)
    for key, entry in registry.items():
        for base in entry["bases"]:
            if base in _IMPLICIT_ROOTS:
                continue
            resolved = _resolve_base(base, entry, registry)
            if resolved is not None and resolved != key:
                children[resolved] += 1
    return children


def _class_report(
    qualified_name: str,
    entry: dict[str, Any],
    depth: int,
    unresolved: bool,
    children: dict[str, int],
) -> ProjectReport:
    subject_path = Path(entry["module"].replace(".", "/") + ".py")
    details = {"approximate": True} if unresolved else None
    rows = [
        MetricResult(
            file_path=subject_path,
            metric_type=MetricType.DEPTH_OF_INHERITANCE_TREE,
            value=float(depth),
            line_number=entry["lineno"],
            function_name=entry["name"],
            details=details,
        ),
        MetricResult(
            file_path=subject_path,
            metric_type=MetricType.NUMBER_OF_CHILDREN,
            value=float(children[qualified_name]),
            line_number=entry["lineno"],
            function_name=entry["name"],
        ),
    ]
    return ProjectReport(subject=qualified_name, metrics=rows, violations=[])
