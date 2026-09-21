"""Class-cohesion analyzer: lack of cohesion.

Lack of cohesion uses the connected-components formulation (LCOM4 in the
literature): methods are nodes, connected when they share a field or one
calls the other; the value is the number of components — directly readable
as "this class is N classes wearing one name." Dunder methods other than
``__init__`` are excluded (protocol plumbing, not responsibilities);
``__init__`` is included because field initialization is what connects
responsibilities to their state. Stub methods (abstract declarations and
no-op hooks) are excluded too: they touch no state by definition, so an
interface with fifty declared methods is not fifty responsibilities.
"""

from __future__ import annotations

from typing import Any

_ABSTRACT_METHOD_MARKER = "abstractmethod"


def lack_of_cohesion(methods: list[dict[str, Any]]) -> int:
    """Connected components over a class's concrete methods (0 when none)."""
    considered = concrete_methods(methods)
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


def concrete_methods(methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The methods that can carry a responsibility: non-dunder (``__init__``
    aside), non-stub, not declared abstract."""
    return [method for method in methods if _is_considered(method)]


def _is_considered(method: dict[str, Any]) -> bool:
    name = method["name"]
    is_dunder = name.startswith("__") and name.endswith("__")
    if is_dunder and name != "__init__":
        return False
    if method.get("stub") is not None:
        return False
    return not any(_ABSTRACT_METHOD_MARKER in d for d in method.get("decorators", []))


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
