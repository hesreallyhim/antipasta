"""House-style runner: one syntax-tree walk for the owner's prose metrics.

Emits per-function rows (message chain depth, arity, boolean flags,
exception discipline, global-state reach, statement count, expression
flatness, pipeline linearity), per-file rows (marker density, comment
density), and the fact rows (imports, callables, classes) that later phases'
derivers consume — one parse, everything extracted.

Python-only: these analyzers read Python's syntax tree. The concepts are
language-agnostic; JavaScript/TypeScript coverage waits on a real
multi-language parse layer (see the adoption plan's cross-cutting notes).
All rules are fixed and config-free so results stay pure functions of file
content (cache-safe); strictness profiles act at the threshold layer.
"""

from __future__ import annotations

import ast
from pathlib import Path

from antipasta.core.detector import Language, is_test_path
from antipasta.core.metrics import FactRow, FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner
from antipasta.runners.python.house_style import (
    cohesion,
    comments,
    expressions,
    structure,
    test_smells,
)
from antipasta.runners.python.house_style.facts import extract_facts


class HouseStyleRunner(BaseRunner):
    """Runner for house-style (prose/newspaper) metrics."""

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics emitted by this runner."""
        return [
            MetricType.MESSAGE_CHAIN_DEPTH.value,
            MetricType.FUNCTION_ARITY.value,
            MetricType.BOOLEAN_FLAG_PARAMETERS.value,
            MetricType.EXCEPTION_DISCIPLINE.value,
            MetricType.GLOBAL_STATE_REACH.value,
            MetricType.FUNCTION_STATEMENTS.value,
            MetricType.EXPRESSION_FLATNESS.value,
            MetricType.PIPELINE_LINEARITY.value,
            MetricType.MARKER_DENSITY.value,
            MetricType.COMMENT_DENSITY.value,
            MetricType.LACK_OF_COHESION.value,
            MetricType.COUPLING_BETWEEN_OBJECTS.value,
            MetricType.ASSERTIONS_PER_TEST.value,
            MetricType.MOCK_CALL_ASSERTIONS.value,
            MetricType.BIG_LITERAL_ASSERTIONS.value,
        ]

    def is_available(self) -> bool:
        """Standard-library only; always available."""
        return True

    def analyze(self, file_path: Path, content: str | None = None) -> FileMetrics:
        """Analyze a Python file's style properties and extract fact rows."""
        if content is None:
            try:
                content = file_path.read_text()
            except Exception as read_error:
                return FileMetrics(
                    file_path=file_path,
                    language=Language.PYTHON.value,
                    metrics=[],
                    error=f"Failed to read file: {read_error}",
                )

        try:
            module = ast.parse(content)
        except (SyntaxError, ValueError):
            # Unparseable source: no rows, matching the other runners.
            return FileMetrics(
                file_path=file_path, language=Language.PYTHON.value, metrics=[]
            )

        facts = extract_facts(module)
        rows = [
            *self._function_rows(file_path, module),
            *self._class_rows(file_path, module, facts),
            *self._file_rows(file_path, content),
            *self._test_smell_rows(file_path, module),
        ]
        return FileMetrics(
            file_path=file_path,
            language=Language.PYTHON.value,
            metrics=rows,
            facts=facts,
        )

    def _function_rows(self, file_path: Path, module: ast.Module) -> list[MetricResult]:
        mutable_names = structure.module_mutable_names(module)
        method_owners = _method_owner_ids(module)
        rows: list[MetricResult] = []
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_method = id(node) in method_owners
                rows.extend(
                    _rows_for_function(file_path, node, is_method, mutable_names)
                )
        return rows

    def _class_rows(
        self, file_path: Path, module: ast.Module, facts: list[FactRow]
    ) -> list[MetricResult]:
        """Per-class cohesion and coupling rows (Phase 2)."""
        imported = cohesion.imported_name_set(module)
        class_nodes = {
            node.name: node for node in ast.walk(module) if isinstance(node, ast.ClassDef)
        }
        rows: list[MetricResult] = []
        for fact in facts:
            if fact.kind != "class":
                continue
            payload = fact.payload
            rows.append(
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.LACK_OF_COHESION,
                    value=float(cohesion.lack_of_cohesion(payload["methods"])),
                    line_number=payload["lineno"],
                    function_name=payload["name"],
                    details={"methods": len(payload["methods"])},
                )
            )
            class_node = class_nodes.get(payload["name"])
            if class_node is not None:
                rows.append(
                    MetricResult(
                        file_path=file_path,
                        metric_type=MetricType.COUPLING_BETWEEN_OBJECTS,
                        value=float(
                            cohesion.coupling_between_objects(class_node, imported)
                        ),
                        line_number=payload["lineno"],
                        function_name=payload["name"],
                        details={"approximate": True},
                    )
                )
        return rows

    def _test_smell_rows(self, file_path: Path, module: ast.Module) -> list[MetricResult]:
        """Track D1 smells — only for test functions in test-looking files."""
        if not is_test_path(str(file_path)):
            return []
        rows: list[MetricResult] = []
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not test_smells.is_test_function(node.name):
                continue
            values = [
                (MetricType.ASSERTIONS_PER_TEST, test_smells.assertions_per_test(node)),
                (MetricType.MOCK_CALL_ASSERTIONS, test_smells.mock_call_assertions(node)),
                (
                    MetricType.BIG_LITERAL_ASSERTIONS,
                    test_smells.big_literal_assertions(node),
                ),
            ]
            rows.extend(
                MetricResult(
                    file_path=file_path,
                    metric_type=metric_type,
                    value=float(value),
                    line_number=node.lineno,
                    function_name=node.name,
                )
                for metric_type, value in values
            )
        return rows

    def _file_rows(self, file_path: Path, content: str) -> list[MetricResult]:
        comment_line_count, markers = comments.comment_lines_and_markers(content)
        line_count = comments.total_lines(content)
        return [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.MARKER_DENSITY,
                value=comments.marker_density(markers, line_count),
                details={"markers": markers, "lines": line_count},
            ),
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.COMMENT_DENSITY,
                value=comments.comment_density(comment_line_count, line_count),
                details={"comment_lines": comment_line_count, "lines": line_count},
            ),
        ]


