"""Comment-stream analyzers: marker density and comment density."""

from __future__ import annotations

import io
import re
import tokenize

_MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def comment_lines_and_markers(content: str) -> tuple[int, int]:
    """Count distinct comment lines and debt markers (TODO/FIXME/HACK/XXX)."""
    comment_line_numbers: set[int] = set()
    markers = 0
    try:
        tokens = tokenize.generate_tokens(io.StringIO(content).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                comment_line_numbers.add(token.start[0])
                markers += len(_MARKER_PATTERN.findall(token.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass  # unparseable tail: report what was tokenized so far
    return len(comment_line_numbers), markers


def total_lines(content: str) -> int:
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def marker_density(markers: int, line_count: int) -> float:
    """Debt markers per thousand lines."""
    if line_count == 0:
        return 0.0
    return markers / line_count * 1000.0


def comment_density(comment_line_count: int, line_count: int) -> float:
    """Comment lines as a percentage of physical lines."""
    if line_count == 0:
        return 0.0
    return comment_line_count / line_count * 100.0
