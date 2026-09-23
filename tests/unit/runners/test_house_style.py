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
    def test_arity_counts_required_positionals_excluding_self(
        self, runner: HouseStyleRunner
    ) -> None:
        source = "class A:\n    def go(self, a, b, c=1, *args, d, **kw):\n        return a\n"
        result = analyze(runner, source)
        row = next(m for m in result.metrics if m.metric_type == MetricType.FUNCTION_ARITY)
        assert row.value == 2.0
        assert row.details == {"defaulted": 1, "keyword_only": 1, "variadic": True}

    def test_keyword_only_api_is_not_a_long_parameter_list(self, runner: HouseStyleRunner) -> None:
        # pydantic's Field: one positional, thirty-odd keyword-only options.
        source = "def field(default, *, alias=None, title=None, gt=None, lt=None):\n    return 1\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.FUNCTION_ARITY, "field") == 1.0

    def test_flag_the_body_branches_on_counts(self, runner: HouseStyleRunner) -> None:
        source = "def go(a, strict=True):\n    if strict:\n        return a\n    return None\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 1.0

    def test_passed_through_flag_is_configuration(self, runner: HouseStyleRunner) -> None:
        source = "def go(a, strict=True):\n    return build(a, strict)\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 0.0

    def test_keyword_only_bool_is_exempt(self, runner: HouseStyleRunner) -> None:
        source = "def go(a, *, strict=True):\n    if strict:\n        return a\n    return None\n"
        result = analyze(runner, source)
        assert value_of(result, MetricType.BOOLEAN_FLAG_PARAMETERS, "go") == 0.0

    def test_bool_annotation_counts_when_branched_on(self, runner: HouseStyleRunner) -> None:
        source = "def go(a, strict: bool):\n    return a if strict else None\n"
        result = analyze(runner, source)
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

    def test_lowercase_read_only_bindings_are_constants(self, runner: HouseStyleRunner) -> None:
        # Compiled regexes, type aliases, and sentinels: assigned once, only read.
        source = (
            "import re\nr_hex = re.compile('x')\nColorTuple = tuple\n_missing = object()\n"
            "def go(s):\n    return r_hex.match(s), ColorTuple, _missing\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "go") == 0.0

    def test_name_written_by_a_function_is_state(self, runner: HouseStyleRunner) -> None:
        source = (
            "_cache = None\n"
            "def load():\n    global _cache\n    _cache = 1\n    return _cache\n"
            "def peek():\n    return _cache\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "load") == 1.0
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "peek") == 1.0

    def test_in_place_mutation_marks_state(self, runner: HouseStyleRunner) -> None:
        source = (
            "handlers = ()\nseen = frozenset()\n"
            "def register(h):\n    handlers.append(h)\n"
            "def check(x):\n    return x in seen\n"
        )
        result = analyze(runner, source)
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "register") == 1.0
        assert value_of(result, MetricType.GLOBAL_STATE_REACH, "check") == 0.0


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
        assert {"module": "", "names": ["sibling"], "level": 1, "scope": "module"} in imports
        assert {"module": "pkg.mod", "names": [], "level": 0, "scope": "module"} in imports

    def test_import_facts_record_deferred_scopes(self, runner: HouseStyleRunner) -> None:
        source = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    import typed\n"
            "try:\n    import optional\nexcept ImportError:\n    optional = None\n"
            "class C:\n    import in_class\n"
            "    def m(self):\n        import lazy\n"
        )
        result = analyze(runner, source)
        scopes = {
            f.payload["module"]: f.payload["scope"] for f in result.facts if f.kind == "import"
        }
        assert scopes == {
            "typing": "module",
            "typed": "type_checking",
            "optional": "module",
            "in_class": "module",
            "lazy": "function",
        }

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

    def test_class_facts_classify_stubs_and_collect_names(self, runner: HouseStyleRunner) -> None:
        source = (
            "from x import Helper\n"
            "class A:\n"
            "    def a(self):\n        'doc only'\n"
            "    def b(self):\n        pass\n"
            "    def c(self):\n        ...\n"
            "    def d(self):\n        raise NotImplementedError('later')\n"
            "    def e(self):\n        return Helper()\n"
            "    @classmethod\n"
            "    def f(cls):\n        return cls.registry\n"
        )
        result = analyze(runner, source)
        klass = next(f.payload for f in result.facts if f.kind == "class")
        stubs = {m["name"]: m["stub"] for m in klass["methods"]}
        assert stubs == {
            "a": "empty",
            "b": "pass",
            "c": "ellipsis",
            "d": "not_implemented",
            "e": None,
            "f": None,
        }
        assert "Helper" in klass["referenced_names"]
        f = next(m for m in klass["methods"] if m["name"] == "f")
        assert f["fields_read"] == ["registry"]

    def test_callable_facts_mark_methods(self, runner: HouseStyleRunner) -> None:
        source = "class A:\n    def m(self):\n        return 1\n\ndef f():\n    return 2\n"
        result = analyze(runner, source)
        callables = {f.payload["name"]: f.payload for f in result.facts if f.kind == "callable"}
        assert callables["m"]["is_method"] is True
        assert callables["m"]["class_name"] == "A"
        assert callables["f"]["is_method"] is False
