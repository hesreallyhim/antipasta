"""Probe: can a static scorer discriminate prose-style (pseudo-code-like) code?

Context (2026-07-03): written while designing the Narrative Index metric
(docs/design/narrative-index.md) — the owner wants to *measure* code that reads
top-to-bottom like pseudo-code: bodies that are sequences of calls to
semantically named helpers, one idea per line, named intermediates flowing
linearly. This probe implements crude versions of four proposed components
(narration ratio, expression flatness, pipeline linearity, name clarity) and
scores four versions of the same behavior:

  1. the owner's canonical example (translated to Python)
  2. a tightened variant (direct boolean return)
  3. an inlined twin — identical behavior, zero extraction
  4. a junk-named twin — prose *structure* but meaningless names

Expected: 1 and 2 score high, 3 fails on structure, 4 fails on names —
demonstrating the components are independent and the composite discriminates.

Run: venv/bin/python metrics/scripts/narrative_index_probe.py
Kept as a metric-development probe; this is the seed of the real analyzer.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
import textwrap

# Probe-scale stand-ins. The real metric ships an embedded English wordlist
# plus a project lexicon harvested from anchor names (package, modules,
# classes, config keys) so domain words like "antipasta" self-whitelist.
LEXICON = {
    "should",
    "accept",
    "new",
    "users",
    "user",
    "get",
    "by",
    "name",
    "desc",
    "filter",
    "filtered",
    "is",
    "too",
    "many",
    "fetch",
    "keep",
    "active",
    "exceeds",
    "capacity",
    "directory",
    "status",
    "last",
    "seen",
    "max",
    "count",
    "check",
    "not",
    "publish",
    "published",
    "daily",
    "report",
    "ranked",
    "rank",
    "summarize",
    "summary",
    "render",
    "format",
    "formatted",
    "validate",
    "validated",
    "save",
    "saved",
    "notify",
    "owner",
    "receipt",
    "record",
    "audit",
    "entry",
    "limit",
}
VERBS = {
    "get",
    "fetch",
    "build",
    "filter",
    "keep",
    "compute",
    "render",
    "parse",
    "should",
    "is",
    "has",
    "can",
    "exceeds",
    "make",
    "load",
    "save",
    "find",
    "count",
    "accept",
    "check",
    "publish",
    "rank",
    "summarize",
    "format",
    "validate",
    "notify",
    "record",
}
JUNK_WORDS = {
    "fn",
    "obj",
    "tmp",
    "mgr",
    "util",
    "impl",
    "stuff",
    "thing",
    "proc",
    "chk",
    "x",
    "y",
    "d",
}


@dataclass
class Score:
    narration: float
    flatness: float
    pipeline: float
    names: float

    @property
    def composite(self) -> float:
        return (self.narration + self.flatness + self.pipeline + self.names) / 4


def _split_words(identifier: str) -> list[str]:
    words: list[str] = []
    for chunk in identifier.split("_"):
        current = ""
        for ch in chunk:
            if ch.isupper() and current:
                words.append(current.lower())
                current = ch
            else:
                current += ch
        if current:
            words.append(current.lower())
    return words


def _is_simple(node: ast.expr) -> bool:
    return isinstance(node, (ast.Name, ast.Constant))


def _is_narrative_call(node: ast.expr) -> bool:
    """A call to a named helper whose arguments are plain names/constants."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and all(_is_simple(arg) for arg in node.args)
        and not node.keywords
    )


def _is_narrative_value(node: ast.expr | None) -> bool:
    """Name, constant, helper call, or negated helper call — a prose step."""
    if node is None or _is_simple(node):
        return True
    if _is_narrative_call(node):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_narrative_value(node.operand)
    return False


def _statements(fn: ast.FunctionDef) -> list[ast.stmt]:
    return [node for node in ast.walk(fn) if isinstance(node, ast.stmt) and node is not fn]


