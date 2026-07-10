"""JavaScript/TypeScript house-style metrics and fact extraction.

This runner deliberately stays dependency-light.  It is a lexical extractor,
not a full ECMAScript type checker, so rows that depend on syntax recovery are
labeled approximate.  The fixed rules mirror the Python house-style runner and
remain config-free so cached rows are pure functions of file content.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re

from antipasta.core.derive import cohesion
from antipasta.core.model.detector import EXTENSION_MAP, Language, is_test_path
from antipasta.core.model.metrics import FactRow, FileMetrics, MetricResult, MetricType
from antipasta.runners.base import BaseRunner
from antipasta.runners.python.house_style.comments import (
    comment_density,
    marker_density,
    total_lines,
)

_MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")

_KEYWORDS = frozenset({
    "abstract",
    "as",
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "from",
    "function",
    "get",
    "if",
    "implements",
    "import",
    "in",
    "instanceof",
    "interface",
    "let",
    "new",
    "of",
    "private",
    "protected",
    "public",
    "readonly",
    "return",
    "set",
    "static",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "type",
    "var",
    "while",
    "yield",
})

_MODIFIERS = frozenset({
    "abstract",
    "async",
    "declare",
    "get",
    "override",
    "private",
    "protected",
    "public",
    "readonly",
    "set",
    "static",
})

_CONTROL_KEYWORDS = frozenset({
    "catch",
    "for",
    "if",
    "switch",
    "while",
    "with",
})

_STATEMENT_KEYWORDS = frozenset({
    "break",
    "case",
    "catch",
    "continue",
    "do",
    "else",
    "finally",
    "for",
    "if",
    "return",
    "switch",
    "throw",
    "try",
    "while",
})

_DECLARATION_KEYWORDS = frozenset({"const", "let", "var"})
_FREE_CHAIN_ROOTS = frozenset({"this", "super"})
_ASSIGNMENT_OPERATORS = frozenset({
    "=",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "**=",
    "&&=",
    "||=",
    "??=",
})
_OPERATION_TOKENS = frozenset({
    "!=",
    "!==",
    "%",
    "&&",
    "*",
    "**",
    "+",
    "-",
    "/",
    "<",
    "<=",
    "==",
    "===",
    ">",
    ">=",
    "??",
    "||",
    "?",
    "[",
})
_MOCK_ASSERT_NAMES = (
    "toHaveBeenCalled",
    "toHaveBeenCalledTimes",
    "toHaveBeenCalledWith",
    "calledWith",
    "calledOnce",
)
_TEST_CALL_NAMES = frozenset({"it", "test"})
_BIG_LITERAL_FLOOR = 8
_ANALYZER = "javascript-house-style"


@dataclass(frozen=True)
class Token:
    """One lexical token with a stable position in the token stream."""

    index: int
    value: str
    kind: str
    line: int
    column: int


@dataclass
class SourceTokens:
    """Token stream plus cheap bracket indexes."""

    tokens: list[Token]
    parens: dict[int, int]
    braces: dict[int, int]
    brackets: dict[int, int]
    comment_lines: set[int]
    markers: int


@dataclass
class FunctionSpan:
    """A JavaScript callable range."""

    name: str
    start_idx: int
    end_idx: int
    body_start: int
    body_end: int
    start_line: int
    params: list[list[Token]]
    is_method: bool = False
    class_name: str | None = None
    return_annotation: str | None = None
    body_is_block: bool = True


@dataclass
class ClassSpan:
    """A JavaScript class range."""

    name: str
    start_idx: int
    end_idx: int
    body_start: int
    body_end: int
    start_line: int
    bases: list[str]
    methods: list[FunctionSpan]
    abstract: bool = False


class HouseStyleRunner(BaseRunner):
    """Runner for JavaScript/TypeScript house-style metrics."""

    @property
    def supported_metrics(self) -> list[str]:
        """List of metrics emitted by this runner."""
        return [
            MetricType.LOGICAL_LINES_OF_CODE.value,
            MetricType.COMMENT_LINES.value,
            MetricType.BLANK_LINES.value,
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
        """Analyze a JavaScript or TypeScript file."""
        language = _detect_language(file_path)
        if content is None:
            try:
                content = file_path.read_text()
            except Exception as read_error:
                return FileMetrics(
                    file_path=file_path,
                    language=language,
                    metrics=[],
                    error=f"Failed to read file: {read_error}",
                )

        source = _lex(content)
        classes = _extract_classes(source)
        functions = _extract_functions(source, classes)
        imports = _import_facts(source.tokens)
        mutable_names = _module_mutable_names(source.tokens)

        rows = [
            *self._raw_rows(file_path, content, source),
            *self._file_rows(file_path, content, source),
            *self._function_rows(file_path, source, functions, classes, mutable_names),
            *self._class_rows(file_path, source, classes, imports),
            *self._test_smell_rows(file_path, source, functions, classes),
        ]
        return FileMetrics(
            file_path=file_path,
            language=language,
            metrics=rows,
            facts=[
                *imports,
                *_callable_facts(source, functions, classes),
                *_class_facts(source, classes),
            ],
        )

    def _raw_rows(self, file_path: Path, content: str, source: SourceTokens) -> list[MetricResult]:
        line_count = total_lines(content)
        blank_lines = sum(1 for line in content.splitlines() if not line.strip())
        return [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.LOGICAL_LINES_OF_CODE,
                value=float(_logical_line_count(source.tokens)),
                details={"analyzer": _ANALYZER, "approximate": True},
            ),
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.COMMENT_LINES,
                value=float(len(source.comment_lines)),
                details={"analyzer": _ANALYZER},
            ),
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.BLANK_LINES,
                value=float(blank_lines if line_count else 0),
                details={"analyzer": _ANALYZER},
            ),
        ]

    def _file_rows(self, file_path: Path, content: str, source: SourceTokens) -> list[MetricResult]:
        line_count = total_lines(content)
        return [
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.MARKER_DENSITY,
                value=marker_density(source.markers, line_count),
                details={
                    "markers": source.markers,
                    "lines": line_count,
                    "analyzer": _ANALYZER,
                },
            ),
            MetricResult(
                file_path=file_path,
                metric_type=MetricType.COMMENT_DENSITY,
                value=comment_density(len(source.comment_lines), line_count),
                details={
                    "comment_lines": len(source.comment_lines),
                    "lines": line_count,
                    "analyzer": _ANALYZER,
                },
            ),
        ]

    def _function_rows(
        self,
        file_path: Path,
        source: SourceTokens,
        functions: list[FunctionSpan],
        classes: list[ClassSpan],
        mutable_names: frozenset[str],
    ) -> list[MetricResult]:
        rows: list[MetricResult] = []
        for function in functions:
            own_tokens = _own_tokens(source.tokens, function, functions, classes)
            values = [
                (MetricType.MESSAGE_CHAIN_DEPTH, float(_max_chain_depth(own_tokens))),
                (MetricType.FUNCTION_ARITY, float(_function_arity(function))),
                (MetricType.BOOLEAN_FLAG_PARAMETERS, float(_boolean_flag_parameters(function))),
                (
                    MetricType.EXCEPTION_DISCIPLINE,
                    float(_exception_discipline(source, own_tokens)),
                ),
                (
                    MetricType.GLOBAL_STATE_REACH,
                    float(_global_state_reach(own_tokens, mutable_names)),
                ),
                (MetricType.FUNCTION_STATEMENTS, float(_statement_count(own_tokens))),
                (MetricType.EXPRESSION_FLATNESS, _expression_flatness(own_tokens)),
                (MetricType.PIPELINE_LINEARITY, _pipeline_linearity(own_tokens)),
            ]
            rows.extend(
                MetricResult(
                    file_path=file_path,
                    metric_type=metric_type,
                    value=value,
                    line_number=function.start_line,
                    function_name=function.name,
                    details={"analyzer": _ANALYZER, "approximate": True},
                )
                for metric_type, value in values
            )
        return rows

    def _class_rows(
        self,
        file_path: Path,
        source: SourceTokens,
        classes: list[ClassSpan],
        imports: list[FactRow],
    ) -> list[MetricResult]:
        imported_names = _imported_local_names(imports)
        rows: list[MetricResult] = []
        for class_span in classes:
            method_payloads = [_method_payload(source, method) for method in class_span.methods]
            rows.extend((
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.LACK_OF_COHESION,
                    value=float(cohesion.lack_of_cohesion(method_payloads)),
                    line_number=class_span.start_line,
                    function_name=class_span.name,
                    details={"methods": len(method_payloads), "analyzer": _ANALYZER},
                ),
                MetricResult(
                    file_path=file_path,
                    metric_type=MetricType.COUPLING_BETWEEN_OBJECTS,
                    value=float(_coupling_between_objects(source, class_span, imported_names)),
                    line_number=class_span.start_line,
                    function_name=class_span.name,
                    details={"approximate": True, "analyzer": _ANALYZER},
                ),
            ))
        return rows

    def _test_smell_rows(
        self,
        file_path: Path,
        source: SourceTokens,
        functions: list[FunctionSpan],
        classes: list[ClassSpan],
    ) -> list[MetricResult]:
        if not is_test_path(str(file_path)):
            return []

        rows: list[MetricResult] = []
        for function in functions:
            if not _is_test_function(function.name):
                continue
            own_tokens = _own_tokens(source.tokens, function, functions, classes)
            values = [
                (MetricType.ASSERTIONS_PER_TEST, _assertions_per_test(own_tokens)),
                (MetricType.MOCK_CALL_ASSERTIONS, _mock_call_assertions(own_tokens)),
                (MetricType.BIG_LITERAL_ASSERTIONS, _big_literal_assertions(source, own_tokens)),
            ]
            rows.extend(
                MetricResult(
                    file_path=file_path,
                    metric_type=metric_type,
                    value=float(value),
                    line_number=function.start_line,
                    function_name=function.name,
                    details={"analyzer": _ANALYZER, "approximate": True},
                )
                for metric_type, value in values
            )
        return rows


def _detect_language(file_path: Path) -> str:
    language = EXTENSION_MAP.get(file_path.suffix.lower(), Language.UNKNOWN)
    return language.value


def _lex(content: str) -> SourceTokens:
    tokens: list[Token] = []
    comment_lines: set[int] = set()
    markers = 0
    index = 0
    line = 1
    column = 1
    pos = 0

    def add(value: str, kind: str, token_line: int, token_column: int) -> None:
        nonlocal index
        tokens.append(Token(index, value, kind, token_line, token_column))
        index += 1

    def advance(text: str) -> None:
        nonlocal line, column
        for char in text:
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1

    while pos < len(content):
        char = content[pos]
        if char.isspace():
            advance(char)
            pos += 1
            continue

        if content.startswith("//", pos):
            end = content.find("\n", pos)
            if end == -1:
                end = len(content)
            comment = content[pos:end]
            comment_lines.add(line)
            markers += len(_MARKER_PATTERN.findall(comment))
            advance(comment)
            pos = end
            continue

        if content.startswith("/*", pos):
            end = content.find("*/", pos + 2)
            end = len(content) if end == -1 else end + 2
            comment = content[pos:end]
            start_line = line
            advance(comment)
            comment_lines.update(range(start_line, line + 1))
            markers += len(_MARKER_PATTERN.findall(comment))
            pos = end
            continue

        if char in ("'", '"', "`"):
            token_line = line
            token_column = column
            value, consumed = _read_string(content[pos:], char)
            add(value, "string", token_line, token_column)
            advance(content[pos : pos + consumed])
            pos += consumed
            continue

        if _is_identifier_start(char):
            token_line = line
            token_column = column
            end = pos + 1
            while end < len(content) and _is_identifier_part(content[end]):
                end += 1
            value = content[pos:end]
            add(value, "keyword" if value in _KEYWORDS else "identifier", token_line, token_column)
            advance(content[pos:end])
            pos = end
            continue

        if char.isdigit():
            token_line = line
            token_column = column
            end = pos + 1
            while end < len(content) and re.match(r"[\w.]", content[end]):
                end += 1
            add(content[pos:end], "number", token_line, token_column)
            advance(content[pos:end])
            pos = end
            continue

        token_line = line
        token_column = column
        op = _match_operator(content, pos)
        if op:
            add(op, "operator", token_line, token_column)
            advance(op)
            pos += len(op)
            continue
        add(char, "punctuation", token_line, token_column)
        advance(char)
        pos += 1

    return SourceTokens(
        tokens=tokens,
        parens=_matching_pairs(tokens, "(", ")"),
        braces=_matching_pairs(tokens, "{", "}"),
        brackets=_matching_pairs(tokens, "[", "]"),
        comment_lines=comment_lines,
        markers=markers,
    )


def _read_string(source: str, quote: str) -> tuple[str, int]:
    escaped = False
    chars: list[str] = []
    pos = 1
    while pos < len(source):
        char = source[pos]
        if escaped:
            chars.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            return "".join(chars), pos + 1
        else:
            chars.append(char)
        pos += 1
    return "".join(chars), pos


def _match_operator(content: str, pos: int) -> str | None:
    for operator in (
        "===",
        "!==",
        ">>>",
        "<<=",
        ">>=",
        "**=",
        "&&=",
        "||=",
        "??=",
        "=>",
        "?.",
        "??",
        "==",
        "!=",
        "<=",
        ">=",
        "++",
        "--",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&&",
        "||",
        "**",
        "...",
    ):
        if content.startswith(operator, pos):
            return operator
    return None


def _is_identifier_start(char: str) -> bool:
    return char == "$" or char == "_" or char.isalpha()


def _is_identifier_part(char: str) -> bool:
    return _is_identifier_start(char) or char.isdigit()


def _matching_pairs(tokens: list[Token], opener: str, closer: str) -> dict[int, int]:
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for token in tokens:
        if token.value == opener:
            stack.append(token.index)
        elif token.value == closer and stack:
            start = stack.pop()
            pairs[start] = token.index
            pairs[token.index] = start
    return pairs


def _extract_classes(source: SourceTokens) -> list[ClassSpan]:
    classes: list[ClassSpan] = []
    tokens = source.tokens
    for index, token in enumerate(tokens):
        if token.value != "class":
            continue
        name_index = _next_identifier(tokens, index + 1)
        if name_index is None:
            continue
        body_start = _next_value(tokens, "{", name_index + 1)
        if body_start is None or body_start not in source.braces:
            continue
        body_end = source.braces[body_start]
        bases = _class_bases(tokens, name_index + 1, body_start)
        abstract = any(t.value == "abstract" for t in tokens[max(0, index - 2) : index])
        class_span = ClassSpan(
            name=tokens[name_index].value,
            start_idx=index,
            end_idx=body_end,
            body_start=body_start,
            body_end=body_end,
            start_line=token.line,
            bases=bases,
            methods=[],
            abstract=abstract,
        )
        class_span.methods = _class_methods(source, class_span)
        classes.append(class_span)
    return classes


def _class_bases(tokens: list[Token], start: int, end: int) -> list[str]:
    for index in range(start, end):
        if tokens[index].value == "extends":
            return [_tokens_text(tokens[index + 1 : end])]
    return []


def _class_methods(source: SourceTokens, class_span: ClassSpan) -> list[FunctionSpan]:
    methods: list[FunctionSpan] = []
    tokens = source.tokens
    index = class_span.body_start + 1
    while index < class_span.body_end:
        token = tokens[index]
        if token.value == "{" and token.index in source.braces:
            index = source.braces[token.index] + 1
            continue
        if token.value in (";", "}", ","):
            index += 1
            continue
        if _inside_any_method(index, methods):
            index += 1
            continue

        member_start = index
        while index < class_span.body_end and tokens[index].value in _MODIFIERS:
            index += 1
        name_index = _member_name_index(tokens, index, class_span.body_end)
        if name_index is None:
            index = member_start + 1
            continue

        after_name = _skip_type_parameters(tokens, name_index + 1, class_span.body_end)
        if after_name < class_span.body_end and tokens[after_name].value == "(":
            method = _method_from_signature(
                source,
                class_span,
                member_start,
                name_index,
                after_name,
            )
            if method is not None:
                methods.append(method)
                index = method.end_idx + 1
                continue
        arrow = _class_field_arrow(source, class_span, member_start, name_index)
        if arrow is not None:
            methods.append(arrow)
            index = arrow.end_idx + 1
            continue
        index = member_start + 1
    return methods


def _method_from_signature(
    source: SourceTokens,
    class_span: ClassSpan,
    member_start: int,
    name_index: int,
    params_start: int,
) -> FunctionSpan | None:
    params_end = source.parens.get(params_start)
    if params_end is None:
        return None
    body_start = _find_body_start(source.tokens, params_end + 1, class_span.body_end)
    if body_start is None or body_start not in source.braces:
        return None
    body_end = source.braces[body_start]
    return FunctionSpan(
        name=source.tokens[name_index].value,
        start_idx=member_start,
        end_idx=body_end,
        body_start=body_start,
        body_end=body_end,
        start_line=source.tokens[member_start].line,
        params=_split_params(source.tokens[params_start + 1 : params_end]),
        is_method=True,
        class_name=class_span.name,
        return_annotation=_return_annotation(source.tokens, params_end + 1, body_start),
    )


def _class_field_arrow(
    source: SourceTokens, class_span: ClassSpan, member_start: int, name_index: int
) -> FunctionSpan | None:
    tokens = source.tokens
    search_end = min(class_span.body_end, name_index + 12)
    equals = _next_value(tokens, "=", name_index + 1, search_end)
    if equals is None:
        return None
    arrow = _next_value(tokens, "=>", equals + 1, search_end + 8)
    if arrow is None:
        return None
    params = _params_before_arrow(source, arrow)
    if params is None:
        return None
    body_start, body_end, body_is_block = _arrow_body(source, arrow)
    if body_start is None:
        return None
    return FunctionSpan(
        name=tokens[name_index].value,
        start_idx=member_start,
        end_idx=body_end,
        body_start=body_start,
        body_end=body_end,
        start_line=tokens[member_start].line,
        params=params,
        is_method=True,
        class_name=class_span.name,
        body_is_block=body_is_block,
    )


def _extract_functions(source: SourceTokens, classes: list[ClassSpan]) -> list[FunctionSpan]:
    functions = [method for class_span in classes for method in class_span.methods]
    seen = {(function.start_idx, function.end_idx) for function in functions}
    tokens = source.tokens
    for index, token in enumerate(tokens):
        if token.value == "function":
            function = _function_declaration(source, index, classes)
        elif token.value == "=>":
            function = _arrow_function(source, index, classes)
        else:
            function = None
        if function is not None and (function.start_idx, function.end_idx) not in seen:
            functions.append(function)
            seen.add((function.start_idx, function.end_idx))
    return sorted(functions, key=lambda span: (span.start_line, span.start_idx))


def _function_declaration(
    source: SourceTokens, function_index: int, classes: list[ClassSpan]
) -> FunctionSpan | None:
    tokens = source.tokens
    name_index = _next_identifier(tokens, function_index + 1)
    if name_index is None:
        params_start = _next_value(tokens, "(", function_index + 1, function_index + 4)
        name = _assignment_name_before(tokens, function_index) or "(anonymous)"
    else:
        params_start = _skip_type_parameters(tokens, name_index + 1, len(tokens))
        name = tokens[name_index].value
    if params_start is None or params_start >= len(tokens) or tokens[params_start].value != "(":
        return None
    params_end = source.parens.get(params_start)
    if params_end is None:
        return None
    body_start = _find_body_start(tokens, params_end + 1, len(tokens))
    if body_start is None or body_start not in source.braces:
        return None
    body_end = source.braces[body_start]
    return FunctionSpan(
        name=name,
        start_idx=function_index,
        end_idx=body_end,
        body_start=body_start,
        body_end=body_end,
        start_line=tokens[function_index].line,
        params=_split_params(tokens[params_start + 1 : params_end]),
        is_method=False,
        return_annotation=_return_annotation(tokens, params_end + 1, body_start),
    )


def _arrow_function(
    source: SourceTokens, arrow_index: int, classes: list[ClassSpan]
) -> FunctionSpan | None:
    params = _params_before_arrow(source, arrow_index)
    if params is None:
        return None
    body_start, body_end, body_is_block = _arrow_body(source, arrow_index)
    if body_start is None:
        return None
    params_start = _arrow_param_start(source, arrow_index)
    name = (
        _assignment_name_before(source.tokens, params_start)
        or _test_call_name_before(source, params_start)
        or "(anonymous)"
    )
    return FunctionSpan(
        name=name,
        start_idx=params_start,
        end_idx=body_end,
        body_start=body_start,
        body_end=body_end,
        start_line=source.tokens[params_start].line,
        params=params,
        is_method=False,
        body_is_block=body_is_block,
    )


def _params_before_arrow(source: SourceTokens, arrow_index: int) -> list[list[Token]] | None:
    tokens = source.tokens
    if arrow_index == 0:
        return None
    previous = tokens[arrow_index - 1]
    if previous.value == ")" and previous.index in source.parens:
        params_start = source.parens[previous.index]
        return _split_params(tokens[params_start + 1 : previous.index])
    if _is_name(previous):
        return [[previous]]
    return None


def _arrow_param_start(source: SourceTokens, arrow_index: int) -> int:
    tokens = source.tokens
    previous = tokens[arrow_index - 1]
    if previous.value == ")" and previous.index in source.parens:
        return source.parens[previous.index]
    return previous.index


def _arrow_body(source: SourceTokens, arrow_index: int) -> tuple[int | None, int, bool]:
    tokens = source.tokens
    body_start = arrow_index + 1
    if body_start >= len(tokens):
        return None, arrow_index, False
    if tokens[body_start].value == "{" and body_start in source.braces:
        return body_start, source.braces[body_start], True
    body_end = body_start
    while body_end + 1 < len(tokens) and tokens[body_end + 1].value not in (",", ";", ")", "]"):
        body_end += 1
    return body_start, body_end, False


def _find_body_start(tokens: list[Token], start: int, end: int) -> int | None:
    for index in range(start, end):
        value = tokens[index].value
        if value == "{":
            return index
        if value in (";", "=>"):
            return None
    return None


def _return_annotation(tokens: list[Token], start: int, end: int) -> str | None:
    colon = _next_value(tokens, ":", start, end)
    if colon is None:
        return None
    return _tokens_text(tokens[colon + 1 : end])


def _split_params(tokens: list[Token]) -> list[list[Token]]:
    params: list[list[Token]] = []
    start = 0
    paren = brace = bracket = 0
    for offset, token in enumerate(tokens):
        if token.value == "(":
            paren += 1
        elif token.value == ")":
            paren -= 1
        elif token.value == "{":
            brace += 1
        elif token.value == "}":
            brace -= 1
        elif token.value == "[":
            bracket += 1
        elif token.value == "]":
            bracket -= 1
        elif token.value == "," and paren == brace == bracket == 0:
            if tokens[start:offset]:
                params.append(tokens[start:offset])
            start = offset + 1
    if tokens[start:]:
        params.append(tokens[start:])
    return [param for param in params if param]


def _member_name_index(tokens: list[Token], start: int, end: int) -> int | None:
    if start >= end:
        return None
    if tokens[start].value == "#" and start + 1 < end and _is_name(tokens[start + 1]):
        return start + 1
    return start if _is_property_name(tokens[start]) else None


def _skip_type_parameters(tokens: list[Token], index: int, end: int) -> int:
    if index >= end or tokens[index].value != "<":
        return index
    depth = 0
    for cursor in range(index, end):
        if tokens[cursor].value == "<":
            depth += 1
        elif tokens[cursor].value == ">":
            depth -= 1
            if depth == 0:
                return cursor + 1
    return index


def _inside_any_method(index: int, methods: list[FunctionSpan]) -> bool:
    return any(method.start_idx <= index <= method.end_idx for method in methods)


def _next_identifier(tokens: list[Token], start: int) -> int | None:
    if start < len(tokens) and _is_name(tokens[start]):
        return start
    return None


def _next_value(tokens: list[Token], value: str, start: int, end: int | None = None) -> int | None:
    real_end = len(tokens) if end is None else min(end, len(tokens))
    for index in range(start, real_end):
        if tokens[index].value == value:
            return index
    return None


def _is_name(token: Token) -> bool:
    return token.kind in {"identifier", "keyword"} and token.value not in {"from", "import"}


def _is_property_name(token: Token) -> bool:
    return _is_name(token) or token.kind in {"number", "string"}


def _assignment_name_before(tokens: list[Token], index: int) -> str | None:
    cursor = index - 1
    while cursor >= 0 and tokens[cursor].value in (":", "?", "async"):
        cursor -= 1
    if cursor >= 0 and tokens[cursor].value == "=":
        left = cursor - 1
        while left >= 0 and tokens[left].value in (":", "?"):
            left -= 1
        if left >= 0 and _is_name(tokens[left]):
            return tokens[left].value
    return None


def _test_call_name_before(source: SourceTokens, index: int) -> str | None:
    tokens = source.tokens
    cursor = index - 1
    while cursor >= 0:
        if (
            tokens[cursor].value == "("
            and cursor in source.parens
            and source.parens[cursor] >= index
            and cursor > 0
            and tokens[cursor - 1].value in _TEST_CALL_NAMES
        ):
            return tokens[cursor - 1].value
        if tokens[cursor].value in (";", "{", "}"):
            return None
        cursor -= 1
    return None


def _own_tokens(
    tokens: list[Token],
    function: FunctionSpan,
    functions: list[FunctionSpan],
    classes: list[ClassSpan],
) -> list[Token]:
    start = function.body_start + (1 if function.body_is_block else 0)
    end = function.body_end - (1 if function.body_is_block else 0)
    excluded = [
        (other.start_idx, other.end_idx)
        for other in functions
        if other is not function and start <= other.start_idx <= end
    ]
    excluded.extend(
        (class_span.start_idx, class_span.end_idx)
        for class_span in classes
        if start <= class_span.start_idx <= end
    )
    return [
        token
        for token in tokens
        if start <= token.index <= end and not _in_ranges(token.index, excluded)
    ]


def _in_ranges(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index <= end for start, end in ranges)


def _module_mutable_names(tokens: list[Token]) -> frozenset[str]:
    names: set[str] = set()
    depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.value == "{":
            depth += 1
        elif token.value == "}":
            depth -= 1
        if depth == 0 and token.value in _DECLARATION_KEYWORDS:
            cursor = index + 1
            while cursor < len(tokens) and tokens[cursor].value not in (";", "\n"):
                if _is_name(tokens[cursor]) and _is_mutable_binding(token.value, tokens, cursor):
                    names.add(tokens[cursor].value)
                comma = _next_value(tokens, ",", cursor + 1)
                semicolon = _next_value(tokens, ";", cursor + 1)
                if comma is None or (semicolon is not None and semicolon < comma):
                    break
                cursor = comma + 1
        index += 1
    return frozenset(names)


def _is_mutable_binding(declaration: str, tokens: list[Token], name_index: int) -> bool:
    name = tokens[name_index].value
    if name.isupper() or (name.startswith("__") and name.endswith("__")):
        return False
    if declaration in {"let", "var"}:
        return True
    next_index = name_index + 1
    return (
        next_index + 1 < len(tokens)
        and tokens[next_index].value == "="
        and tokens[next_index + 1].value in ("{", "[", "new")
    )


def _logical_line_count(tokens: list[Token]) -> int:
    lines = _statement_lines(tokens)
    if lines:
        return len(lines)
    return len({token.line for token in tokens})


def _statement_count(tokens: list[Token]) -> int:
    lines = _statement_lines(tokens)
    return len(lines) if lines else (1 if tokens else 0)


def _statement_lines(tokens: list[Token]) -> set[int]:
    lines: set[int] = set()
    paren_depth = 0
    previous_line = None
    for token in tokens:
        if token.value == "(":
            paren_depth += 1
        elif token.value == ")":
            paren_depth = max(0, paren_depth - 1)
        elif token.value in _STATEMENT_KEYWORDS | _DECLARATION_KEYWORDS:
            lines.add(token.line)
        elif token.value == ";" and paren_depth == 0 and previous_line is not None:
            lines.add(previous_line)
        if token.value != ";":
            previous_line = token.line
    return lines


def _max_chain_depth(tokens: list[Token]) -> int:
    deepest = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not (_is_name(token) or token.value in _FREE_CHAIN_ROOTS):
            index += 1
            continue
        root = token.value
        cursor = index
        dots = 0
        while cursor + 2 < len(tokens):
            separator = tokens[cursor + 1].value
            if separator not in {".", "?."}:
                if separator == "(" and cursor + 1 < len(tokens):
                    close = _scan_close(tokens, cursor + 1, "(", ")")
                    if close is not None:
                        cursor = close
                        continue
                break
            if not _is_property_name(tokens[cursor + 2]):
                break
            dots += 1
            cursor += 2
        depth = dots - 1 if root in _FREE_CHAIN_ROOTS and dots else dots
        deepest = max(deepest, depth)
        index = max(index + 1, cursor + 1)
    return deepest


def _scan_close(tokens: list[Token], start: int, opener: str, closer: str) -> int | None:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index].value == opener:
            depth += 1
        elif tokens[index].value == closer:
            depth -= 1
            if depth == 0:
                return index
    return None


def _function_arity(function: FunctionSpan) -> int:
    return sum(1 for param in function.params if _param_name(param) != "this")


def _boolean_flag_parameters(function: FunctionSpan) -> int:
    return sum(1 for param in function.params if _is_boolean_param(param))


def _is_boolean_param(param: list[Token]) -> bool:
    values = [token.value for token in param]
    if "true" in values or "false" in values:
        return True
    return any(
        values[index] == ":" and values[index + 1] == "boolean" for index in range(len(values) - 1)
    )


def _param_name(param: list[Token]) -> str | None:
    for token in param:
        if _is_name(token) and token.value not in {"readonly", "public", "private", "protected"}:
            return token.value
    return None


def _exception_discipline(source: SourceTokens, tokens: list[Token]) -> int:
    count = 0
    token_indexes = {token.index for token in tokens}
    for token in tokens:
        if token.value != "catch":
            continue
        body_start = _next_value(source.tokens, "{", token.index + 1, token.index + 12)
        if body_start is None or body_start not in source.braces:
            count += 1
            continue
        body_end = source.braces[body_start]
        body = [t for t in source.tokens[body_start + 1 : body_end] if t.index in token_indexes]
        if not body or not any(t.value == "throw" for t in body):
            count += 1
    return count


def _global_state_reach(tokens: list[Token], mutable_names: frozenset[str]) -> int:
    declared = _local_declarations(tokens)
    return len({token.value for token in tokens if token.value in mutable_names - declared})


def _local_declarations(tokens: list[Token]) -> set[str]:
    declared: set[str] = set()
    for index, token in enumerate(tokens[:-1]):
        if token.value in _DECLARATION_KEYWORDS and _is_name(tokens[index + 1]):
            declared.add(tokens[index + 1].value)
    return declared


def _expression_flatness(tokens: list[Token]) -> float:
    grouped = _tokens_by_statement_line(tokens)
    if not grouped:
        return 1.0
    flat = sum(
        1 for statement_tokens in grouped.values() if _operation_weight(statement_tokens) <= 1
    )
    return flat / len(grouped)


def _tokens_by_statement_line(tokens: list[Token]) -> dict[int, list[Token]]:
    statement_lines = _statement_lines(tokens)
    grouped: dict[int, list[Token]] = {line: [] for line in statement_lines}
    current_line = None
    for token in tokens:
        if token.line in grouped:
            current_line = token.line
        if current_line is not None:
            grouped.setdefault(current_line, []).append(token)
        if token.value == ";":
            current_line = None
    if not grouped and tokens:
        grouped = {
            line: [token for token in tokens if token.line == line]
            for line in {t.line for t in tokens}
        }
    return grouped


def _operation_weight(tokens: list[Token]) -> int:
    weight = 0
    for index, token in enumerate(tokens):
        if token.value in _OPERATION_TOKENS:
            weight += 2
        elif _is_call_token(tokens, index):
            weight += 1
    return weight


def _is_call_token(tokens: list[Token], index: int) -> bool:
    return index + 1 < len(tokens) and _is_name(tokens[index]) and tokens[index + 1].value == "("


def _pipeline_linearity(tokens: list[Token]) -> float:
    assigned: Counter[str] = Counter()
    loaded: Counter[str] = Counter()
    for index, token in enumerate(tokens):
        if not _is_name(token) or token.value in _KEYWORDS:
            continue
        if _is_assignment_target(tokens, index):
            assigned[token.value] += 1
        else:
            loaded[token.value] += 1
    if not assigned:
        return 1.0
    linear = sum(1 for name, count in assigned.items() if count == 1 and loaded[name] == 1)
    return linear / len(assigned)


def _is_assignment_target(tokens: list[Token], index: int) -> bool:
    return (
        index + 1 < len(tokens)
        and tokens[index + 1].value in _ASSIGNMENT_OPERATORS
        or index > 0
        and tokens[index - 1].value in _DECLARATION_KEYWORDS
    )


def _import_facts(tokens: list[Token]) -> list[FactRow]:
    facts: list[FactRow] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.value in {"import", "export"}:
            fact, index = _import_or_export_fact(tokens, index)
            if fact is not None:
                facts.append(fact)
                continue
        if token.value == "require" and index + 2 < len(tokens) and tokens[index + 1].value == "(":
            module_token = tokens[index + 2]
            if module_token.kind == "string":
                facts.append(_module_fact(module_token.value, []))
        index += 1
    return facts


def _import_or_export_fact(tokens: list[Token], index: int) -> tuple[FactRow | None, int]:
    end = index
    while end < len(tokens) and tokens[end].value != ";":
        if tokens[end].kind == "string":
            names = _imported_names(tokens[index:end])
            return _module_fact(tokens[end].value, names), end + 1
        end += 1
    return None, end + 1


def _imported_names(tokens: list[Token]) -> list[str]:
    names: list[str] = []
    in_braces = False
    for index, token in enumerate(tokens):
        if token.value == "{":
            in_braces = True
        elif token.value == "}":
            in_braces = False
        elif in_braces and _is_name(token) and token.value != "as":
            if index > 0 and tokens[index - 1].value == "as":
                continue
            names.append(token.value)
        elif token.value == "*" and index + 2 < len(tokens) and tokens[index + 1].value == "as":
            names.append(tokens[index + 2].value)
        elif index == 1 and _is_name(token):
            names.append(token.value)
    return names


def _module_fact(module_specifier: str, names: list[str]) -> FactRow:
    level, module = _module_parts(module_specifier)
    return FactRow(kind="import", payload={"module": module, "names": names, "level": level})


def _module_parts(specifier: str) -> tuple[int, str]:
    if specifier.startswith("."):
        parts = specifier.split("/")
        relative = [part for part in parts if part == ".." or part == "."]
        level = 1 + sum(1 for part in relative if part == "..")
        module_parts = [part for part in parts if part not in {".", "..", ""}]
    else:
        level = 0
        module_parts = [part for part in specifier.split("/") if part]
    clean = []
    for part in module_parts:
        stem = part.rsplit(".", 1)[0] if "." in part else part
        if stem != "index":
            clean.append(stem)
    return max(level, 0), ".".join(clean)


def _callable_facts(
    source: SourceTokens, functions: list[FunctionSpan], classes: list[ClassSpan]
) -> list[FactRow]:
    facts: list[FactRow] = []
    for function in functions:
        own_tokens = _own_tokens(source.tokens, function, functions, classes)
        facts.append(
            FactRow(
                kind="callable",
                payload={
                    "name": function.name,
                    "lineno": function.start_line,
                    "is_method": function.is_method,
                    "class_name": function.class_name,
                    "call_names": _call_names(own_tokens),
                    "computation_weight": _computation_weight(own_tokens),
                    "statements": _statement_count(own_tokens),
                    "nesting": _max_nesting(own_tokens),
                    "returns_value": _returns_value(own_tokens),
                    "return_annotation": function.return_annotation,
                },
            )
        )
    return facts


def _class_facts(source: SourceTokens, classes: list[ClassSpan]) -> list[FactRow]:
    return [
        FactRow(
            kind="class",
            payload={
                "name": class_span.name,
                "lineno": class_span.start_line,
                "bases": class_span.bases,
                "decorators": ["abstract"] if class_span.abstract else [],
                "keywords": [],
                "methods": [_method_payload(source, method) for method in class_span.methods],
            },
        )
        for class_span in classes
    ]


def _method_payload(source: SourceTokens, method: FunctionSpan) -> dict[str, object]:
    fields_read: set[str] = set()
    fields_written: set[str] = set()
    calls_local: set[str] = set()
    tokens = source.tokens[method.body_start + 1 : method.body_end]
    for index, token in enumerate(tokens[:-2]):
        if token.value not in {"this", "super"} or tokens[index + 1].value not in {".", "?."}:
            continue
        field = tokens[index + 2].value
        if tokens[index + 3].value == "(" if index + 3 < len(tokens) else False:
            calls_local.add(field)
        elif tokens[index + 3].value in _ASSIGNMENT_OPERATORS if index + 3 < len(tokens) else False:
            fields_written.add(field)
        else:
            fields_read.add(field)
    fields_read -= calls_local
    return {
        "name": method.name,
        "decorators": [],
        "fields_read": sorted(fields_read),
        "fields_written": sorted(fields_written),
        "calls_local": sorted(calls_local),
    }


def _imported_local_names(imports: list[FactRow]) -> set[str]:
    names: set[str] = set()
    for fact in imports:
        names.update(str(name) for name in fact.payload.get("names", []))
        module = str(fact.payload.get("module", ""))
        if module:
            names.add(module.split(".")[-1])
    return names


def _coupling_between_objects(
    source: SourceTokens, class_span: ClassSpan, imported_names: set[str]
) -> int:
    tokens = source.tokens[class_span.body_start + 1 : class_span.body_end]
    return len({token.value for token in tokens if token.value in imported_names})


def _call_names(tokens: list[Token]) -> list[str]:
    names: set[str] = set()
    for index, token in enumerate(tokens[:-1]):
        if token.value in _CONTROL_KEYWORDS or token.value == "function":
            continue
        if (
            token.value == "."
            and index > 0
            and index + 2 < len(tokens)
            and tokens[index + 2].value == "("
        ):
            if _is_property_name(tokens[index + 1]):
                names.add(tokens[index + 1].value)
        elif _is_name(token) and tokens[index + 1].value == "(":
            names.add(token.value)
    return sorted(names)


def _computation_weight(tokens: list[Token]) -> int:
    return sum(2 for token in tokens if token.value in _OPERATION_TOKENS)


def _max_nesting(tokens: list[Token]) -> int:
    depth = 0
    deepest = 0
    pending_control = False
    for token in tokens:
        if token.value in _CONTROL_KEYWORDS | {"try"}:
            pending_control = True
        elif token.value == "{" and pending_control:
            depth += 1
            deepest = max(deepest, depth)
            pending_control = False
        elif token.value == "}":
            depth = max(0, depth - 1)
            pending_control = False
        elif token.value not in ("(", ")"):
            pending_control = False
    return deepest


def _returns_value(tokens: list[Token]) -> bool:
    for index, token in enumerate(tokens):
        if token.value == "return":
            return index + 1 < len(tokens) and tokens[index + 1].value not in {";", "}"}
    return False


def _is_test_function(name: str) -> bool:
    return name == "test" or name == "it" or name.startswith("test_") or name.endswith(".test")


def _assertions_per_test(tokens: list[Token]) -> int:
    return sum(1 for index, token in enumerate(tokens[:-1]) if _is_assertion_call(tokens, index))


def _mock_call_assertions(tokens: list[Token]) -> int:
    count = 0
    for token in tokens:
        if any(token.value.startswith(name) for name in _MOCK_ASSERT_NAMES):
            count += 1
    return count


def _big_literal_assertions(source: SourceTokens, tokens: list[Token]) -> int:
    count = 0
    assertion_lines = {
        token.line for index, token in enumerate(tokens[:-1]) if _is_assertion_call(tokens, index)
    }
    for token in tokens:
        if token.line in assertion_lines and token.value in {"[", "{"}:
            close_map = source.brackets if token.value == "[" else source.braces
            close = close_map.get(token.index)
            if (
                close is not None
                and _literal_element_count(source.tokens[token.index + 1 : close])
                >= _BIG_LITERAL_FLOOR
            ):
                count += 1
    return count


def _is_assertion_call(tokens: list[Token], index: int) -> bool:
    token = tokens[index]
    return (
        token.value in {"assert", "expect"}
        and index + 1 < len(tokens)
        and tokens[index + 1].value == "("
        or token.value.startswith("assert")
        and index + 1 < len(tokens)
        and tokens[index + 1].value == "("
    )


def _literal_element_count(tokens: list[Token]) -> int:
    if not tokens:
        return 0
    depth = 0
    commas = 0
    has_value = False
    for token in tokens:
        if token.value in {"[", "{", "("}:
            depth += 1
        elif token.value in {"]", "}", ")"}:
            depth -= 1
        elif token.value == "," and depth == 0:
            commas += 1
        elif depth == 0:
            has_value = True
    return commas + 1 if has_value else 0


def _tokens_text(tokens: list[Token]) -> str:
    return " ".join(token.value for token in tokens).strip()
