"""Abstractness classification and the Main-Sequence composites.

Per-module abstractness = abstract classes / total classes, where "abstract"
is inferred from static markers (a labeled approximation — Python has no
single abstraction construct): an abstract-base/Protocol base, an ABCMeta
metaclass keyword, or any abstractmethod-decorated member. Modules without
classes get no abstractness row — Robert Martin's A-axis presumes types, and
a pure-function module on the Main Sequence chart would be noise.

Distance from the Main Sequence is |A + I − 1| (instability supplied by the
import graph). Dependency inversion is the mean abstractness of a module's
imported targets — "do my arrows land on abstractions?" — again labeled
approximate.
"""

from __future__ import annotations

from typing import Any

from antipasta.core.metrics import FactRow

_ABSTRACT_BASE_MARKERS = ("ABC", "Protocol")
_ABSTRACT_METACLASS_MARKER = "ABCMeta"
_ABSTRACT_METHOD_MARKER = "abstractmethod"


def module_abstractness(facts: list[FactRow]) -> float | None:
    """Abstract-class ratio for one module; None when it has no classes."""
    class_payloads = [fact.payload for fact in facts if fact.kind == "class"]
    if not class_payloads:
        return None
    abstract = sum(1 for payload in class_payloads if _is_abstract(payload))
    return abstract / len(class_payloads)


def _is_abstract(payload: dict[str, Any]) -> bool:
    if any(_base_is_abstract(base) for base in payload["bases"]):
        return True
    if any(_ABSTRACT_METACLASS_MARKER in keyword for keyword in payload.get("keywords", [])):
        return True
    return any(
        _ABSTRACT_METHOD_MARKER in decorator
        for method in payload["methods"]
        for decorator in method.get("decorators", [])
    )


def _base_is_abstract(base: str) -> bool:
    head = base.split("[")[0]  # Protocol[T] -> Protocol
    last = head.split(".")[-1]  # typing.Protocol -> Protocol
    return last in _ABSTRACT_BASE_MARKERS


def distance_from_main_sequence(abstractness: float, instability: float) -> float:
    """|A + I − 1|: zero on the Main Sequence, 1.0 in the corners
    (pain: concrete + stable; uselessness: abstract + unstable)."""
    return abs(abstractness + instability - 1.0)


def dependency_inversion(
    target_modules: set[str], abstractness_by_module: dict[str, float | None]
) -> float | None:
    """Mean abstractness of imported targets; None with no outgoing edges.

    Targets without classes contribute 0.0 — importing a pure-function
    module is a concrete dependency by definition.
    """
    if not target_modules:
        return None
    total = sum(abstractness_by_module.get(target) or 0.0 for target in target_modules)
    return total / len(target_modules)
