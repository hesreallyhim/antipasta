"""Import-graph deriver: the dependency half of the SOLID suite.

Builds the module dependency graph from the raw import facts (extraction
stays path-independent; all resolution happens here, where the module table
is known) and derives Robert Martin's coupling metrics per module — efferent
and afferent coupling, instability — plus dependency cycles via an iterative
strongly-connected-components pass, stable-dependencies violations, and
package-level rollups.

Resolution is a documented approximation (labeled where it matters): targets
are matched longest-prefix-first against the analyzed module set, with
leading-package stripping so a src-layout analysis root (``-d src/pkg``)
still matches absolute imports (``pkg.core.x`` → ``core.x``). Imports that
resolve outside the analyzed set are external: they count toward nothing
here (external coupling is a Phase 4 concern).

Gating is opt-in like everything else: rows are informational until an
``import_graph`` config block exists; with one, cycles violate (the Acyclic
Dependencies Principle) and stable-dependencies violations gate on count.
"""

from __future__ import annotations

from pathlib import Path

from antipasta.core.abstractness import (
    dependency_inversion,
    distance_from_main_sequence,
    module_abstractness,
)
from antipasta.core.config import ImportGraphConfig
from antipasta.core.derivation import DerivationInput
from antipasta.core.metrics import FactRow, MetricResult, MetricType
from antipasta.core.violations import ProjectReport, Violation, check_metric_violation

#: Instability delta below which an edge toward a more-unstable module is
#: tolerated by the stable-dependencies check.
_SDP_TOLERANCE = 0.2


def derive_import_graph(derivation_input: DerivationInput) -> list[ProjectReport]:
    """Module coupling rows, cycle reports, and package rollups."""
    graph = _build_graph(derivation_input)
    if not graph:
        return []
    config = derivation_input.config.import_graph
    abstractness_by_module = _abstractness_by_module(derivation_input)
    return [
        *_module_reports(graph, config, abstractness_by_module),
        *_cycle_reports(graph, config),
        *_package_reports(graph),
    ]


def _abstractness_by_module(derivation_input: DerivationInput) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for file_path, facts in derivation_input.facts_by_file.items():
        module = _module_name(file_path, derivation_input.root)
        if module is not None:
            values[module] = module_abstractness(facts)
    return values


# ── graph construction ──────────────────────────────────────────────────────


def _build_graph(derivation_input: DerivationInput) -> dict[str, set[str]]:
    """module → set of analyzed modules it imports (self-edges dropped)."""
    root = derivation_input.root
    module_of: dict[Path, str] = {}
    for file_path in derivation_input.facts_by_file:
        module = _module_name(file_path, root)
        if module is not None:
            module_of[file_path] = module

    known = set(module_of.values())
    graph: dict[str, set[str]] = {module: set() for module in known}
    for file_path, facts in derivation_input.facts_by_file.items():
        source = module_of.get(file_path)
        if source is None:
            continue
        for target in _resolved_targets(facts, source, known):
            if target != source and not _is_ancestor_edge(source, target):
                graph[source].add(target)
    return graph


def _is_ancestor_edge(source: str, target: str) -> bool:
    """A module importing its own ancestor package is re-export plumbing.

    Owner decision (2026-07-04): the cycles metric should mean VICIOUS
    circles. Child→ancestor edges (``cli.main`` importing ``cli``) exist in
    every package that re-exports its members and would otherwise report
    every such package as a cycle; dropping them leaves only cycles between
    genuinely separate modules. Parent→child edges are kept — a package
    aggregating its children is acyclic on its own.
    """
    return source.startswith(target + ".")


def _module_name(file_path: Path, root: Path) -> str | None:
    try:
        relative = file_path.resolve().relative_to(root)
    except ValueError:
        return None
    parts = relative.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def _resolved_targets(facts: list[FactRow], source: str, known: set[str]) -> set[str]:
    targets: set[str] = set()
    for fact in facts:
        if fact.kind != "import":
            continue
        payload = fact.payload
        prefix = _import_prefix(payload["module"], payload["level"], source)
        targets.update(_resolve_statement(prefix, payload["names"], known))
    return targets


def _import_prefix(module: str, level: int, source: str) -> str:
    """The dotted prefix an import statement addresses (relative dots applied)."""
    if level == 0:
        return module
    base_parts = source.split(".")[:-level] if level <= source.count(".") + 1 else []
    return ".".join([*base_parts, module]) if module else ".".join(base_parts)


