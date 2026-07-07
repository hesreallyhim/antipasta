"""Tests for Phase 2 class-scope metrics: cohesion, coupling, weighted
methods, inheritance depth, children counts."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.derive.class_registry import derive_class_registry
from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import FileMetrics, MetricType
from antipasta.runners.python.house_style import HouseStyleRunner
from antipasta.runners.python.radon import RadonRunner

COHESIVE_CLASS = """\
class Account:
    def __init__(self):
        self.balance = 0
        self.log = []
    def deposit(self, amount):
        self.balance = self.balance + amount
        self.log.append(amount)
    def summary(self):
        return self.balance, self.log
"""

GOD_CLASS = """\
class Kitchen:
    def chop(self):
        self.knife = "sharp"
    def slice(self):
        return self.knife
    def invoice(self):
        self.ledger = []
    def bill(self):
        return self.ledger
    def tweet(self):
        return post(self.handle)
"""


def _analyze(source: str) -> FileMetrics:
    return HouseStyleRunner().analyze(Path("sample.py"), content=source)


def _value(result: FileMetrics, metric_type: MetricType, name: str) -> float:
    for metric in result.metrics:
        if metric.metric_type == metric_type and metric.function_name == name:
            return metric.value
    raise AssertionError(f"no {metric_type} row for {name}")


class TestLackOfCohesion:
    def test_cohesive_class_is_one_component(self) -> None:
        result = _analyze(COHESIVE_CLASS)
        assert _value(result, MetricType.LACK_OF_COHESION, "Account") == 1.0

    def test_god_class_splits_into_components(self) -> None:
        result = _analyze(GOD_CLASS)
        # knife-world, ledger-world, handle-world: three responsibilities.
        assert _value(result, MetricType.LACK_OF_COHESION, "Kitchen") == 3.0

    def test_local_call_connects_methods(self) -> None:
        source = (
            "class A:\n"
            "    def outer(self):\n"
            "        return self.inner()\n"
            "    def inner(self):\n"
            "        return 1\n"
        )
        result = _analyze(source)
        assert _value(result, MetricType.LACK_OF_COHESION, "A") == 1.0

    def test_dunders_other_than_init_excluded(self) -> None:
        source = (
            "class A:\n"
            "    def __repr__(self):\n"
            "        return 'A'\n"
            "    def work(self):\n"
            "        return self.x\n"
        )
        result = _analyze(source)
        assert _value(result, MetricType.LACK_OF_COHESION, "A") == 1.0


class TestCouplingBetweenObjects:
    def test_counts_distinct_imported_references(self) -> None:
        source = (
            "from pkg import Alpha, Beta\n"
            "import gamma\n"
            "class Uses:\n"
            "    def go(self):\n"
            "        return Alpha(), Beta(), gamma.run()\n"
        )
        result = _analyze(source)
        row_value = _value(result, MetricType.COUPLING_BETWEEN_OBJECTS, "Uses")
        assert row_value == 3.0

    def test_unreferenced_imports_do_not_count(self) -> None:
        source = "from pkg import Alpha\nclass Quiet:\n    def go(self):\n        return 1\n"
        result = _analyze(source)
        assert _value(result, MetricType.COUPLING_BETWEEN_OBJECTS, "Quiet") == 0.0


class TestWeightedMethodsPerClass:
    def test_sums_member_complexity(self) -> None:
        source = (
            "class Busy:\n"
            "    def simple(self):\n"
            "        return 1\n"
            "    def branchy(self, n):\n"
            "        if n > 0:\n"
            "            return n\n"
            "        return -n\n"
        )
        result = RadonRunner().analyze(Path("sample.py"), content=source)
        rows = [m for m in result.metrics if m.metric_type == MetricType.WEIGHTED_METHODS_PER_CLASS]
        assert len(rows) == 1
        assert rows[0].function_name == "Busy"
        assert rows[0].value == 3.0  # 1 + 2
        assert rows[0].details == {"methods": 2}

    def test_average_row_unaffected_by_weighted_rows(self) -> None:
        source = "class A:\n    def m(self):\n        return 1\n"
        result = RadonRunner().analyze(Path("sample.py"), content=source)
        average = next(
            m
            for m in result.metrics
            if m.metric_type == MetricType.CYCLOMATIC_COMPLEXITY
            and (m.details or {}).get("type") == "average"
        )
        assert average.value == 1.0
        assert (average.details or {})["function_count"] == 1


class TestClassRegistry:
    def _derive(self, root: Path, sources: dict[str, str]) -> dict[str, dict[str, float]]:
        runner = HouseStyleRunner()
        facts_by_file = {}
        for rel, source in sources.items():
            path = root / rel
            facts_by_file[path] = runner.analyze(path, content=source).facts
        derivation_input = DerivationInput(
            file_reports=[], facts_by_file=facts_by_file, root=root, config=AntipastaConfig()
        )
        reports = derive_class_registry(derivation_input)
        return {r.subject: {m.metric_type.value: m.value for m in r.metrics} for r in reports}

    def test_same_module_chain(self, tmp_path: Path) -> None:
        by_class = self._derive(
            tmp_path, {"zoo.py": "class Animal:\n    pass\nclass Dog(Animal):\n    pass\n"}
        )
        assert by_class["zoo::Animal"]["depth_of_inheritance_tree"] == 1.0
        assert by_class["zoo::Dog"]["depth_of_inheritance_tree"] == 2.0
        assert by_class["zoo::Animal"]["number_of_children"] == 1.0
        assert by_class["zoo::Dog"]["number_of_children"] == 0.0

    def test_cross_module_resolution(self, tmp_path: Path) -> None:
        by_class = self._derive(
            tmp_path,
            {
                "base.py": "class Root:\n    pass\n",
                "leaf.py": "from base import Root\nclass Child(Root):\n    pass\n",
            },
        )
        assert by_class["leaf::Child"]["depth_of_inheritance_tree"] == 2.0
        assert by_class["base::Root"]["number_of_children"] == 1.0

    def test_external_base_is_shallow_and_flagged(self, tmp_path: Path) -> None:
        runner = HouseStyleRunner()
        path = tmp_path / "ext.py"
        facts = runner.analyze(
            path, content="from django import Model\nclass Thing(Model):\n    pass\n"
        ).facts
        derivation_input = DerivationInput(
            file_reports=[],
            facts_by_file={path: facts},
            root=tmp_path,
            config=AntipastaConfig(),
        )
        reports = derive_class_registry(derivation_input)
        depth_row = reports[0].metrics[0]
        assert depth_row.value == 2.0
        assert (depth_row.details or {})["approximate"] is True

    def test_inheritance_cycle_is_survivable(self, tmp_path: Path) -> None:
        by_class = self._derive(
            tmp_path, {"weird.py": "class A(B):\n    pass\nclass B(A):\n    pass\n"}
        )
        assert set(by_class) == {"weird::A", "weird::B"}  # no crash, rows emitted
