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


class TestClusterRules:
    def test_property_read_links_to_its_getter(self) -> None:
        # packaging.version.Version: ``major`` reads ``self.release``, a
        # property whose getter reads ``self._version``.
        source = (
            "class Version:\n"
            "    def __init__(self, v):\n        self._version = v\n"
            "    @property\n"
            "    def release(self):\n        return self._version.release\n"
            "    @property\n"
            "    def major(self):\n        return self.release[0]\n"
        )
        assert _value(_analyze(source), MetricType.LACK_OF_COHESION, "Version") == 1.0

    def test_shared_inherited_callee_links_methods(self) -> None:
        # email.message.MIMEPart reaches its state only through Message methods.
        source = (
            "class Part(Message):\n"
            "    def is_attachment(self):\n        return self.get('cd') == 'a'\n"
            "    def iter_parts(self):\n        return list(self.get_payload())\n"
            "    def body(self):\n        return self.get_payload()\n"
        )
        result = _analyze(source)
        assert _value(result, MetricType.LACK_OF_COHESION, "Part") == 1.0

    def test_stateless_helpers_are_not_clusters(self) -> None:
        source = (
            "class Loop:\n"
            "    def __init__(self):\n        self.readers = {}\n"
            "    def add_reader(self, fd):\n        self.readers[fd] = 1\n"
            "    def _sock_recv(self, fut, sock, n):\n        fut.set_result(sock.recv(n))\n"
            "    def _sock_send(self, fut, sock, data):\n        fut.set_result(sock.send(data))\n"
        )
        result = _analyze(source)
        row = next(m for m in result.metrics if m.metric_type == MetricType.LACK_OF_COHESION)
        assert row.value == 1.0
        assert (row.details or {})["stateless_methods"] == 2
        assert (row.details or {})["clusters"] == [["__init__", "add_reader"]]

    def test_init_only_cluster_is_setup_not_a_responsibility(self) -> None:
        source = (
            "class Decoder:\n"
            "    def __init__(self):\n        self.hook = None\n"
            "    def decode(self, s):\n        return self.scan(s)\n"
            "    def scan(self, s):\n        return self.raw(s)\n"
        )
        assert _value(_analyze(source), MetricType.LACK_OF_COHESION, "Decoder") == 1.0


class TestStubAwareCohesion:
    def test_interface_has_no_cohesion_row(self) -> None:
        source = (
            "class Port:\n"
            "    def read(self):\n        raise NotImplementedError\n"
            "    def write(self, data):\n        ...\n"
            "    def close(self):\n        pass\n"
        )
        result = _analyze(source)
        assert not [m for m in result.metrics if m.metric_type == MetricType.LACK_OF_COHESION]

    def test_stub_methods_do_not_split_a_concrete_class(self) -> None:
        source = (
            "class Base:\n"
            "    def __init__(self):\n        self.state = 0\n"
            "    def step(self):\n        self.state += 1\n"
            "    def on_done(self):\n        pass\n"
            "    def render(self):\n        raise NotImplementedError\n"
        )
        result = _analyze(source)
        assert _value(result, MetricType.LACK_OF_COHESION, "Base") == 1.0

    def test_cls_attribute_access_connects_classmethods(self) -> None:
        source = (
            "class Registry:\n"
            "    @classmethod\n"
            "    def register(cls, item):\n        cls.items.append(item)\n"
            "    @classmethod\n"
            "    def count(cls):\n        return len(cls.items)\n"
        )
        result = _analyze(source)
        assert _value(result, MetricType.LACK_OF_COHESION, "Registry") == 1.0


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


class TestCouplingBetweenObjects:
    def _rows(self, root: Path, sources: dict[str, str]) -> dict[str, tuple[float, list[str]]]:
        runner = HouseStyleRunner()
        facts_by_file = {}
        for rel, source in sources.items():
            path = root / rel
            facts_by_file[path] = runner.analyze(path, content=source).facts
        derivation_input = DerivationInput(
            file_reports=[], facts_by_file=facts_by_file, root=root, config=AntipastaConfig()
        )
        out = {}
        for report in derive_class_registry(derivation_input):
            row = next(
                m for m in report.metrics if m.metric_type == MetricType.COUPLING_BETWEEN_OBJECTS
            )
            out[report.subject] = (row.value, (row.details or {})["classes"])
        return out

    def test_counts_analyzed_classes_same_module_and_imported(self, tmp_path: Path) -> None:
        rows = self._rows(
            tmp_path,
            {
                "shapes.py": "class Point:\n    pass\nclass Size:\n    pass\n",
                "ui.py": (
                    "from shapes import Point\n"
                    "import json\n"
                    "class Theme:\n    pass\n"
                    "class Widget:\n"
                    "    def draw(self, theme: Theme):\n"
                    "        return Point(), json.dumps(theme)\n"
                ),
            },
        )
        assert rows["ui::Widget"] == (2.0, ["shapes::Point", "ui::Theme"])

    def test_external_names_and_self_reference_do_not_count(self, tmp_path: Path) -> None:
        rows = self._rows(
            tmp_path,
            {
                "solo.py": (
                    "from django import Model\n"
                    "class Node:\n"
                    "    def clone(self):\n"
                    "        return Node(), Model()\n"
                ),
            },
        )
        assert rows["solo::Node"] == (0.0, [])


class TestSingleResponsibilityIndex:
    def _sri(self, root: Path, source: str) -> dict[str, tuple[float, dict[str, object]]]:
        runner = HouseStyleRunner()
        path = root / "m.py"
        facts = runner.analyze(path, content=source).facts
        derivation_input = DerivationInput(
            file_reports=[], facts_by_file={path: facts}, root=root, config=AntipastaConfig()
        )
        out = {}
        for report in derive_class_registry(derivation_input):
            row = next(
                m for m in report.metrics if m.metric_type == MetricType.SINGLE_RESPONSIBILITY_INDEX
            )
            out[report.subject] = (row.value, row.details or {})
        return out

    def test_cohesive_class_scores_zero_regardless_of_size(self, tmp_path: Path) -> None:
        value, details = self._sri(tmp_path, COHESIVE_CLASS)["m::Account"]
        assert value == 0.0
        assert details["cohesion_components"] == 1

    def test_interface_scores_zero(self, tmp_path: Path) -> None:
        source = (
            "class Port:\n"
            "    def read(self):\n        raise NotImplementedError\n"
            "    def write(self):\n        raise NotImplementedError\n"
        )
        value, details = self._sri(tmp_path, source)["m::Port"]
        assert value == 0.0
        assert details["cohesion_components"] == 0

    def test_excess_components_scale_with_size(self, tmp_path: Path) -> None:
        value, details = self._sri(tmp_path, GOD_CLASS)["m::Kitchen"]
        # three components -> two in excess; five one-statement methods.
        assert details["cohesion_components"] == 3
        assert details["statements"] == 5
        assert value == round(2 * (1 + 0 / 30) * (1 + 5 / 60), 2)
