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
                    },
                )
            )
    return facts


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
