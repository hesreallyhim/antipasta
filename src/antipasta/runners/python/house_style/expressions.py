"""Expression-shape analyzers: chain depth, flatness, pipeline linearity.

All rules here are fixed (profile- and config-free) so results stay pure
functions of file content — the strictness dial applies at the threshold
layer, never inside extraction. Semantics originate from the Narrative Index
discrimination probe (tests/temp/narrative_index_probe.temp.py).
"""

from __future__ import annotations

import ast
from collections import Counter

# Raw-computation expression forms. A named call reads as prose (weight 1);
# computation is heavier (weight 2); negation is free ("not x" reads fine).
_OPERATION_NODES = (
    ast.BinOp,
    ast.BoolOp,
    ast.Compare,
    ast.Subscript,
    ast.Lambda,
    ast.IfExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)

# Chains rooted here get their first hop free: `self.helper()` is not
# "reaching through" anything — it is how Python spells a local call.
_FREE_CHAIN_ROOTS = frozenset({"self", "cls", "super"})

_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def own_statements(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    """Statements belonging to this function, not to scopes nested in it.

    Descends through control flow (if/for/while/with/try/match) but stops at
    nested function and class definitions — those get their own metric rows,
    and counting them into the parent would double-charge.
    """
    collected: list[ast.stmt] = []

    def visit(body: list[ast.stmt]) -> None:
        for statement in body:
            collected.append(statement)
            if isinstance(statement, _NESTED_SCOPES):
                continue
            for inner_body in _nested_bodies(statement):
                visit(inner_body)

    visit(function.body)
    return collected


def _nested_bodies(statement: ast.stmt) -> list[list[ast.stmt]]:
    """Statement blocks nested inside a compound statement."""
    bodies = []
    for field_name in ("body", "orelse", "finalbody"):
        inner = getattr(statement, field_name, None)
        if inner:
            bodies.append(inner)
    for handler in getattr(statement, "handlers", []):
        bodies.append(handler.body)
    for case in getattr(statement, "cases", []):
        bodies.append(case.body)
    return bodies


def _own_expression_nodes(statement: ast.stmt) -> list[ast.expr]:
    """Expression nodes belonging to this statement (not nested statements)."""
    nodes: list[ast.expr] = []
    stack: list[ast.AST] = [
        child
        for child in ast.iter_child_nodes(statement)
        if not isinstance(child, (ast.stmt, ast.excepthandler, ast.match_case))
    ]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.expr):
            nodes.append(node)
        stack.extend(
            child for child in ast.iter_child_nodes(node) if not isinstance(child, ast.stmt)
        )
    return nodes


def max_chain_depth(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Deepest attribute/call chain in the function.

    ``foo.bar()`` is depth 1; ``foo.bar.baz.quix()`` is depth 3. Chains
    rooted at self/cls/super get the first hop free.
    """
    deepest = 0
    for statement in own_statements(function):
        for node in _own_expression_nodes(statement):
            if isinstance(node, ast.Attribute):
                deepest = max(deepest, _chain_depth(node))
    return deepest


def _chain_depth(node: ast.Attribute) -> int:
    depth = 0
    current: ast.expr = node
    while True:
        if isinstance(current, ast.Attribute):
            depth += 1
            current = current.value
        elif isinstance(current, ast.Call):
            current = current.func
        else:
            break
    if isinstance(current, ast.Name) and current.id in _FREE_CHAIN_ROOTS:
        depth -= 1
    return depth


def expression_flatness(function: ast.FunctionDef | ast.AsyncFunctionDef) -> float:
    """One idea per line: fraction of statements within the operation budget.

    Calls weigh 1; raw computation weighs 2; ``not`` is free. A statement is
    flat when its total weight is at most 1.
    """
    statements = own_statements(function)
    if not statements:
        return 1.0
    flat = sum(1 for statement in statements if _operation_weight(statement) <= 1)
    return flat / len(statements)


def _operation_weight(statement: ast.stmt) -> int:
    weight = 0
    for node in _own_expression_nodes(statement):
        if isinstance(node, ast.Call):
            weight += 1
        elif isinstance(node, _OPERATION_NODES):
            weight += 2
    return weight


def pipeline_linearity(function: ast.FunctionDef | ast.AsyncFunctionDef) -> float:
    """Fraction of local names assigned exactly once and read exactly once —
    the "explaining variable" pattern that makes bodies read as then/then/then.
    """
    assigned: Counter[str] = Counter()
    loaded: Counter[str] = Counter()
    for statement in own_statements(function):
        for node in _own_expression_nodes(statement):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    assigned[node.id] += 1
                elif isinstance(node.ctx, ast.Load):
                    loaded[node.id] += 1
    if not assigned:
        return 1.0
    linear = sum(1 for name, count in assigned.items() if count == 1 and loaded[name] == 1)
    return linear / len(assigned)
