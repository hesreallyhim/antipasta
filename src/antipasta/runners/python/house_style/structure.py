"""Structural analyzers: arity, flag parameters, exceptions, global reach."""

from __future__ import annotations

import ast

from antipasta.runners.python.house_style.expressions import own_statements

_SELF_NAMES = frozenset({"self", "cls"})
_BROAD_EXCEPTION_NAMES = frozenset({"Exception", "BaseException"})


def function_arity(function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> int:
    """Parameter count, excluding self/cls; *args and **kwargs count one each."""
    arguments = function.args
    named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if is_method and named and named[0].arg in _SELF_NAMES:
        named = named[1:]
    return len(named) + (1 if arguments.vararg else 0) + (1 if arguments.kwarg else 0)


def boolean_flag_parameters(
    function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> int:
    """Positional parameters that are boolean flags (a function hiding two).

    Keyword-only booleans are exempt — forcing the flag to be named at the
    call site is the accepted remedy, not a smell.
    """
    positional = [*function.args.posonlyargs, *function.args.args]
    if is_method and positional and positional[0].arg in _SELF_NAMES:
        positional = positional[1:]

    defaults = function.args.defaults
    defaulted = dict(zip([arg.arg for arg in positional[-len(defaults):]], defaults, strict=False))

    count = 0
    for parameter in positional:
        is_flag = _is_bool_annotation(parameter.annotation) or _is_bool_constant(
            defaulted.get(parameter.arg)
        )
        if is_flag:
            count += 1
    return count


def _is_bool_annotation(annotation: ast.expr | None) -> bool:
    return isinstance(annotation, ast.Name) and annotation.id == "bool"


def _is_bool_constant(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def exception_discipline(handlers: list[ast.ExceptHandler]) -> int:
    """Count of undisciplined handlers: bare, broad-without-reraise, silent."""
    return sum(1 for handler in handlers if _is_undisciplined(handler))


def _is_undisciplined(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True  # bare except
    if _is_silent(handler.body):
        return True
    return _is_broad(handler.type) and not _reraises(handler.body)


def _is_broad(exception_type: ast.expr) -> bool:
    candidates = exception_type.elts if isinstance(exception_type, ast.Tuple) else [exception_type]
    return any(
        isinstance(candidate, ast.Name) and candidate.id in _BROAD_EXCEPTION_NAMES
        for candidate in candidates
    )


def _reraises(body: list[ast.stmt]) -> bool:
    return any(isinstance(node, ast.Raise) for statement in body for node in ast.walk(statement))


def _is_silent(body: list[ast.stmt]) -> bool:
    return all(
        isinstance(statement, ast.Pass)
        or (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is Ellipsis
        )
        for statement in body
    )


def handlers_in(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.ExceptHandler]:
    """Exception handlers belonging to this function's own statements."""
    handlers: list[ast.ExceptHandler] = []
    for statement in own_statements(function):
        # Any statement carrying a `handlers` block is a try form (Try/TryStar).
        handlers.extend(getattr(statement, "handlers", []))
    return handlers


def module_mutable_names(module: ast.Module) -> frozenset[str]:
    """Module-level bindings that read as mutable state.

    Fixed convention: lowercase, non-dunder names assigned at module top
    level. UPPER_CASE names are treated as constants; imports, functions,
    and classes are bindings, not state.
    """
    names: set[str] = set()
    for statement in module.body:
        for target in _assignment_targets(statement):
            if isinstance(target, ast.Name) and _is_mutable_style(target.id):
                names.add(target.id)
    return frozenset(names)


def _assignment_targets(statement: ast.stmt) -> list[ast.expr]:
    if isinstance(statement, ast.Assign):
        return list(statement.targets)
    if isinstance(statement, (ast.AugAssign, ast.AnnAssign)):
        return [statement.target]
    return []


def _is_mutable_style(name: str) -> bool:
    return not name.isupper() and not (name.startswith("__") and name.endswith("__"))


def global_state_reach(
    function: ast.FunctionDef | ast.AsyncFunctionDef, mutable_names: frozenset[str]
) -> int:
    """Distinct module-level mutable names this function touches."""
    touched: set[str] = set()
    for statement in own_statements(function):
        if isinstance(statement, ast.Global):
            touched.update(name for name in statement.names if name in mutable_names)
        for node in ast.walk(statement):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in mutable_names
            ):
                touched.add(node.id)
    return len(touched)
