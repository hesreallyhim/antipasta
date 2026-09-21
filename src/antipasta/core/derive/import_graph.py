"""Import-graph deriver: the dependency half of the SOLID suite.

Builds the module dependency graph from the raw import facts (extraction
stays path-independent; all resolution happens here, where the module table
is known) and derives Robert Martin's coupling metrics per module — efferent
and afferent coupling, instability — plus dependency cycles via an iterative
strongly-connected-components pass, stable-dependencies violations, and
package-level rollups.

Resolution is a documented approximation (labeled where it matters): targets
are matched longest-prefix-first against the analyzed module set. Relative
imports resolve directly. Absolute imports resolve only through the analyzed
package's own name when the root is a package (``-d src/pkg`` makes
``pkg.core.x`` → ``core.x``, while ``import subprocess`` inside ``pkg`` stays
external even if ``pkg/subprocess.py`` exists); a non-package root (``-d
src``) matches absolute imports as written. Imports that resolve outside the
analyzed set are external: they count toward nothing here.

Only imports that execute at module import time are dependency edges.
Imports deferred into function bodies or guarded by ``TYPE_CHECKING`` are
how Python code breaks cycles on purpose, so counting them as edges reports
cycles that never occur; they are surfaced separately as ``deferred_imports``.

Gating is opt-in like everything else: rows are informational until an
``import_graph`` config block exists; with one, cycles violate (the Acyclic
Dependencies Principle) and stable-dependencies violations gate on count.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from antipasta.core.model.config import ImportGraphConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import FactRow, MetricResult, MetricType
from antipasta.core.model.violations import ProjectReport, Violation, check_metric_violation

#: Instability delta below which an edge toward a more-unstable module is
#: tolerated by the stable-dependencies check.
_SDP_TOLERANCE = 0.2


def derive_import_graph(derivation_input: DerivationInput) -> list[ProjectReport]:
    """Module coupling rows, cycle reports, and package rollups."""
    graph, deferred = _build_graphs(derivation_input)
    if not graph:
        return []
    config = derivation_input.config.import_graph
    abstractness_by_module = _abstractness_by_module(derivation_input)
    return [
        *_module_reports(graph, deferred, config, abstractness_by_module),
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


def build_module_graph(derivation_input: DerivationInput) -> dict[str, set[str]]:
    """Public entry: the resolved module dependency graph (layering reuses it)."""
    return _build_graph(derivation_input)


def build_import_graph_payload(derivation_input: DerivationInput) -> dict[str, Any]:
    """A JSON-serializable dependency graph for the HTML report's SOLID view.

    Returns ``{"modules": {name: {"sloc", "files"}}, "edges": [[src, tgt], ...]}``.
    Node ids are dotted module names matching the ``project`` block's coupling
    subjects, so the renderer can join edges to per-module instability etc.
    """
    graph = _build_graph(derivation_input)
    sloc: dict[str, float] = dict.fromkeys(graph, 0.0)
    files: dict[str, int] = dict.fromkeys(graph, 0)
    for report in derivation_input.file_reports:
        module = _module_name(report.file_path, derivation_input.root)
        if module is None or module not in graph:
            continue
        sloc[module] += _report_sloc(report)
        files[module] += 1
    modules = {name: {"sloc": sloc[name], "files": files[name]} for name in graph}
    edges = [[source, target] for source, targets in graph.items() for target in sorted(targets)]
    return {"modules": modules, "edges": edges}


def _report_sloc(report: Any) -> float:
    """A file report's source-lines-of-code (file-level row), or 0.0."""
    for metric in report.metrics:
        if metric.function_name is None and metric.metric_type == MetricType.SOURCE_LINES_OF_CODE:
            return float(metric.value)
    return 0.0


def _build_graph(derivation_input: DerivationInput) -> dict[str, set[str]]:
    """module → set of analyzed modules it imports at import time."""
    return _build_graphs(derivation_input)[0]


