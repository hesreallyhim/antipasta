"""Structural analyzers: arity, flag parameters, global reach."""

from __future__ import annotations

import ast

from antipasta.runners.python.structural.expressions import own_statements

_SELF_NAMES = frozenset({"self", "cls"})


def function_arity(function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> int:
    """Required positional parameters, excluding self/cls.

    The long-parameter-list smell is about what every caller must supply in
    order. Defaulted and keyword-only parameters are a configuration surface
    (pydantic's ``Field`` takes thirty-four keyword-only arguments and is not
    missing a parameter object); they are reported in the row's details.
    """
    return len(_required_positional(function, is_method))


def arity_details(
    function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> dict[str, int | bool]:
    """The parameter shape behind the arity value."""
    arguments = function.args
    positional = _positional(function, is_method)
    return {
        "defaulted": min(len(arguments.defaults), len(positional)),
        "keyword_only": len(arguments.kwonlyargs),
        "variadic": bool(arguments.vararg or arguments.kwarg),
    }


def _positional(function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> list[ast.arg]:
    positional = [*function.args.posonlyargs, *function.args.args]
    if is_method and positional and positional[0].arg in _SELF_NAMES:
        positional = positional[1:]
    return positional


def _required_positional(
    function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> list[ast.arg]:
    positional = _positional(function, is_method)
    defaults = len(function.args.defaults)
    return positional[: len(positional) - defaults] if defaults else positional


def boolean_flag_parameters(
    function: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool
) -> int:
    """Positional boolean parameters the body branches on (a function hiding two).

    The smell is control coupling: the caller picks a code path with a flag.
    A boolean that is only stored or passed along is configuration, not a
    hidden second function. Keyword-only booleans are exempt — forcing the
    flag to be named at the call site is the accepted remedy, not a smell.
    """
    positional = _positional(function, is_method)
    defaults = function.args.defaults
    defaulted = dict(zip([arg.arg for arg in positional[-len(defaults) :]], defaults, strict=False))
    flags = {
        parameter.arg
        for parameter in positional
        if _is_bool_annotation(parameter.annotation)
        or _is_bool_constant(defaulted.get(parameter.arg))
    }
    return len(flags & _branch_condition_names(function))


def _branch_condition_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names read inside the tests of the function's own conditionals."""
    names: set[str] = set()
    for statement in own_statements(function):
        tests: list[ast.expr] = []
        if isinstance(statement, (ast.If, ast.While)):
            tests.append(statement.test)
        for node in ast.walk(statement):
            if isinstance(node, ast.IfExp):
                tests.append(node.test)
        for test in tests:
            names.update(n.id for n in ast.walk(test) if isinstance(n, ast.Name))
    return names


def _is_bool_annotation(annotation: ast.expr | None) -> bool:
    return isinstance(annotation, ast.Name) and annotation.id == "bool"


def _is_bool_constant(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


_MUTATING_METHODS = frozenset({
    "append",
    "extend",
    "insert",
    "pop",
    "remove",
    "clear",
    "update",
    "setdefault",
    "add",
    "discard",
    "popitem",
    "sort",
    "reverse",
    "appendleft",
    "extendleft",
    "popleft",
})
_MUTABLE_CONSTRUCTORS = frozenset({
    "list",
    "dict",
    "set",
    "bytearray",
    "deque",
    "defaultdict",
    "OrderedDict",
    "Counter",
})


def module_mutable_names(module: ast.Module) -> frozenset[str]:
    """Module-level bindings that are mutable state, by evidence not by case.

    A name counts when the module actually treats it as state: some function
    writes to it (``global`` plus assignment, an item or attribute store, or
    a mutating method call), it is rebound more than once at module level,
    or it is bound to a mutable container (a registry or cache waiting to be
    filled). Compiled regexes, type aliases, and sentinels assigned once and
    only read are constants whatever their spelling.
    """
    bound: dict[str, int] = {}
    containers: set[str] = set()
    for statement in module.body:
        for target in _assignment_targets(statement):
            if isinstance(target, ast.Name) and not _is_dunder(target.id):
                bound[target.id] = bound.get(target.id, 0) + 1
                if _is_mutable_container(getattr(statement, "value", None)):
                    containers.add(target.id)
    written = _names_written_in_functions(module)
    rebound = {name for name, count in bound.items() if count > 1}
    return frozenset((written | rebound | containers) & set(bound))


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_mutable_container(value: ast.expr | None) -> bool:
    if isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(value, ast.Call):
        callee = value.func
        name = callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", None)
        return name in _MUTABLE_CONSTRUCTORS
    return False


def _names_written_in_functions(module: ast.Module) -> set[str]:
    """Module-level names some function stores to, mutates in place, or declares global."""
    written: set[str] = set()
    for function in ast.walk(module):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            written.update(_written_by(function))
    return written


def _written_by(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    written: set[str] = set()
    declared_global: set[str] = set()
    stored: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Global):
            declared_global.update(node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stored.add(node.id)
        else:
            target = _in_place_write_target(node)
            if target is not None:
                written.add(target)
    return written | (declared_global & stored)


def _in_place_write_target(node: ast.AST) -> str | None:
    """The name behind ``name[k] = v``, ``name.attr = v``, or ``name.append(v)``."""
    if isinstance(node, (ast.Subscript, ast.Attribute)) and isinstance(node.ctx, ast.Store):
        return _root_name(node)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _MUTATING_METHODS
        and isinstance(node.func.value, ast.Name)
    ):
        return node.func.value.id
    return None


def _root_name(node: ast.expr) -> str | None:
    current = node
    while isinstance(current, (ast.Subscript, ast.Attribute)):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _assignment_targets(statement: ast.stmt) -> list[ast.expr]:
    if isinstance(statement, ast.Assign):
        return list(statement.targets)
    if isinstance(statement, (ast.AugAssign, ast.AnnAssign)):
        return [statement.target]
    return []


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
