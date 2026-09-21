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

from antipasta.core.model.metrics import FactRow
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
    """Import rows with the scope they execute in.

    ``scope`` is ``module`` for imports that run at import time (top level,
    class bodies, conditional blocks), ``function`` for imports deferred into
    a function body, and ``type_checking`` for imports guarded by an
    ``if TYPE_CHECKING:`` block. Only module-scope imports are dependency
    edges; the others are recorded so derivers can count them separately.
    """
    facts: list[FactRow] = []
    _collect_imports(module.body, "module", facts)
    return facts


def _collect_imports(statements: list[ast.stmt], scope: str, facts: list[FactRow]) -> None:
    for node in statements:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            facts.extend(_import_rows(node, scope))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _collect_imports(node.body, "function", facts)
        elif isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            _collect_imports(node.body, "type_checking", facts)
            _collect_imports(node.orelse, scope, facts)
        else:
            for block in _child_blocks(node):
                _collect_imports(block, scope, facts)


def _import_rows(node: ast.Import | ast.ImportFrom, scope: str) -> list[FactRow]:
    if isinstance(node, ast.Import):
        return [
            FactRow(
                kind="import",
                payload={"module": alias.name, "names": [], "level": 0, "scope": scope},
            )
            for alias in node.names
        ]
    return [
        FactRow(
            kind="import",
            payload={
                "module": node.module or "",
                "names": [alias.name for alias in node.names],
                "level": node.level,
                "scope": scope,
            },
        )
    ]


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _child_blocks(node: ast.stmt) -> list[list[ast.stmt]]:
    """Statement lists nested directly under a compound statement."""
    blocks: list[list[ast.stmt]] = []
    for name in ("body", "orelse", "finalbody"):
        block = getattr(node, name, None)
        if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            blocks.append(block)
    for handler in getattr(node, "handlers", []) or []:
        blocks.append(handler.body)
    for case in getattr(node, "cases", []) or []:
        blocks.append(case.body)
    return blocks


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
                        "return_annotation": (ast.unparse(node.returns) if node.returns else None),
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
                            f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.keywords if kw.arg
                        ],
                        "methods": [
                            _method_payload(member)
                            for member in node.body
                            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                        ],
                        # Every name the class body reads; the class registry
                        # resolves these to analyzed classes for coupling.
                        "referenced_names": sorted({
                            child.id
                            for child in ast.walk(node)
                            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
                        }),
                    },
                )
            )
    return facts


def _method_payload(method: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    fields_read: set[str] = set()
    fields_written: set[str] = set()
    calls_local: set[str] = set()
    for node in ast.walk(method):
        if _is_receiver_attribute(node):
            if isinstance(node.ctx, ast.Store):
                fields_written.add(node.attr)
            else:
                fields_read.add(node.attr)
        if isinstance(node, ast.Call) and _is_receiver_attribute(node.func):
            calls_local.add(node.func.attr)
    # Local calls are not field reads; keep the sets disjoint.
    fields_read -= calls_local
    return {
        "name": method.name,
        "decorators": [ast.unparse(d) for d in method.decorator_list],
        "fields_read": sorted(fields_read),
        "fields_written": sorted(fields_written),
        "calls_local": sorted(calls_local),
        "stub": stub_kind(method),
    }


def _is_receiver_attribute(node: ast.AST) -> TypeGuard[ast.Attribute]:
    """``self.x`` or ``cls.x``: state reached through the method receiver."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in ("self", "cls")
    )


def stub_kind(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Classify a body that carries no behavior.

    ``not_implemented`` (``raise NotImplementedError``) and ``ellipsis`` are
    the conventions for abstract methods outside ``abc``; ``pass`` and
    ``empty`` (docstring only) are no-op hooks. ``None`` means the body does
    something.
    """
    body = own_statements(function)
    if body and _is_docstring(body[0]):
        body = body[1:]
    if not body:
        return "empty"
    if len(body) != 1:
        return None
    statement = body[0]
    if isinstance(statement, ast.Pass):
        return "pass"
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        return "ellipsis" if statement.value.value is Ellipsis else None
    if isinstance(statement, ast.Raise) and _raises_not_implemented(statement):
        return "not_implemented"
    return None


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


def _raises_not_implemented(statement: ast.Raise) -> bool:
    target = statement.exc
    if isinstance(target, ast.Call):
        target = target.func
    return isinstance(target, ast.Name) and target.id == "NotImplementedError"