def _build_graphs(
    derivation_input: DerivationInput,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(import-time graph, deferred-import graph); self-edges dropped."""
    root = derivation_input.root
    module_of: dict[Path, str] = {}
    for file_path in derivation_input.facts_by_file:
        module = _module_name(file_path, root)
        if module is not None:
            module_of[file_path] = module

    known = set(module_of.values())
    resolver = _Resolver(known, root.name, root_is_package=(root / "__init__.py").exists())
    graph: dict[str, set[str]] = {module: set() for module in known}
    deferred: dict[str, set[str]] = {module: set() for module in known}
    for file_path, facts in derivation_input.facts_by_file.items():
        source = module_of.get(file_path)
        if source is None:
            continue
        for fact in facts:
            if fact.kind != "import":
                continue
            bucket = graph if fact.payload.get("scope", "module") == "module" else deferred
            for target in resolver.targets(fact.payload, source):
                if target != source and not _is_ancestor_edge(source, target):
                    bucket[source].add(target)
    return graph, deferred


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


class _Resolver:
    """Resolve raw import payloads against the analyzed module set."""

    def __init__(self, known: set[str], root_package: str, *, root_is_package: bool) -> None:
        self.known = known
        self.root_package = root_package
        self.root_is_package = root_is_package

    def targets(self, payload: dict[str, Any], source: str) -> set[str]:
        level = payload["level"]
        prefix = _import_prefix(payload["module"], level, source)
        return self._resolve_statement(prefix, payload["names"], absolute=level == 0)

    def _resolve_statement(self, prefix: str, names: list[str], *, absolute: bool) -> set[str]:
        """`from X import name`: name may be a submodule (X.name) or a symbol
        defined in X — the specific submodule wins; the package is only the
        fallback when the submodule doesn't exist."""
        if not names:
            resolved = self._match(prefix, absolute) if prefix else None
            return {resolved} if resolved else set()
        targets: set[str] = set()
        for name in names:
            candidate = f"{prefix}.{name}" if prefix else name
            resolved = self._match(candidate, absolute)
            if resolved is None and prefix:
                resolved = self._match(prefix, absolute)
            if resolved is not None:
                targets.add(resolved)
        return targets

    def _match(self, candidate: str, absolute: bool) -> str | None:
        parts = candidate.split(".")
        if absolute and self.root_is_package:
            # Inside a package root, an absolute import is internal only when
            # it names the package itself; ``import json`` never means
            # ``pkg/json.py``.
            if parts[0] != self.root_package:
                return None
            return _longest_known_prefix(parts[1:], self.known)
        if absolute and parts[0] == self.root_package:
            # src-layout root: ``pkg.core.x`` and ``core.x`` both address the
            # analyzed set. The stripped form wins only when the unstripped
            # one is unknown, so an analyzed module literally named like the
            # root still resolves.
            direct = _longest_known_prefix(parts, self.known)
            return direct if direct is not None else _longest_known_prefix(parts[1:], self.known)
        return _longest_known_prefix(parts, self.known)


def _longest_known_prefix(parts: list[str], known: set[str]) -> str | None:
    for end in range(len(parts), 0, -1):
        name = ".".join(parts[:end])
        if name in known:
            return name
    return None


def _import_prefix(module: str, level: int, source: str) -> str:
    """The dotted prefix an import statement addresses (relative dots applied)."""
    if level == 0:
        return module
    base_parts = source.split(".")[:-level] if level <= source.count(".") + 1 else []
    return ".".join([*base_parts, module]) if module else ".".join(base_parts)


# ── module metrics ──────────────────────────────────────────────────────────


def _module_reports(
    graph: dict[str, set[str]],
    deferred: dict[str, set[str]],
    config: ImportGraphConfig | None,
    abstractness_by_module: dict[str, float | None],
) -> list[ProjectReport]:
    afferent = _afferent_counts(graph)
    instability = _instability_map(graph, afferent)
    reports = []
    for module in sorted(graph):
        rows = _coupling_rows(module, graph, afferent, instability)
        sdp_row = rows[-1]
        rows.extend(_main_sequence_rows(module, graph, instability, abstractness_by_module))
        rows.append(_deferred_row(module, deferred[module]))
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


def _instability_map(graph: dict[str, set[str]], afferent: dict[str, int]) -> dict[str, float]:
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
    less_stable = sorted(
        target
        for target in graph[module]
        if instability[target] - instability[module] > _SDP_TOLERANCE
    )
    sdp_details: dict[str, Any] = {"tolerance": _SDP_TOLERANCE}
    if less_stable:
        sdp_details["targets"] = less_stable
    values = [
        (MetricType.EFFERENT_COUPLING, float(len(graph[module])), None),
        (MetricType.AFFERENT_COUPLING, float(afferent[module]), None),
        (MetricType.INSTABILITY, round(instability[module], 4), None),
        (MetricType.STABLE_DEPENDENCIES_VIOLATIONS, float(len(less_stable)), sdp_details),
    ]
    return [
        MetricResult(file_path=subject_path, metric_type=metric_type, value=value, details=details)
        for metric_type, value, details in values
    ]


def _deferred_row(module: str, targets: set[str]) -> MetricResult:
    """Analyzed modules imported only inside functions or ``TYPE_CHECKING``
    blocks: not dependency edges, but each one is usually a cycle someone
    broke by hand."""
    return MetricResult(
        file_path=Path(module.replace(".", "/") + ".py"),
        metric_type=MetricType.DEFERRED_IMPORTS,
        value=float(len(targets)),
        details={"targets": sorted(targets)[:10]} if targets else None,
    )


def _sdp_violations(sdp_row: MetricResult, config: ImportGraphConfig | None) -> list[Violation]:
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
        reports.append(ProjectReport(subject=f"package {package}", metrics=rows, violations=[]))
    return reports


def _package_of(module: str) -> str:
    return module.rsplit(".", 1)[0] if "." in module else "(top)"


# ── abstractness (merged from the former abstractness module: consumed
# only here, and the merge keeps the derive layer inside the fan-out band) ──


_ABSTRACT_BASE_MARKERS = ("ABC", "Protocol")
_ABSTRACT_METACLASS_MARKER = "ABCMeta"
_ABSTRACT_METHOD_MARKER = "abstractmethod"
_ABSTRACT_CLASS_DECORATORS = ("abstract",)
_ABSTRACT_STUB_KINDS = frozenset({"not_implemented", "ellipsis"})


def module_abstractness(facts: list[FactRow]) -> float | None:
    """Abstract-class ratio for one module; None when it has no classes."""
    class_payloads = [fact.payload for fact in facts if fact.kind == "class"]
    if not class_payloads:
        return None
    abstract = sum(1 for payload in class_payloads if _is_abstract(payload))
    return abstract / len(class_payloads)


def _is_abstract(payload: dict[str, Any]) -> bool:
    if any(_base_is_abstract(base) for base in payload["bases"]):
        return True
    if any(
        any(marker in decorator for marker in _ABSTRACT_CLASS_DECORATORS)
        for decorator in payload.get("decorators", [])
    ):
        return True
    if any(_ABSTRACT_METACLASS_MARKER in keyword for keyword in payload.get("keywords", [])):
        return True
    methods = payload["methods"]
    if any(
        _ABSTRACT_METHOD_MARKER in decorator
        for method in methods
        for decorator in method.get("decorators", [])
    ):
        return True
    # Python's other conventions: a method that only raises NotImplementedError
    # (or is ``...``) declares an abstract slot; a class whose every method is
    # a no-op stub is an interface (asyncio's BaseProtocol).
    stubs = [method.get("stub") for method in methods]
    if any(stub in _ABSTRACT_STUB_KINDS for stub in stubs):
        return True
    return bool(methods) and all(stub is not None for stub in stubs)


def _base_is_abstract(base: str) -> bool:
    head = base.split("[")[0]  # Protocol[T] -> Protocol
    last = head.split(".")[-1]  # typing.Protocol -> Protocol
    return last in _ABSTRACT_BASE_MARKERS


def distance_from_main_sequence(abstractness: float, instability: float) -> float:
    """|A + I − 1|: zero on the Main Sequence, 1.0 in the corners
    (pain: concrete + stable; uselessness: abstract + unstable)."""
    return abs(abstractness + instability - 1.0)


def dependency_inversion(
    target_modules: set[str], abstractness_by_module: dict[str, float | None]
) -> float | None:
    """Mean abstractness of imported targets; None with no outgoing edges.

    Targets without classes contribute 0.0 — importing a pure-function
    module is a concrete dependency by definition.
    """
    if not target_modules:
        return None
    total = sum(abstractness_by_module.get(target) or 0.0 for target in target_modules)
    return total / len(target_modules)
