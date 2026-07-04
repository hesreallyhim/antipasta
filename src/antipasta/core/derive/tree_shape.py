"""Module Tree Shape, tree half: bounded fan-out over the analyzed tree.

The owner's architectural house style at directory scale: every package has
roughly 5–7 children (modules or subpackages) — too many means a missing
layer, too few means a pointless one. This deriver is the pilot for
project-scoped reporting: it consumes only the analyzed file list (no
parsing, no per-file facts), emits one ``directory_children`` row per
directory, and raises violations only when a ``tree_shape`` config block is
present — informational-first, per the dogfooding policy.

Language-agnostic by construction: children are counted from paths, so this
works for any analyzed language. The layering half (imports must flow
downward) arrives with the import graph in Phase 3.
"""

from __future__ import annotations

from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from antipasta.core.model.config import TreeShapeConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import ProjectReport, Violation, check_metric_violation

#: Subject label for the analysis root directory.
ROOT_SUBJECT = "."

#: Plumbing files that don't count as a directory's children.
_NON_CHILD_FILES = frozenset({"__init__.py", "__main__.py"})


def derive_layering(derivation_input: DerivationInput) -> list[ProjectReport]:
    """Upward-import checks against the configured layer order.

    Layers are listed top to bottom; an earlier layer may import later ones
    (cli reaching down into core is the architecture working); a later layer
    importing an earlier one is an upward violation. Modules whose top
    segment matches no layer are ignored. Without a configured order there
    is nothing to compute — no invented ordering.
    """
    config = derivation_input.config.tree_shape
    if config is None or not config.layers:
        return []
    from antipasta.core.derive.import_graph import build_module_graph

    graph = build_module_graph(derivation_input)
    layer_index = {name: index for index, name in enumerate(config.layers)}
    reports = []
    for module in sorted(graph):
        source_layer = layer_index.get(module.split(".")[0])
        if source_layer is None:
            continue
        upward = _upward_targets(module, graph[module], source_layer, layer_index)
        row = MetricResult(
            file_path=Path(module.replace(".", "/") + ".py"),
            metric_type=MetricType.LAYERING_VIOLATIONS,
            value=float(len(upward)),
            details={"upward": upward[:10]} if upward else None,
        )
        violation = check_metric_violation(row, config.layering_config())
        reports.append(
            ProjectReport(
                subject=module,
                metrics=[row],
                violations=[violation] if violation else [],
            )
        )
    return reports


def _upward_targets(
    module: str,
    targets: set[str],
    source_layer: int,
    layer_index: dict[str, int],
) -> list[str]:
    upward = []
    for target in sorted(targets):
        target_layer = layer_index.get(target.split(".")[0])
        if target_layer is not None and target_layer < source_layer:
            upward.append(target)
    return upward


def derive_tree_shape(derivation_input: DerivationInput) -> list[ProjectReport]:
    """One ProjectReport per analyzed directory, with fan-out counts."""
    children_by_directory = _count_children(derivation_input)
    config = derivation_input.config.tree_shape
    reports = []
    for directory in sorted(children_by_directory):
        child_count = children_by_directory[directory]
        if config is not None and _is_excluded(directory, config.exclude):
            continue
        reports.append(_directory_report(directory, child_count, config))
    return reports


def _count_children(derivation_input: DerivationInput) -> dict[str, int]:
    """Fan-out per directory: immediate module files + immediate subpackages."""
    root = derivation_input.root
    module_children: dict[str, int] = defaultdict(int)
    subdirectories: dict[str, set[str]] = defaultdict(set)

    for report in derivation_input.file_reports:
        relative = _relative_to_root(report.file_path, root)
        if relative is None:
            continue
        parent = _subject_of(relative.parent)
        if relative.name not in _NON_CHILD_FILES:
            module_children[parent] += 1
        for directory, ancestor in _parent_pairs(relative):
            subdirectories[ancestor].add(directory)

    directories = set(module_children) | set(subdirectories)
    return {
        directory: module_children[directory] + len(subdirectories[directory])
        for directory in directories
    }


def _relative_to_root(file_path: Path, root: Path) -> PurePosixPath | None:
    try:
        return PurePosixPath(file_path.resolve().relative_to(root).as_posix())
    except ValueError:
        return None


def _subject_of(directory: PurePosixPath) -> str:
    label = directory.as_posix()
    return ROOT_SUBJECT if label == "" else label


def _parent_pairs(relative_file: PurePosixPath) -> list[tuple[str, str]]:
    """(directory, its parent) for every ancestor directory of the file."""
    pairs = []
    directory = relative_file.parent
    while directory.as_posix() != ".":
        pairs.append((_subject_of(directory), _subject_of(directory.parent)))
        directory = directory.parent
    return pairs


def _is_excluded(subject: str, patterns: list[str]) -> bool:
    return any(fnmatch(subject, pattern) for pattern in patterns)


def _directory_report(
    subject: str, child_count: int, config: TreeShapeConfig | None
) -> ProjectReport:
    row = MetricResult(
        file_path=Path(subject),
        metric_type=MetricType.DIRECTORY_CHILDREN,
        value=float(child_count),
    )
    violations: list[Violation] = []
    if config is not None:
        violations.extend(_band_violations(row, subject, config))
    return ProjectReport(subject=subject, metrics=[row], violations=violations)


def _band_violations(
    row: MetricResult, subject: str, config: TreeShapeConfig
) -> list[Violation]:
    """Fan-out band checks: too many children (missing layer) always applies;
    too few (pointless layer) exempts the root, which legitimately fans wide
    or narrow depending on project size."""
    checks = [config.max_children_config()]
    if subject != ROOT_SUBJECT:
        checks.append(config.min_children_config())
    violations = []
    for metric_config in checks:
        violation = check_metric_violation(row, metric_config)
        if violation:
            violations.append(violation)
    return violations
