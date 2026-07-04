"""Fact extraction: raw imports, callables, classes.

Facts are path-independent and judgment-free (the two cache-safety rules from
docs/design/structural-metrics-caching.md). Imports are deliberately stored
UNRESOLVED — resolving ``from . import x`` depends on the file's location,
which belongs to the derivation layer. Class facts carry the per-method field
access and local calls the Phase 2 cohesion metrics need, so the file is
parsed once for everything.
"""

from __future__ import annotations

import ast
from typing import Any, TypeGuard

from antipasta.core.metrics import FactRow
from antipasta.runners.python.house_style.expressions import (
    call_names,
    max_nesting,
    own_statements,
    total_computation_weight,
)


def extract_facts(module: ast.Module) -> list[FactRow]:
    """All fact rows for one parsed module."""
    return [
        *_import_facts(module),
        *_callable_facts(module),
        *_class_facts(module),
    ]


def _import_facts(module: ast.Module) -> list[FactRow]:
    facts: list[FactRow] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                facts.append(
                    FactRow(
                        kind="import",
                        payload={"module": alias.name, "names": [], "level": 0},
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            facts.append(
                FactRow(
                    kind="import",
                    payload={
                        "module": node.module or "",
                        "names": [alias.name for alias in node.names],
                        "level": node.level,
                    },
                )
            )
    return facts


def _callable_facts(module: ast.Module) -> list[FactRow]:
    method_names = _method_name_ids(module)
    facts: list[FactRow] = []
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            facts.append(
                FactRow(
                    kind="callable",
                    payload={
                        "name": node.name,
                        "lineno": node.lineno,
                        "is_method": id(node) in method_names,
                        "class_name": method_names.get(id(node)),
                        # Narrative ingredients (fixed rules; classification
                        # is derivation-side): what it calls, how much raw
                        # computation it holds, and its size/shape budget data.
                        "call_names": call_names(node),
                        "computation_weight": total_computation_weight(node),
                        "statements": len(own_statements(node)),
                        "nesting": max_nesting(node),
                        "returns_value": _returns_value(node),
                        "return_annotation": (
                            ast.unparse(node.returns) if node.returns else None
                        ),
                    },
                )
            )
    return facts


def _returns_value(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(statement, ast.Return) and statement.value is not None
        for statement in own_statements(function)
    )


def _method_name_ids(module: ast.Module) -> dict[int, str]:
    """Map id(function node) -> owning class name, for direct class members."""
    owners: dict[int, str] = {}
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owners[id(member)] = node.name
    return owners


def _class_facts(module: ast.Module) -> list[FactRow]:
    facts: list[FactRow] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef):
            facts.append(
                FactRow(
                    kind="class",
                    payload={
                        "name": node.name,
                        "lineno": node.lineno,
                        "bases": [ast.unparse(base) for base in node.bases],
                        "decorators": [ast.unparse(d) for d in node.decorator_list],
                        "keywords": [
                            f"{kw.arg}={ast.unparse(kw.value)}"
                            for kw in node.keywords
                            if kw.arg
                        ],
                        "methods": [
                            _method_payload(member)
                            for member in node.body
                            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ],
                    },
                )
            )
    return facts


def _method_payload(method: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    fields_read: set[str] = set()
    fields_written: set[str] = set()
    calls_local: set[str] = set()
    for node in ast.walk(method):
        if _is_self_attribute(node):
            if isinstance(node.ctx, ast.Store):
                fields_written.add(node.attr)
            else:
                fields_read.add(node.attr)
        if isinstance(node, ast.Call) and _is_self_attribute(node.func):
            calls_local.add(node.func.attr)
    # Local calls are not field reads; keep the sets disjoint.
    fields_read -= calls_local
    return {
        "name": method.name,
        "decorators": [ast.unparse(d) for d in method.decorator_list],
        "fields_read": sorted(fields_read),
        "fields_written": sorted(fields_written),
        "calls_local": sorted(calls_local),
    }


def _is_self_attribute(node: ast.AST) -> TypeGuard[ast.Attribute]:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )
