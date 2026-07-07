"""Duplication deriver: WET-code detection via the pydry engine.

Track A of the adoption plan (docs/design/test-suite-health.md names the
test-tree application too). pydry — the owner's own clone-detection engine —
finds exact structural duplicates after syntax-tree normalization (Type-2
clones: local names and constants normalizable). This deriver is
**config-gated on presence** of a ``duplication`` block, unlike the
informational-first derivers: pydry re-parses the tree on every run, so the
default command path must not pay for it. Merkle-tree memoization (see
structural-metrics-caching.md) is the recorded follow-up if the cost ever
matters at scale.

The PyPI package is named pydry-cli; the import module is pydry. The runtime
dependency is still probed defensively so a broken environment yields a
diagnostic row instead of crashing a full report run.
"""

from __future__ import annotations

from collections import defaultdict
import importlib.util
from pathlib import Path
from typing import Any

from antipasta.core.model.config import DuplicationConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import ProjectReport, Violation, check_metric_violation


def pydry_available() -> bool:
    """Is the pydry engine importable?"""
    try:
        return importlib.util.find_spec("pydry.engine") is not None
    except ModuleNotFoundError:
        return False


def derive_duplication(derivation_input: DerivationInput) -> list[ProjectReport]:
    """Clone groups + per-file duplication ratios, when configured."""
    config = derivation_input.config.duplication
    if config is None:
        return []
    if not pydry_available():
        return [_unavailable_report()]

    groups = _exact_groups(derivation_input.root, config)
    if not groups:
        return []
    sloc_by_file = _sloc_by_relative_path(derivation_input)
    return [
        *_group_reports(groups, derivation_input.root),
        *_file_reports(groups, derivation_input.root, sloc_by_file, config),
    ]


def _unavailable_report() -> ProjectReport:
    row = MetricResult(
        file_path=Path("."),
        metric_type=MetricType.CLONE_OCCURRENCES,
        value=0.0,
        details={"unavailable": "pydry engine is unavailable; reinstall antipasta"},
    )
    return ProjectReport(subject="duplication", metrics=[row], violations=[])


def _exact_groups(root: Path, config: DuplicationConfig) -> list[Any]:
    from pydry.engine import exact_groups

    groups: list[Any] = exact_groups(
        root,
        min_count=config.min_count,
        normalize_local_names=config.normalize_local_names,
        normalize_constants=config.normalize_constants,
    )
    return groups


def _sloc_by_relative_path(derivation_input: DerivationInput) -> dict[str, float]:
    sloc: dict[str, float] = {}
    root = derivation_input.root
    for report in derivation_input.file_reports:
        try:
            relative = str(report.file_path.resolve().relative_to(root))
        except ValueError:
            continue
        for metric in report.metrics:
            if metric.metric_type is MetricType.SOURCE_LINES_OF_CODE:
                sloc[relative] = metric.value
    return sloc


def _group_reports(groups: list[Any], root: Path) -> list[ProjectReport]:
    reports = []
    for group in groups:
        members = [_member_label(occurrence, root) for occurrence in group.occurrences]
        name = group.occurrences[0].name
        row = MetricResult(
            file_path=Path(_relative(group.occurrences[0].path, root)),
            metric_type=MetricType.CLONE_OCCURRENCES,
            value=float(group.count),
            details={"members": members[:10]},
        )
        reports.append(
            ProjectReport(
                subject=f"clone-group: {name} x{group.count}",
                metrics=[row],
                violations=[],
            )
        )
    return reports


def _file_reports(
    groups: list[Any],
    root: Path,
    sloc_by_file: dict[str, float],
    config: DuplicationConfig,
) -> list[ProjectReport]:
    duplicated: dict[str, int] = defaultdict(int)
    for group in groups:
        for occurrence in group.occurrences:
            span = (occurrence.end_lineno or occurrence.lineno) - occurrence.lineno + 1
            duplicated[_relative(occurrence.path, root)] += span

    reports = []
    for relative_path in sorted(duplicated):
        sloc = sloc_by_file.get(relative_path)
        ratio = duplicated[relative_path] / sloc if sloc else 0.0
        row = MetricResult(
            file_path=Path(relative_path),
            metric_type=MetricType.DUPLICATION_RATIO,
            value=round(min(ratio, 1.0), 4),
            details={"duplicated_lines": duplicated[relative_path]},
        )
        violations: list[Violation] = []
        if config.max_ratio is not None:
            violation = check_metric_violation(row, config.ratio_gate())
            if violation:
                violations.append(violation)
        reports.append(ProjectReport(subject=relative_path, metrics=[row], violations=violations))
    return reports


def _relative(path: Any, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root))
    except ValueError:
        return str(path)


def _member_label(occurrence: Any, root: Path) -> str:
    return f"{_relative(occurrence.path, root)}:{occurrence.lineno} {occurrence.qualname}"
