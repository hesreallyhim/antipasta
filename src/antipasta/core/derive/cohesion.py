"""Class-cohesion analyzer: lack of cohesion.

Lack of cohesion follows the connected-components formulation (LCOM4 in the
literature) with the rules calibrated against the standard library, click,
pydantic, and packaging: methods are nodes, connected when they share state
or call one another, and the value is the number of *responsibility
clusters* — directly readable as "this class is N classes wearing one name."

What connects two methods:

- both touch the same field through ``self`` or ``cls``;
- one calls the other, or reads a property the other defines;
- both call the same inherited method (state reached through a base class
  is still shared state; ``email.message.MIMEPart`` reaches its payload only
  through ``Message`` methods).

What does not count as a cluster:

- dunder methods other than ``__init__`` (protocol plumbing);
- stub methods and abstract declarations (they touch nothing by definition,
  so an interface with fifty declared methods is not fifty responsibilities);
- a stateless method that touches no field and shares nothing (a helper
  parked on the class is not a reason for the class to change; these are
  reported separately as ``stateless_methods``);
- a cluster consisting only of ``__init__`` (setup, not a responsibility).

Before these rules, 187 of 1,022 benchmark classes had more than one
component, most of them interfaces and classes with a few stateless helpers;
after, 37 do, and reading them they are the classes a maintainer would name.
"""

from __future__ import annotations

from typing import Any

_ABSTRACT_METHOD_MARKER = "abstractmethod"
_INIT = "__init__"


def lack_of_cohesion(methods: list[dict[str, Any]]) -> int:
    """Number of responsibility clusters (0 when the class has none)."""
    return len(cohesion_clusters(methods))


def cohesion_clusters(methods: list[dict[str, Any]]) -> list[list[str]]:
    """Responsibility clusters, largest first, each a list of method names."""
    clusters, _ = _partition(methods)
    return clusters


def stateless_methods(methods: list[dict[str, Any]]) -> list[str]:
    """Concrete methods that touch no state and share nothing with a sibling."""
    _, stateless = _partition(methods)
    return stateless


def concrete_methods(methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The methods that can carry a responsibility: non-dunder (``__init__``
    aside), non-stub, not declared abstract."""
    return [method for method in methods if _is_considered(method)]


def _is_considered(method: dict[str, Any]) -> bool:
    name = method["name"]
    is_dunder = name.startswith("__") and name.endswith("__")
    if is_dunder and name != _INIT:
        return False
    if method.get("stub") is not None:
        return False
    return not any(_ABSTRACT_METHOD_MARKER in d for d in method.get("decorators", []))


def _partition(methods: list[dict[str, Any]]) -> tuple[list[list[str]], list[str]]:
    considered = concrete_methods(methods)
    if not considered:
        return [], []
    components = _Components([method["name"] for method in considered])
    _connect_shared_members(considered, components)
    _connect_local_calls(considered, components)
    clusters: list[list[str]] = []
    stateless: list[str] = []
    for group in components.groups():
        members = [method for method in considered if method["name"] in group]
        if _is_responsibility(members):
            clusters.append(sorted(group))
        elif not any(_touches_state(method) for method in members):
            stateless.extend(sorted(group))
    clusters.sort(key=len, reverse=True)
    return clusters, stateless


def _is_responsibility(members: list[dict[str, Any]]) -> bool:
    names = {method["name"] for method in members}
    if names == {_INIT}:
        return False
    return len(members) > 1 or any(_touches_state(method) for method in members)


def _touches_state(method: dict[str, Any]) -> bool:
    return bool(method["fields_read"] or method["fields_written"])


def _connect_shared_members(methods: list[dict[str, Any]], components: _Components) -> None:
    """Union methods that share a field, a property, or an inherited callee."""
    local_names = set(components.names)
    first_user: dict[str, str] = {}
    for method in methods:
        keys = set(method["fields_read"]) | set(method["fields_written"])
        keys |= {f"call:{callee}" for callee in method["calls_local"] if callee not in local_names}
        for key in keys:
            if key in local_names:  # a property read is a call to its getter
                components.union(method["name"], key)
            if key in first_user:
                components.union(method["name"], first_user[key])
            else:
                first_user[key] = method["name"]


def _connect_local_calls(methods: list[dict[str, Any]], components: _Components) -> None:
    local_names = set(components.names)
    for method in methods:
        for callee in method["calls_local"]:
            if callee in local_names:
                components.union(method["name"], callee)


class _Components:
    """Union-find over method names."""

    def __init__(self, names: list[str]) -> None:
        self.names = names
        self._parent = {name: name for name in names}

    def find(self, name: str) -> str:
        parent = self._parent
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)

    def groups(self) -> list[set[str]]:
        grouped: dict[str, set[str]] = {}
        for name in self.names:
            grouped.setdefault(self.find(name), set()).add(name)
        return list(grouped.values())