def _narration_ratio(fn: ast.FunctionDef) -> float:
    """Fraction of statements that advance the story via a named step."""
    statements = _statements(fn)
    narrative = 0
    for stmt in statements:
        if (isinstance(stmt, (ast.Assign, ast.Return)) and _is_narrative_value(stmt.value)) or (
            isinstance(stmt, ast.If) and _is_narrative_value(stmt.test)
        ):
            narrative += 1
    return narrative / len(statements) if statements else 1.0


_OPERATION_NODES = (
    ast.BinOp,
    ast.BoolOp,
    ast.Compare,
    ast.Subscript,
    ast.Lambda,
    ast.IfExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def _flatness(fn: ast.FunctionDef) -> float:
    """One idea per line: fraction of statements with at most one operation.

    Calls count as one idea; `not` is free (negation reads as prose);
    arithmetic, comparisons, boolean algebra, and subscripts are computation.
    """
    statements = _statements(fn)
    flat = 0
    for stmt in statements:
        operations = 0
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                operations += 1
            elif isinstance(node, _OPERATION_NODES):
                operations += 2  # raw computation is heavier than a named call
        if operations <= 1:
            flat += 1
    return flat / len(statements) if statements else 1.0


def _pipeline_linearity(fn: ast.FunctionDef) -> float:
    """Named intermediates that are assigned once and consumed once, in order."""
    assigned: dict[str, int] = {}
    used: dict[str, int] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned[node.id] = assigned.get(node.id, 0) + 1
            elif isinstance(node.ctx, ast.Load):
                used[node.id] = used.get(node.id, 0) + 1
    locals_ = set(assigned)
    if not locals_:
        return 1.0
    linear = sum(1 for name in locals_ if assigned[name] == 1 and used.get(name, 0) == 1)
    return linear / len(locals_)


def _name_clarity(fn: ast.FunctionDef) -> float:
    """Lexicon hit rate + verb-start for callables, junk-word penalties."""
    identifiers: list[tuple[str, bool]] = [(fn.name, True)]
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            identifiers.append((node.func.id, True))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            identifiers.append((node.id, False))
    total = 0.0
    for identifier, is_callable in identifiers:
        words = _split_words(identifier)
        if not words:
            continue
        hit_rate = sum(1 for word in words if word in LEXICON) / len(words)
        junk_penalty = sum(1 for word in words if word in JUNK_WORDS) / len(words)
        verb_bonus = 1.0 if (not is_callable or words[0] in VERBS) else 0.5
        total += max(0.0, hit_rate * verb_bonus - junk_penalty)
    return total / len(identifiers) if identifiers else 1.0


_BUILTIN_NAMES = frozenset(dir(builtins))


def _project_call_count(fn: ast.FunctionDef) -> int:
    """Calls to project-defined callables: named calls that aren't builtins.

    Self-recursion doesn't count (a recursive computation kernel is still a
    leaf). The real analyzer resolves against an actual project symbol table
    (plus class-scope resolution for self.method calls) and excludes an
    ambient-vocabulary list (logging, metrics) so cross-cutting calls don't
    flip a computer into a mixed violator.
    """
    count = 0
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id not in _BUILTIN_NAMES
            and node.func.id != fn.name
        ):
            count += 1
    return count


def _computation_count(fn: ast.FunctionDef) -> int:
    return sum(1 for node in ast.walk(fn) if isinstance(node, _OPERATION_NODES))


def classify_function(fn: ast.FunctionDef) -> str:
    """Trimodal classification: the violation is MIXING, not computing.

    narrator — advances the story via named project calls, no raw computation
    computer — a leaf: raw computation, zero project calls (judged by leaf
               budgets: size/nesting/cognitive, not by narration)
    MIXED    — both in one body: two abstraction altitudes, the actual smell
    trivial  — too small to classify (< 3 statements)
    """
    if len(_statements(fn)) < 3:
        return "trivial"
    project_calls = _project_call_count(fn)
    computation = _computation_count(fn)
    if project_calls and computation:
        return "MIXED"
    if project_calls:
        return "narrator"
    return "computer"


