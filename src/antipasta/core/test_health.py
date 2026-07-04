"""Coverage-matrix analytics (track D2): redundancy and blast radius.

Artifact ingestion, never execution: antipasta reads a coverage.py data file
recorded with dynamic contexts (``pytest --cov --cov-context=test``) — the
same provider posture as the llvm-cov discussion. From the test×line matrix:

- **unique-coverage ratio** per test: lines only this test covers ÷ lines it
  covers. Zero-unique tests are redundancy *candidates* (line subsumption is
  not semantic redundancy — the honesty label rides in details).
- **suite redundancy index**: 1 − greedy-set-cover size ÷ suite size — "this
  share of tests adds no line coverage the rest doesn't already provide."
- **blast radius** per file: distinct tests executing it — the direct
  predictor of "a hundred tests break."

The coverage package is an optional runtime dependency (present wherever
pytest-cov is); absent, the loader raises a clear message.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from antipasta.core.metrics import MetricResult, MetricType
from antipasta.core.violations import ProjectReport

#: At most this many rows per section.
_TOP_LIMIT = 15


@dataclass
class CoverageMatrix:
    """test context → set of covered (file, line) pairs."""

    lines_by_test: dict[str, set[tuple[str, int]]] = field(default_factory=dict)

    @property
    def test_count(self) -> int:
        return len(self.lines_by_test)


def load_matrix(coverage_file: Path) -> CoverageMatrix:
    """Read a contexts-enabled coverage.py data file into the matrix."""
    try:
        from coverage import CoverageData
    except ImportError as error:  # pragma: no cover - env-dependent
        raise RuntimeError(
            "the coverage package is required to read coverage artifacts "
            "(pip install coverage)"
        ) from error

    data = CoverageData(basename=str(coverage_file))
    data.read()
    matrix = CoverageMatrix()
    for measured in data.measured_files():
        contexts_by_line = data.contexts_by_lineno(measured)
        for line, contexts in contexts_by_line.items():
            for context in contexts:
                test = _test_of_context(context)
                if test is None:
                    continue
                matrix.lines_by_test.setdefault(test, set()).add((measured, line))
    return matrix


def _test_of_context(context: str) -> str | None:
    """pytest-cov contexts look like 'tests/unit/test_x.py::TestC::test_m|run'."""
    if not context:
        return None
    return context.split("|")[0] or None


# ── analytics ───────────────────────────────────────────────────────────────


def unique_coverage(matrix: CoverageMatrix) -> dict[str, float]:
    """Per test: share of its covered lines nobody else covers."""
    coverers: dict[tuple[str, int], int] = defaultdict(int)
    for lines in matrix.lines_by_test.values():
        for line in lines:
            coverers[line] += 1
    ratios = {}
    for test, lines in matrix.lines_by_test.items():
        if not lines:
            ratios[test] = 0.0
            continue
        unique = sum(1 for line in lines if coverers[line] == 1)
        ratios[test] = unique / len(lines)
    return ratios


def redundancy_index(matrix: CoverageMatrix) -> tuple[float, int]:
    """(1 − greedy-cover size ÷ suite size, cover size)."""
    remaining: set[tuple[str, int]] = set()
    for lines in matrix.lines_by_test.values():
        remaining |= lines
    chosen = 0
    pool = dict(matrix.lines_by_test)
    while remaining and pool:
        best_test = max(pool, key=lambda test: len(pool[test] & remaining))
        gain = pool.pop(best_test) & remaining
        if not gain:
            break
        remaining -= gain
        chosen += 1
    total = matrix.test_count
    return (1.0 - chosen / total, chosen) if total else (0.0, 0)


def blast_radius(matrix: CoverageMatrix) -> dict[str, int]:
    """Per file: distinct tests executing any of its lines."""
    tests_by_file: dict[str, set[str]] = defaultdict(set)
    for test, lines in matrix.lines_by_test.items():
        for file_path, _ in lines:
            tests_by_file[file_path].add(test)
    return {file_path: len(tests) for file_path, tests in tests_by_file.items()}


# ── reports ─────────────────────────────────────────────────────────────────


def matrix_reports(matrix: CoverageMatrix) -> list[ProjectReport]:
    """The D2 report set for one coverage artifact."""
    index, cover_size = redundancy_index(matrix)
    ratios = unique_coverage(matrix)
    zero_unique = sorted(test for test, ratio in ratios.items() if ratio == 0.0)
    suite_row = MetricResult(
        file_path=Path("."),
        metric_type=MetricType.SUITE_REDUNDANCY_INDEX,
        value=round(index, 4),
        details={
            "tests": matrix.test_count,
            "greedy_cover_size": cover_size,
            "zero_unique_tests": len(zero_unique),
            "zero_unique_sample": zero_unique[:_TOP_LIMIT],
            "note": "line-coverage subsumption; candidates, not verdicts",
        },
    )
    reports = [
        ProjectReport(subject="suite-redundancy", metrics=[suite_row], violations=[])
    ]
    radii = blast_radius(matrix)
    for file_path in sorted(radii, key=lambda key: -radii[key])[:_TOP_LIMIT]:
        row = MetricResult(
            file_path=Path(file_path),
            metric_type=MetricType.BLAST_RADIUS,
            value=float(radii[file_path]),
        )
        reports.append(
            ProjectReport(subject=file_path, metrics=[row], violations=[])
        )
    return reports