def _resolve_statement(prefix: str, names: list[str], known: set[str]) -> set[str]:
    """Resolve one import statement against the analyzed module set.

    `from X import name`: name may be a submodule (X.name) or a symbol
    defined in X — the specific submodule wins; the package is only the
    fallback when the submodule doesn't exist.
    """
    if not names:
        resolved = _match_known(prefix, known) if prefix else None
        return {resolved} if resolved else set()
    targets: set[str] = set()
    for name in names:
        candidate = f"{prefix}.{name}" if prefix else name
        resolved = _match_known(candidate, known)
        if resolved is None and prefix:
            resolved = _match_known(prefix, known)
        if resolved is not None:
            targets.add(resolved)
    return targets


def _match_known(candidate: str, known: set[str]) -> str | None:
    """Longest-prefix match, with leading-package stripping for src layouts."""
    parts = candidate.split(".")
    for strip in range(len(parts)):
        remaining = parts[strip:]
        for end in range(len(remaining), 0, -1):
            name = ".".join(remaining[:end])
            if name in known:
                return name
        if strip == 0 and parts[0] in known:
            break  # exact head already known; deeper strips would mis-match
    return None


# ── module metrics ──────────────────────────────────────────────────────────


def _module_reports(
    graph: dict[str, set[str]],
    config: ImportGraphConfig | None,
    abstractness_by_module: dict[str, float | None],
) -> list[ProjectReport]:
    afferent = _afferent_counts(graph)
    instability = _instability_map(graph, afferent)
    reports = []
    for module in sorted(graph):
        rows = _coupling_rows(module, graph, afferent, instability)
        sdp_row = rows[-1]
        rows.extend(
            _main_sequence_rows(module, graph, instability, abstractness_by_module)
        )
        violations = _sdp_violations(sdp_row, config)
        reports.append(ProjectReport(subject=module, metrics=rows, violations=violations))
    return reports


def _main_sequence_rows(
    module: str,
    graph: dict[str, set[str]],
    instability: dict[str, float],
    abstractness_by_module: dict[str, float | None],
) -> list[MetricResult]:
    """Abstractness, Distance, and dependency-inversion rows (all labeled
    approximate; abstractness/distance only for modules with classes)."""
    subject_path = Path(module.replace(".", "/") + ".py")
    rows: list[MetricResult] = []
    abstractness = abstractness_by_module.get(module)
    if abstractness is not None:
        distance = distance_from_main_sequence(abstractness, instability[module])
        rows.extend(
            MetricResult(
                file_path=subject_path,
                metric_type=metric_type,
                value=round(value, 4),
                details={"approximate": True},
            )
            for metric_type, value in (
                (MetricType.ABSTRACTNESS, abstractness),
                (MetricType.DISTANCE_FROM_MAIN_SEQUENCE, distance),
            )
        )
    inversion = dependency_inversion(graph[module], abstractness_by_module)
    if inversion is not None:
        rows.append(
            MetricResult(
                file_path=subject_path,
                metric_type=MetricType.DEPENDENCY_INVERSION,
                value=round(inversion, 4),
                details={"approximate": True, "targets": len(graph[module])},
            )
        )
    return rows


def _afferent_counts(graph: dict[str, set[str]]) -> dict[str, int]:
    counts = dict.fromkeys(graph, 0)
    for targets in graph.values():
        for target in targets:
            counts[target] += 1
    return counts


def _instability_map(
    graph: dict[str, set[str]], afferent: dict[str, int]
) -> dict[str, float]:
    instability = {}
    for module, targets in graph.items():
        efferent = len(targets)
        total = efferent + afferent[module]
        instability[module] = efferent / total if total else 0.0
    return instability


def _coupling_rows(
    module: str,
    graph: dict[str, set[str]],
    afferent: dict[str, int],
    instability: dict[str, float],
) -> list[MetricResult]:
    subject_path = Path(module.replace(".", "/") + ".py")
    sdp_count = sum(
        1
        for target in graph[module]
        if instability[target] - instability[module] > _SDP_TOLERANCE
    )
    values = [
        (MetricType.EFFERENT_COUPLING, float(len(graph[module])), None),
        (MetricType.AFFERENT_COUPLING, float(afferent[module]), None),
        (MetricType.INSTABILITY, round(instability[module], 4), None),
        (
            MetricType.STABLE_DEPENDENCIES_VIOLATIONS,
            float(sdp_count),
            {"tolerance": _SDP_TOLERANCE},
        ),
    ]
    return [
        MetricResult(file_path=subject_path, metric_type=metric_type, value=value, details=details)
        for metric_type, value, details in values
    ]


