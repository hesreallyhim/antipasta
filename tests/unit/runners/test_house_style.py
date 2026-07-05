"""Tests for the house-style runner (adoption plan, Phase 1).

Each metric gets a good/bad twin, probe style: the good twin obeys the house
rule, the bad twin violates exactly one thing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from antipasta.core.model.metrics import FileMetrics, MetricType
from antipasta.runners.python.house_style import HouseStyleRunner


@pytest.fixture
def runner() -> HouseStyleRunner:
    return HouseStyleRunner()


def analyze(runner: HouseStyleRunner, source: str) -> FileMetrics:
    return runner.analyze(Path("sample.py"), content=source)


def value_of(
    result: FileMetrics, metric_type: MetricType, function_name: str | None = None
) -> float:
    for metric in result.metrics:
        if metric.metric_type == metric_type and metric.function_name == function_name:
            return metric.value
    raise AssertionError(f"no {metric_type} row for {function_name}")


class TestChainDepth:
    def test_single_hop_is_fine(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(foo):\n    return foo.bar()\n")
        assert value_of(result, MetricType.MESSAGE_CHAIN_DEPTH, "go") == 1.0

    def test_reaching_through_counts_links(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(foo):\n    return foo.bar.baz.quix()\n")
        assert value_of(result, MetricType.MESSAGE_CHAIN_DEPTH, "go") == 3.0

    def test_self_first_hop_is_free(self, runner: HouseStyleRunner) -> None:
        source = "class A:\n    def go(self):\n        return self.helper()\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.MESSAGE_CHAIN_DEPTH, "go") == 0.0

    def test_chained_calls_count(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(q):\n    return q.filter(x).order_by(y)\n")
        assert value_of(result, MetricType.MESSAGE_CHAIN_DEPTH, "go") == 2.0


class TestArityAndFlags:
    def test_arity_excludes_self(self, runner: HouseStyleRunner) -> None:
        source = "class A:\n    def go(self, a, b, *args, **kw):\n        return a\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.FUNCTION_ARITY, "go") == 4.0

    def test_positional_bool_flag_counts(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(a, strict=True):\n    return a\n")
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 1.0

    def test_keyword_only_bool_is_exempt(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(a, *, strict=True):\n    return a\n")
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 0.0

    def test_bool_annotation_counts(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def go(a, strict: bool):\n    return a\n")
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 1.0


class TestExceptionDiscipline:
    def test_bare_except_counts(self, runner: HouseStyleRunner) -> None:
        source = "def go():\n    try:\n        work()\n    except:\n        recover()\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXCEPTION_DISCIPLINE, "go") == 1.0

    def test_broad_with_reraise_is_fine(self, runner: HouseStyleRunner) -> None:
        source = (
            "def go():\n    try:\n        work()\n"
            "    except Exception:\n        log()\n        raise\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXCEPTION_DISCIPLINE, "go") == 0.0

    def test_silent_pass_handler_counts(self, runner: HouseStyleRunner) -> None:
        source = "def go():\n    try:\n        work()\n    except ValueError:\n        pass\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXCEPTION_DISCIPLINE, "go") == 1.0

    def test_narrow_handled_is_fine(self, runner: HouseStyleRunner) -> None:
        source = "def go():\n    try:\n        work()\n    except ValueError:\n        recover()\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXCEPTION_DISCIPLINE, "go") == 0.0


class TestGlobalStateReach:
    def test_touching_module_state_counts(self, runner: HouseStyleRunner) -> None:
        source = "registry = {}\n\ndef go(key):\n    return registry[key]\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "go") == 1.0

    def test_constants_do_not_count(self, runner: HouseStyleRunner) -> None:
        source = "LIMIT = 10\n\ndef go(n):\n    return n < LIMIT\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "go") == 0.0


class TestNarrativeComponents:
    def test_prose_function_is_flat_and_linear(self, runner: HouseStyleRunner) -> None:
        source = (
            "def publish(directory):\n"
            "    users = fetch_users(directory)\n"
            "    active_users = keep_active(users)\n"
            "    return render(active_users)\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXPRESSION_FLATNESS, "publish") == 1.0
        assert value_of(result, MetricType.PIPELINE_LINEARITY, "publish") == 1.0
        assert value_of(result, MetricType.FUNCTION_STATEMENTS, "publish") == 3.0

    def test_inlined_function_scores_low(self, runner: HouseStyleRunner) -> None:
        source = (
            "def publish(directory):\n"
            "    total = 0\n"
            "    for user in directory:\n"
            "        if user.get('active') and user.get('age', 0) > 3:\n"
            "            total += user['weight'] * 2\n"
            "    return total\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.EXPRESSION_FLATNESS, "publish") <= 0.6
        assert value_of(result, MetricType.PIPELINE_LINEARITY, "publish") == 0.0

    def test_nested_function_not_double_counted(self, runner: HouseStyleRunner) -> None:
        source = "def outer():\n    def inner(a):\n        return a + a + a\n    return inner(1)\n"
        result = analyze(runner, source)
        # outer owns 2 statements (the def + return); inner's body is inner's.
        assert value_of(result, MetricType.FUNCTION_STATEMENTS, "outer") == 2.0
        assert value_of(result, MetricType.FUNCTION_STATEMENTS, "inner") == 1.0


class TestFileRows:
    def test_marker_and_comment_density(self, runner: HouseStyleRunner) -> None:
        source = "# TODO: fix this\n# plain note\ndef go():\n    return 1\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.MARKER_DENSITY) == pytest.approx(250.0)
        assert value_of(result, MetricType.COMMENT_DENSITY) == pytest.approx(50.0)

    def test_unparseable_source_yields_no_rows(self, runner: HouseStyleRunner) -> None:
        result = analyze(runner, "def broken(:\n")
        assert result.metrics == []
        assert result.facts == []


class TestFactExtraction:
    def test_import_facts_stay_raw(self, runner: HouseStyleRunner) -> None:
        source = "from . import sibling\nimport pkg.mod\n\ndef go():\n    return 1\n"
        result = analyze(runner, source)
        imports = [f.payload for f in result.facts if f.kind == "import"]
        assert {"module": "", "names": ["sibling"], "level": 1} in imports
        assert {"module": "pkg.mod", "names": [], "level": 0} in imports

    def test_class_facts_carry_method_field_access(self, runner: HouseStyleRunner) -> None:
        source = (
            "class Account:\n"
            "    def deposit(self, amount):\n"
            "        self.balance = self.balance + amount\n"
            "    def audit(self):\n"
            "        return self.log\n"
        )
        result = analyze(runner, source)
        klass = next(f.payload for f in result.facts if f.kind == "class")
        deposit = next(m for m in klass["methods"] if m["name"] == "deposit")
        assert deposit["fields_read"] == ["balance"]
        assert deposit["fields_written"] == ["balance"]
        audit = next(m for m in klass["methods"] if m["name"] == "audit")
        assert audit["fields_read"] == ["log"]

    def test_callable_facts_mark_methods(self, runner: HouseStyleRunner) -> None:
        source = "class A:\n    def m(self):\n        return 1\n\ndef f():\n    return 2\n"
        result = analyze(runner, source)
        callables = {f.payload["name"]: f.payload for f in result.facts if f.kind == "callable"}
        assert callables["m"]["is_method"] is True
        assert callables["m"]["class_name"] == "A"
        assert callables["f"]["is_method"] is False