def _method_owner_ids(module: ast.Module) -> set[int]:
    owners: set[int] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owners.add(id(member))
    return owners


def _rows_for_function(
    file_path: Path,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool,
    mutable_names: frozenset[str],
) -> list[MetricResult]:
    """The eight per-function house-style rows."""
    values: list[tuple[MetricType, float]] = [
        (MetricType.MESSAGE_CHAIN_DEPTH, float(expressions.max_chain_depth(function))),
        (MetricType.FUNCTION_ARITY, float(structure.function_arity(function, is_method))),
        (
            MetricType.BOOLEAN_FLAG_PARAMETERS,
            float(structure.boolean_flag_parameters(function, is_method)),
        ),
        (
            MetricType.EXCEPTION_DISCIPLINE,
            float(structure.exception_discipline(structure.handlers_in(function))),
        ),
        (
            MetricType.GLOBAL_STATE_REACH,
            float(structure.global_state_reach(function, mutable_names)),
        ),
        (
            MetricType.FUNCTION_STATEMENTS,
            float(len(expressions.own_statements(function))),
        ),
        (MetricType.EXPRESSION_FLATNESS, expressions.expression_flatness(function)),
        (MetricType.PIPELINE_LINEARITY, expressions.pipeline_linearity(function)),
    ]
    return [
        MetricResult(
            file_path=file_path,
            metric_type=metric_type,
            value=value,
            line_number=function.lineno,
            function_name=function.name,
        )
        for metric_type, value in values
    ]