def _sdp_violations(
    sdp_row: MetricResult, config: ImportGraphConfig | None
) -> list[Violation]:
    if config is None:
        return []
    violation = check_metric_violation(sdp_row, config.stable_dependencies_config())
    return [violation] if violation else []


# ── cycles ──────────────────────────────────────────────────────────────────


def _cycle_reports(
    graph: dict[str, set[str]], config: ImportGraphConfig | None
) -> list[ProjectReport]:
    reports = []
    for component in _strongly_connected(graph):
        if len(component) < 2:
            continue
        members = sorted(component)
        row = MetricResult(
            file_path=Path(members[0].replace(".", "/") + ".py"),
            metric_type=MetricType.DEPENDENCY_CYCLES,
            value=float(len(members)),
            details={"members": members},
        )
        violations = []
        if config is not None and config.forbid_cycles:
            violation = check_metric_violation(row, config.cycles_config())
            if violation:
                violations.append(violation)
        subject = "cycle: " + " <-> ".join(members)
        reports.append(ProjectReport(subject=subject, metrics=[row], violations=violations))
    return reports


def _strongly_connected(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's algorithm, iterative (no recursion limit on deep graphs)."""
    return _Tarjan(graph).components()


class _Tarjan:
    """Iterative Tarjan bookkeeping, decomposed into named steps."""

    def __init__(self, graph: dict[str, set[str]]) -> None:
        self.graph = graph
        self.index_counter = 0
        self.indices: dict[str, int] = {}
        self.lowlink: dict[str, int] = {}
        self.on_stack: set[str] = set()
        self.stack: list[str] = []
        self.result: list[list[str]] = []

    def components(self) -> list[list[str]]:
        for start in self.graph:
            if start not in self.indices:
                self._explore(start)
        return self.result

    def _explore(self, start: str) -> None:
        self._open(start)
        work: list[tuple[str, list[str]]] = [(start, list(self.graph[start]))]
        while work:
            node, pending = work[-1]
            if pending:
                self._visit(node, pending.pop(), work)
            else:
                work.pop()
                self._close(node, work)

    def _open(self, node: str) -> None:
        self.indices[node] = self.lowlink[node] = self.index_counter
        self.index_counter += 1
        self.stack.append(node)
        self.on_stack.add(node)

    def _visit(self, node: str, neighbor: str, work: list[tuple[str, list[str]]]) -> None:
        if neighbor not in self.indices:
            self._open(neighbor)
            work.append((neighbor, list(self.graph[neighbor])))
        elif neighbor in self.on_stack:
            self.lowlink[node] = min(self.lowlink[node], self.indices[neighbor])

    def _close(self, node: str, work: list[tuple[str, list[str]]]) -> None:
        if work:
            parent = work[-1][0]
            self.lowlink[parent] = min(self.lowlink[parent], self.lowlink[node])
        if self.lowlink[node] == self.indices[node]:
            self.result.append(self._pop_component(node))

    def _pop_component(self, node: str) -> list[str]:
        component = []
        while True:
            member = self.stack.pop()
            self.on_stack.discard(member)
            component.append(member)
            if member == node:
                return component


# ── package rollup ──────────────────────────────────────────────────────────


def _package_reports(graph: dict[str, set[str]]) -> list[ProjectReport]:
    """Coupling between packages: the module graph collapsed one level up."""
    package_graph: dict[str, set[str]] = {}
    for module, targets in graph.items():
        source_package = _package_of(module)
        edges = package_graph.setdefault(source_package, set())
        for target in targets:
            target_package = _package_of(target)
            if target_package != source_package:
                edges.add(target_package)

    afferent = _afferent_counts(package_graph)
    reports = []
    for package in sorted(package_graph):
        subject_path = Path(package.replace(".", "/"))
        rows = [
            MetricResult(
                file_path=subject_path,
                metric_type=MetricType.EFFERENT_COUPLING,
                value=float(len(package_graph[package])),
            ),
            MetricResult(
                file_path=subject_path,
                metric_type=MetricType.AFFERENT_COUPLING,
                value=float(afferent[package]),
            ),
        ]
        reports.append(
            ProjectReport(subject=f"package {package}", metrics=rows, violations=[])
        )
    return reports


def _package_of(module: str) -> str:
    return module.rsplit(".", 1)[0] if "." in module else "(top)"
