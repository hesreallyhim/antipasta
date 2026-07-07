"""Tests for Phase 4 Main-Sequence composites: abstractness, distance,
dependency inversion."""

from __future__ import annotations

from pathlib import Path

import pytest

from antipasta.core.derive.import_graph import (
    dependency_inversion,
    derive_import_graph,
    distance_from_main_sequence,
    module_abstractness,
)
from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import FactRow
from antipasta.core.model.violations import ProjectReport
from antipasta.runners.python.house_style import HouseStyleRunner


def _facts(source: str) -> list[FactRow]:
    return HouseStyleRunner().analyze(Path("m.py"), content=source).facts


class TestAbstractnessClassification:
    def test_abstract_base_class_counts(self) -> None:
        source = "from abc import ABC\nclass Port(ABC):\n    pass\nclass Impl:\n    pass\n"
        assert module_abstractness(_facts(source)) == 0.5

    def test_protocol_counts(self) -> None:
        source = (
            "from typing import Protocol\n"
            "class Reader(Protocol):\n    def read(self):\n        ...\n"
        )
        assert module_abstractness(_facts(source)) == 1.0

    def test_parametrized_protocol_counts(self) -> None:
        source = (
            "from typing import Protocol, TypeVar\nT = TypeVar('T')\n"
            "class Box(Protocol[T]):\n    def get(self) -> T:\n        ...\n"
        )
        assert module_abstractness(_facts(source)) == 1.0

    def test_abstractmethod_marks_class(self) -> None:
        source = (
            "from abc import abstractmethod\n"
            "class Half:\n"
            "    @abstractmethod\n"
            "    def must(self):\n"
            "        ...\n"
        )
        assert module_abstractness(_facts(source)) == 1.0

    def test_metaclass_keyword_counts(self) -> None:
        source = "from abc import ABCMeta\nclass Meta(metaclass=ABCMeta):\n    pass\n"
        assert module_abstractness(_facts(source)) == 1.0

    def test_concrete_class_is_zero(self) -> None:
        assert module_abstractness(_facts("class Plain:\n    pass\n")) == 0.0

    def test_classless_module_is_none(self) -> None:
        assert module_abstractness(_facts("def free():\n    return 1\n")) is None


class TestComposites:
    def test_distance_arithmetic(self) -> None:
        assert distance_from_main_sequence(0.0, 1.0) == 0.0  # on the sequence
        assert distance_from_main_sequence(1.0, 1.0) == 1.0  # useless corner
        assert distance_from_main_sequence(0.0, 0.0) == 1.0  # pain corner
        assert distance_from_main_sequence(0.5, 0.5) == 0.0

    def test_dependency_inversion_mean(self) -> None:
        abstractness = {"port": 1.0, "impl": 0.0, "funcs": None}
        assert dependency_inversion({"port", "impl"}, abstractness) == 0.5
        assert dependency_inversion({"funcs"}, abstractness) == 0.0  # classless = concrete
        assert dependency_inversion(set(), abstractness) is None


class TestDeriverIntegration:
    def _derive(self, root: Path, sources: dict[str, str]) -> list[ProjectReport]:
        runner = HouseStyleRunner()
        facts_by_file = {
            root / rel: runner.analyze(root / rel, content=src).facts
            for rel, src in sources.items()
        }
        return derive_import_graph(
            DerivationInput(
                file_reports=[],
                facts_by_file=facts_by_file,
                root=root,
                config=AntipastaConfig(),
            )
        )

    def test_main_sequence_rows_on_module_reports(self, tmp_path: Path) -> None:
        sources = {
            "port.py": "from abc import ABC\nclass Port(ABC):\n    pass\n",
            "impl.py": (
                "from port import Port\nclass Impl(Port):\n    def go(self):\n        return 1\n"
            ),
        }
        reports = self._derive(tmp_path, sources)

        port = next(r for r in reports if r.subject == "port")
        rows = {m.metric_type.value: m for m in port.metrics}
        assert rows["abstractness"].value == 1.0
        assert rows["abstractness"].details == {"approximate": True}
        # port: instability 0 (depended on), abstractness 1 -> on the sequence
        assert rows["distance_from_main_sequence"].value == 0.0

        impl = next(r for r in reports if r.subject == "impl")
        impl_rows = {m.metric_type.value: m.value for m in impl.metrics}
        assert impl_rows["dependency_inversion"] == 1.0  # imports only the port

    def test_classless_module_has_no_abstractness_row(self, tmp_path: Path) -> None:
        reports = self._derive(tmp_path, {"funcs.py": "def go():\n    return 1\n"})

        funcs = next(r for r in reports if r.subject == "funcs")
        types = {m.metric_type.value for m in funcs.metrics}
        assert "abstractness" not in types
        assert "distance_from_main_sequence" not in types

    def test_inversion_row_absent_without_edges(self, tmp_path: Path) -> None:
        reports = self._derive(tmp_path, {"loner.py": "class A:\n    pass\n"})

        loner = next(r for r in reports if r.subject == "loner")
        types = {m.metric_type.value for m in loner.metrics}
        assert "dependency_inversion" not in types


class TestFactDecorators:
    def test_method_decorators_captured(self) -> None:
        facts = _facts("class A:\n    @property\n    def x(self):\n        return 1\n")
        klass = next(f.payload for f in facts if f.kind == "class")
        assert klass["methods"][0]["decorators"] == ["property"]

    @pytest.mark.parametrize("keyword", ["metaclass=ABCMeta"])
    def test_class_keywords_captured(self, keyword: str) -> None:
        facts = _facts("from abc import ABCMeta\nclass A(metaclass=ABCMeta):\n    pass\n")
        klass = next(f.payload for f in facts if f.kind == "class")
        assert keyword in klass["keywords"]
