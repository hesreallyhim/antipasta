"""Tests for the import-graph deriver (adoption plan, Phase 3)."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.config import AntipastaConfig, ImportGraphConfig
from antipasta.core.derivation import DerivationInput
from antipasta.core.import_graph import derive_import_graph
from antipasta.core.violations import ProjectReport
from antipasta.runners.python.house_style import HouseStyleRunner


def _derive(
    root: Path, sources: dict[str, str], config: AntipastaConfig | None = None
) -> list[ProjectReport]:
    runner = HouseStyleRunner()
    facts_by_file = {}
    for rel, source in sources.items():
        path = root / rel
        facts_by_file[path] = runner.analyze(path, content=source).facts
    return derive_import_graph(
        DerivationInput(
            file_reports=[],
            facts_by_file=facts_by_file,
            root=root,
            config=config or AntipastaConfig(),
        )
    )


def _module_rows(reports: list[ProjectReport], subject: str) -> dict[str, float]:
    report = next(r for r in reports if r.subject == subject)
    return {m.metric_type.value: m.value for m in report.metrics}


CHAIN = {
    "cli.py": "import core\n\ndef main():\n    return core.run()\n",
    "core.py": "from util import helper\n\ndef run():\n    return helper()\n",
    "util.py": "def helper():\n    return 1\n",
}


class TestCouplingMetrics:
    def test_efferent_afferent_instability(self, tmp_path: Path) -> None:
        reports = _derive(tmp_path, CHAIN)

        cli = _module_rows(reports, "cli")
        core = _module_rows(reports, "core")
        util = _module_rows(reports, "util")
        assert (cli["efferent_coupling"], cli["afferent_coupling"]) == (1.0, 0.0)
        assert (core["efferent_coupling"], core["afferent_coupling"]) == (1.0, 1.0)
        assert (util["efferent_coupling"], util["afferent_coupling"]) == (0.0, 1.0)
        assert cli["instability"] == 1.0  # depends, nothing depends on it
        assert util["instability"] == 0.0  # depended upon, depends on nothing
        assert core["instability"] == 0.5

    def test_stable_dependencies_count(self, tmp_path: Path) -> None:
        # util (stable, I=0) imports cli (unstable, I=1): the wrong direction.
        sources = {
            "cli.py": "def main():\n    return 1\n",
            "util.py": "import cli\n\ndef helper():\n    return cli.main()\n",
        }
        reports = _derive(tmp_path, sources)

        util = _module_rows(reports, "util")
        assert util["stable_dependencies_violations"] == 0.0  # util IS the unstable one here

    def test_relative_import_resolution(self, tmp_path: Path) -> None:
        sources = {
            "pkg/__init__.py": "",
            "pkg/alpha.py": "from . import beta\n\ndef go():\n    return beta.run()\n",
            "pkg/beta.py": "def run():\n    return 1\n",
        }
        reports = _derive(tmp_path, sources)

        alpha = _module_rows(reports, "pkg.alpha")
        assert alpha["efferent_coupling"] == 1.0
        beta = _module_rows(reports, "pkg.beta")
        assert beta["afferent_coupling"] == 1.0

    def test_prefix_stripping_for_src_layout(self, tmp_path: Path) -> None:
        # Analyzed root is the package itself, so imports carry a leading
        # package name the module table doesn't have.
        sources = {
            "core/engine.py": "from antipasta.core import model\n\ndef go():\n    return model.M\n",
            "core/model.py": "M = 1\n",
        }
        reports = _derive(tmp_path, sources)

        engine = _module_rows(reports, "core.engine")
        assert engine["efferent_coupling"] == 1.0


class TestCycles:
    CYCLE = {
        "alpha.py": "import beta\n\ndef a():\n    return beta.b\n",
        "beta.py": "import alpha\n\ndef b():\n    return alpha.a\n",
        "loner.py": "def c():\n    return 1\n",
    }

    def test_cycle_reported_informationally(self, tmp_path: Path) -> None:
        reports = _derive(tmp_path, self.CYCLE)

        cycles = [r for r in reports if r.subject.startswith("cycle:")]
        assert len(cycles) == 1
        assert cycles[0].subject == "cycle: alpha <-> beta"
        assert cycles[0].metrics[0].value == 2.0
        assert cycles[0].violations == []  # no config -> observation only

    def test_cycle_violates_with_config(self, tmp_path: Path) -> None:
        config = AntipastaConfig(import_graph=ImportGraphConfig())
        reports = _derive(tmp_path, self.CYCLE, config)

        cycle = next(r for r in reports if r.subject.startswith("cycle:"))
        assert cycle.has_violations

    def test_acyclic_graph_reports_no_cycles(self, tmp_path: Path) -> None:
        reports = _derive(tmp_path, CHAIN)

        assert not [r for r in reports if r.subject.startswith("cycle:")]


class TestPackageRollup:
    def test_package_coupling(self, tmp_path: Path) -> None:
        sources = {
            "app/cli.py": "from lib import util\n\ndef main():\n    return util.go()\n",
            "lib/util.py": "def go():\n    return 1\n",
        }
        reports = _derive(tmp_path, sources)

        app = _module_rows(reports, "package app")
        lib = _module_rows(reports, "package lib")
        assert app["efferent_coupling"] == 1.0
        assert lib["afferent_coupling"] == 1.0


class TestGraphHygiene:
    def test_self_imports_dropped_and_empty_ok(self, tmp_path: Path) -> None:
        sources = {"only.py": "import only\n\ndef go():\n    return 1\n"}
        reports = _derive(tmp_path, sources)

        only = _module_rows(reports, "only")
        assert only["efferent_coupling"] == 0.0

    def test_external_imports_ignored(self, tmp_path: Path) -> None:
        sources = {"user.py": "import json\nfrom django import Model\n\ndef go():\n    return 1\n"}
        reports = _derive(tmp_path, sources)

        user = _module_rows(reports, "user")
        assert user["efferent_coupling"] == 0.0
