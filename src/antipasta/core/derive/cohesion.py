"""Class-cohesion analyzers: lack of cohesion, coupling between objects.

Lack of cohesion uses the connected-components formulation (LCOM4 in the
literature): methods are nodes, connected when they share a field or one
calls the other; the value is the number of components — directly readable
as "this class is N classes wearing one name." Dunder methods other than
``__init__`` are excluded (protocol plumbing, not responsibilities);
``__init__`` is included because field initialization is what connects
responsibilities to their state.

Coupling between objects is a labeled approximation (rows carry
``approximate: true``): the distinct imported names a class body references.
Full precision needs type resolution Python does not offer statically.
"""

from __future__ import annotations

import ast
from typing import Any


def lack_of_cohesion(methods: list[dict[str, Any]]) -> int:
    """Connected components over a class's methods (0 for method-less classes)."""
    considered = [m for m in methods if _is_considered(m["name"])]
    if not considered:
        return 0
    names = [method["name"] for method in considered]
    parent = {name: name for name in names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    _connect_shared_fields(considered, union)
    _connect_local_calls(considered, names, union)
    return len({find(name) for name in names})


def _is_considered(method_name: str) -> bool:
    is_dunder = method_name.startswith("__") and method_name.endswith("__")
    return not is_dunder or method_name == "__init__"


def _connect_shared_fields(methods: list[dict[str, Any]], union: Any) -> None:
    by_field: dict[str, str] = {}
    for method in methods:
        for field_name in [*method["fields_read"], *method["fields_written"]]:
            if field_name in by_field:
                union(method["name"], by_field[field_name])
            else:
                by_field[field_name] = method["name"]


def _connect_local_calls(methods: list[dict[str, Any]], names: list[str], union: Any) -> None:
    name_set = set(names)
    for method in methods:
        for callee in method["calls_local"]:
            if callee in name_set:
                union(method["name"], callee)


def coupling_between_objects(class_node: ast.ClassDef, imported_names: frozenset[str]) -> int:
    """Distinct imported names the class body references (approximation)."""
    referenced: set[str] = set()
    for node in ast.walk(class_node):
        if isinstance(node, ast.Name) and node.id in imported_names:
            referenced.add(node.id)
    return len(referenced)


def imported_name_set(module: ast.Module) -> frozenset[str]:
    """Top-level names bound by imports (the coupling vocabulary)."""
    names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)
