"""Test-smell analyzers (track D1): the agent-suite pathology, statically.

Rows are emitted only for test functions in test-looking files (path
convention), so they appear when a test tree is analyzed and never pollute
source metrics. Three smells, all cheap single-walk counts:

- assertions per test — a thirty-assert test is a change detector;
- mock over-specification — assert_called_with/call-count assertions pin
  implementation, not contract;
- big-literal assertions — comparing against large inline structures is
  hand-rolled snapshot testing.
"""

from __future__ import annotations

import ast

from antipasta.runners.python.house_style.expressions import own_statements

_MOCK_ASSERT_PREFIXES = ("assert_called", "assert_awaited", "assert_not_called", "assert_has_calls")
_BIG_LITERAL_FLOOR = 8


def is_test_function(name: str) -> bool:
    return name.startswith("test_") or name == "test"


def assertions_per_test(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Plain assert statements plus mock-style assert calls."""
    count = 0
    for statement in own_statements(function):
        is_plain = isinstance(statement, ast.Assert)
        is_mock = isinstance(statement, ast.Expr) and _is_mock_assert(statement.value)
        if is_plain or is_mock:
            count += 1
    return count


def mock_call_assertions(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """assert_called*/assert_awaited* style calls: implementation pinning."""
    return sum(
        1
        for statement in own_statements(function)
        if isinstance(statement, ast.Expr) and _is_mock_assert(statement.value)
    )


def _is_mock_assert(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith(_MOCK_ASSERT_PREFIXES)
    )


def big_literal_assertions(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Asserts comparing against large inline dict/list/set/tuple literals."""
    count = 0
    for statement in own_statements(function):
        if isinstance(statement, ast.Assert) and _has_big_literal(statement.test):
            count += 1
    return count


def _has_big_literal(node: ast.expr) -> bool:
    for child in ast.walk(node):
        size = _literal_size(child)
        if size >= _BIG_LITERAL_FLOOR:
            return True
    return False


def _literal_size(node: ast.AST) -> int:
    if isinstance(node, ast.Dict):
        return len(node.keys)
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return len(node.elts)
    return 0
