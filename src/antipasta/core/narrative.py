"""Narrative Index deriver: altitude classification, budgets, step-down.

The owner's prose discipline, enforced per docs/design/narrative-index.md:
every function classifies as narrator (advances the story via named project
calls), computer (a leaf: raw computation, no project calls), MIXED (both in
one body — the violation), or trivial (under 3 statements). Narrators carry
a step budget (prose has paragraphs; 25 perfect steps is a run-on) and
computers carry statement/nesting budgets (leaves must be small).
Step-down ordering is the newspaper rule per module: callees defined below
their callers.

Whole-program by nature: the project symbol table (all defined callables and
classes) decides which calls are narrative steps, and ambient vocabulary —
names called from a large share of functions (logging-style cross-cutting
utilities) — is excluded so it neither makes narrators nor breaks computers.

Reports are per module, compact: counts with offender names in details, not
one row per function. Violations fire only when a ``narrative`` config block
exists; informational otherwise, per the dogfooding policy.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from antipasta.core.config import NarrativeConfig
from antipasta.core.derivation import DerivationInput
from antipasta.core.lexicon import full_vocabulary, harvest_anchors, score_identifier
from antipasta.core.metrics import MetricResult, MetricType
from antipasta.core.violations import ProjectReport, Violation, check_metric_violation

#: Functions under this many statements are too small to classify.
TRIVIAL_FLOOR = 3

#: A name called by at least this share of all functions (and at least
#: _AMBIENT_MIN_CALLERS of them) is ambient vocabulary, not a narrative step.
_AMBIENT_CALLER_SHARE = 0.2
_AMBIENT_MIN_CALLERS = 5

#: At most this many offender names ride in a row's details.
_DETAIL_NAME_CAP = 10


def derive_narrative(derivation_input: DerivationInput) -> list[ProjectReport]:
    """Per-module narrative reports over the callable facts."""
    callables_by_module = _callables_by_module(derivation_input)
    if not callables_by_module:
        return []
    symbols = _project_symbols(derivation_input)
    ambient = _ambient_names(callables_by_module)
    config = derivation_input.config.narrative
    tolerance = (config or NarrativeConfig()).effective_mixing_tolerance(
        derivation_input.config.profile
    )
    vocabulary = full_vocabulary(
        _anchor_vocabulary(callables_by_module, derivation_input),
        (config or NarrativeConfig()).allowlist,
    )
    return [
        _module_report(module, payloads, symbols, ambient, config, tolerance, vocabulary)
        for module, payloads in sorted(callables_by_module.items())
    ]


def _anchor_vocabulary(
    callables_by_module: dict[str, list[dict[str, Any]]],
    derivation_input: DerivationInput,
) -> frozenset[str]:
    class_names = [
        fact.payload["name"]
        for facts in derivation_input.facts_by_file.values()
        for fact in facts
        if fact.kind == "class"
    ]
    return harvest_anchors(list(callables_by_module), class_names)


# ── inputs ──────────────────────────────────────────────────────────────────


def _callables_by_module(
    derivation_input: DerivationInput,
) -> dict[str, list[dict[str, Any]]]:
    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for file_path, facts in derivation_input.facts_by_file.items():
        module = _module_name(file_path, derivation_input.root)
        if module is None:
            continue
        for fact in facts:
            if fact.kind == "callable":
                by_module[module].append(fact.payload)
    return dict(by_module)


def _module_name(file_path: Path, root: Path) -> str | None:
    try:
        relative = file_path.resolve().relative_to(root)
    except ValueError:
        return None
    parts = relative.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def _project_symbols(derivation_input: DerivationInput) -> frozenset[str]:
    """Every project-defined callable and class name (constructors are
    named steps too)."""
    symbols: set[str] = set()
    for facts in derivation_input.facts_by_file.values():
        for fact in facts:
            if fact.kind in ("callable", "class"):
                symbols.add(fact.payload["name"])
    return frozenset(symbols)


def _ambient_names(
    callables_by_module: dict[str, list[dict[str, Any]]],
) -> frozenset[str]:
    callers_of: dict[str, int] = defaultdict(int)
    total_functions = 0
    for payloads in callables_by_module.values():
        for payload in payloads:
            total_functions += 1
            for name in set(payload["call_names"]):
                callers_of[name] += 1
    threshold = max(_AMBIENT_MIN_CALLERS, int(total_functions * _AMBIENT_CALLER_SHARE))
    return frozenset(name for name, count in callers_of.items() if count >= threshold)


# ── classification ──────────────────────────────────────────────────────────


def classify(
    payload: dict[str, Any],
    symbols: frozenset[str],
    ambient: frozenset[str],
    mixing_tolerance: int = 0,
) -> str:
    """Trimodal altitude classification (see narrative-index.md).

    ``mixing_tolerance`` is the strictness dial: raw-computation weight a
    narrator may carry before it counts as MIXED (0 = extreme profile).
    """
    if payload["statements"] < TRIVIAL_FLOOR:
        return "trivial"
    narrative_calls = [
        name
        for name in payload["call_names"]
        if name in symbols and name not in ambient and name != payload["name"]
    ]
    computes = payload["computation_weight"] > mixing_tolerance
    if narrative_calls and computes:
        return "mixed"
    if narrative_calls:
        return "narrator"
    return "computer"


# ── per-module report ───────────────────────────────────────────────────────


def _module_report(
    module: str,
    payloads: list[dict[str, Any]],
    symbols: frozenset[str],
    ambient: frozenset[str],
    config: NarrativeConfig | None,
    mixing_tolerance: int,
    vocabulary: frozenset[str],
) -> ProjectReport:
    effective = config if config is not None else NarrativeConfig()
    mixed: list[str] = []
    over_narrators: list[str] = []
    over_computers: list[str] = []
    for payload in payloads:
        kind = classify(payload, symbols, ambient, mixing_tolerance)
        if kind == "mixed":
            mixed.append(payload["name"])
        elif kind == "narrator" and payload["statements"] > effective.narrator_step_budget:
            over_narrators.append(payload["name"])
        elif kind == "computer" and _computer_over_budget(payload, effective):
            over_computers.append(payload["name"])

    rows = [
        _count_row(module, MetricType.NARRATIVE_MIXED_FUNCTIONS, mixed),
        _count_row(module, MetricType.NARRATOR_BUDGET_EXCEEDED, over_narrators),
        _count_row(module, MetricType.COMPUTER_BUDGET_EXCEEDED, over_computers),
        MetricResult(
            file_path=_subject_path(module),
            metric_type=MetricType.STEP_DOWN_ORDERING,
            value=round(_step_down_ratio(payloads), 4),
        ),
        _clarity_row(module, payloads, vocabulary),
        _count_row(module, MetricType.NAMING_ANTIPATTERNS, _antipatterns(payloads)),
    ]
    violations = _narrative_violations(rows, config)
    return ProjectReport(subject=module, metrics=rows, violations=violations)


def _clarity_row(
    module: str, payloads: list[dict[str, Any]], vocabulary: frozenset[str]
) -> MetricResult:
    """Module mean name clarity, worst offenders in details."""
    scored = [
        (score_identifier(payload["name"], vocabulary), payload["name"])
        for payload in payloads
        if not _is_dunder(payload["name"])
    ]
    if not scored:
        return MetricResult(
            file_path=_subject_path(module),
            metric_type=MetricType.NAME_CLARITY,
            value=1.0,
        )
    mean = sum(score for score, _ in scored) / len(scored)
    worst = [name for score, name in sorted(scored)[:5] if score < 0.7]
    return MetricResult(
        file_path=_subject_path(module),
        metric_type=MetricType.NAME_CLARITY,
        value=round(mean, 4),
        details={"worst": worst} if worst else None,
    )


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


#: Predicate prefixes whose functions should annotate bool.
_PREDICATE_HEADS = ("is_", "has_", "should_", "can_")


def _antipatterns(payloads: list[dict[str, Any]]) -> list[str]:
    """Linguistic antipatterns: names whose grammar contradicts behavior.

    All approximate by nature (annotations may be absent); each rule fires
    only on positive evidence of contradiction.
    """
    offenders = []
    for payload in payloads:
        name = payload["name"]
        annotation = payload.get("return_annotation")
        predicate_lying = (
            name.startswith(_PREDICATE_HEADS)
            and annotation is not None
            and "bool" not in annotation
        )
        getter_returns_nothing = (
            name.startswith(("get_", "fetch_")) and not payload.get("returns_value")
        )
        two_jobs = "_and_" in name
        if predicate_lying or getter_returns_nothing or two_jobs:
            offenders.append(name)
    return offenders


def _computer_over_budget(payload: dict[str, Any], config: NarrativeConfig) -> bool:
    return bool(
        payload["statements"] > config.computer_statement_budget
        or payload["nesting"] > config.computer_nesting_budget
    )


def _step_down_ratio(payloads: list[dict[str, Any]]) -> float:
    """Fraction of intra-module calls whose callee is defined below the
    caller — the newspaper rule, as a number."""
    line_of = {payload["name"]: payload["lineno"] for payload in payloads}
    ordered = 0
    total = 0
    for payload in payloads:
        for callee in payload["call_names"]:
            callee_line = line_of.get(callee)
            if callee_line is None or callee == payload["name"]:
                continue
            total += 1
            if callee_line > payload["lineno"]:
                ordered += 1
    return ordered / total if total else 1.0


def _count_row(
    module: str, metric_type: MetricType, offenders: list[str]
) -> MetricResult:
    details = {"functions": offenders[:_DETAIL_NAME_CAP]} if offenders else None
    return MetricResult(
        file_path=_subject_path(module),
        metric_type=metric_type,
        value=float(len(offenders)),
        details=details,
    )


def _subject_path(module: str) -> Path:
    return Path(module.replace(".", "/") + ".py")


def _narrative_violations(
    rows: list[MetricResult], config: NarrativeConfig | None
) -> list[Violation]:
    if config is None:
        return []
    violations = []
    for row in rows:
        gate = _gate_for(row, config)
        if gate is None:
            continue
        violation = check_metric_violation(row, gate)
        if violation:
            violations.append(violation)
    return violations


_COUNT_GATED = frozenset(
    {
        MetricType.NARRATIVE_MIXED_FUNCTIONS,
        MetricType.NARRATOR_BUDGET_EXCEEDED,
        MetricType.COMPUTER_BUDGET_EXCEEDED,
        MetricType.NAMING_ANTIPATTERNS,
    }
)


def _gate_for(row: MetricResult, config: NarrativeConfig) -> Any:
    """Which gate applies to a row (None = advisory)."""
    if row.metric_type in _COUNT_GATED:
        return config.count_gate(row.metric_type)
    if row.metric_type is MetricType.NAME_CLARITY and config.name_clarity_floor is not None:
        return config.clarity_gate()
    return None