# Per-class budgets (extreme-profile values). Bounded fan-out at every
# altitude: a narrator over the step budget is a run-on paragraph — chunk it
# into named phases. Note neither cognitive complexity (0) nor cyclomatic (1)
# can see a 25-step run-on narrator; only a step budget catches it.
NARRATOR_STEP_BUDGET = 9
COMPUTER_STATEMENT_BUDGET = 8
COMPUTER_NESTING_BUDGET = 1

_NESTING_NODES = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith, ast.Try)


def _max_nesting(node: ast.stmt | ast.FunctionDef, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTING_NODES):
            deepest = max(deepest, _max_nesting(child, depth + 1))
        elif isinstance(child, ast.stmt):
            deepest = max(deepest, _max_nesting(child, depth))
    return deepest


def check_budget(fn: ast.FunctionDef, kind: str) -> str:
    steps = len(_statements(fn))
    if kind == "narrator":
        return "over" if steps > NARRATOR_STEP_BUDGET else "ok"
    if kind == "computer":
        too_big = steps > COMPUTER_STATEMENT_BUDGET
        too_deep = _max_nesting(fn) > COMPUTER_NESTING_BUDGET
        return "over" if (too_big or too_deep) else "ok"
    return "-"


def score_function(source: str) -> tuple[Score, str, int, str]:
    fn = ast.parse(textwrap.dedent(source)).body[0]
    assert isinstance(fn, ast.FunctionDef)
    score = Score(
        narration=_narration_ratio(fn),
        flatness=_flatness(fn),
        pipeline=_pipeline_linearity(fn),
        names=_name_clarity(fn),
    )
    kind = classify_function(fn)
    return score, kind, len(_statements(fn)), check_budget(fn, kind)


SAMPLES: dict[str, str] = {
    "owner's example (as written)": """
        def should_accept_new_users():
            users = get_users_by_name()
            filtered_users = filter_users(users)
            if is_too_many_users(filtered_users):
                return False
            else:
                return True
    """,
    "tightened variant": """
        def should_accept_new_users(directory):
            users = fetch_users(directory)
            active_users = keep_active_users(users)
            return not exceeds_capacity(active_users)
    """,
    "inlined twin (same behavior)": """
        def should_accept_new_users(directory):
            us = []
            for u in directory.get("users", []):
                if u.get("status") == "active" and u.get("last_seen", 0) > 1700000000:
                    us.append(u)
            return not (len(us) > MAX_USERS * 0.9)
    """,
    "junk-named twin (prose shape, bad names)": """
        def check2(d):
            x = do_stuff(d)
            y = proc(x)
            return not chk(y)
    """,
    "half-refactored (mixes altitudes)": """
        def should_accept_new_users(directory):
            users = fetch_users(directory)
            active = [u for u in users if u.get("status") == "active"]
            return not (len(active) > MAX_USERS * 0.9)
    """,
    "extracted leaf (pure computer)": """
        def exceeds_capacity(active_users):
            limit = MAX_USERS * 0.9
            count = len(active_users)
            return count > limit
    """,
    "run-on narrator (12 perfect steps)": """
        def publish_daily_report(directory):
            users = fetch_users(directory)
            active_users = keep_active_users(users)
            ranked_users = rank_users(active_users)
            user_summary = summarize_users(ranked_users)
            report = render_report(user_summary)
            formatted_report = format_report(report)
            validated_report = validate_report(formatted_report)
            saved_report = save_report(validated_report)
            published_report = publish_report(saved_report)
            receipt = notify_owner(published_report)
            audit_entry = record_audit(receipt)
            return audit_entry
    """,
}


def main() -> None:
    header = (
        f"{'sample':42} {'class':>9} {'steps':>6} {'budget':>7}"
        f" {'narr':>6} {'flat':>6} {'pipe':>6} {'names':>6} {'SCORE':>7}"
    )
    print(header)
    for label, source in SAMPLES.items():
        s, kind, steps, budget = score_function(source)
        print(
            f"{label:42} {kind:>9} {steps:6d} {budget:>7} {s.narration:6.2f}"
            f" {s.flatness:6.2f} {s.pipeline:6.2f} {s.names:6.2f} {s.composite:7.2f}"
        )


if __name__ == "__main__":
    main()
