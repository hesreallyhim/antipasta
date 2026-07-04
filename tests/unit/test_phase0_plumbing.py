"""Tests for Phase 0 plumbing: fact rows, project reports, derivation stage.

See docs/design/metrics-adoption-plan.md, Phase 0.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
import pytest

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.cache import MetricsCache
from antipasta.core.config import AntipastaConfig, ComparisonOperator
from antipasta.core.derivation import DerivationInput
from antipasta.core.metrics import FactRow, MetricResult, MetricType
from antipasta.core.snapshot import SCHEMA_VERSION, build_snapshot
from antipasta.core.violations import ProjectReport, Violation

SAMPLE_SOURCE = """\
def helper(value):
    if value > 3:
        return value * 2
    return value
"""


class TestFactRow:
    """Fact rows are path-independent and JSON round-trippable."""

    def test_roundtrip(self) -> None:
        fact = FactRow(kind="imports", payload={"module": ".x", "level": 1})

        assert FactRow.from_dict(fact.to_dict()) == fact

    def test_cache_roundtrip_carries_facts(self, tmp_path: Path) -> None:
        cache = MetricsCache(cache_dir=tmp_path / "store")
        key = cache.key_for(b"content", "python")
        facts = [FactRow(kind="imports", payload={"module": "pkg.mod", "level": 0})]
        cache.put(key, [], facts, [])

        result = cache.get(key, tmp_path / "a.py")

        assert result is not None
        _, rehydrated, errors = result
        assert errors == []
        assert rehydrated == facts


class TestProjectReport:
    """Project reports carry directory-scoped findings."""

    def _violation(self) -> Violation:
        return Violation(
            file_path=Path("src/big_package"),
            metric_type=MetricType.LINES_OF_CODE,
            value=12.0,
            threshold=7.0,
            comparison=ComparisonOperator.LE,
        )

    def test_violation_accounting(self) -> None:
        report = ProjectReport(
            subject="src/big_package", metrics=[], violations=[self._violation()]
        )

        assert report.has_violations
        assert report.violation_count == 1
        assert report.violation_messages()[0].startswith("❌")

    def test_to_dict(self) -> None:
        report = ProjectReport(subject=".", metrics=[], violations=[])

        assert report.to_dict() == {"subject": ".", "metrics": [], "violations": []}


class TestDerivationStage:
    """The aggregator runs registered derivers over collected facts."""

    def test_deriver_receives_input_and_reports_flow_through(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text(SAMPLE_SOURCE)
        seen: list[DerivationInput] = []

        def tree_cop(derivation_input: DerivationInput) -> list[ProjectReport]:
            seen.append(derivation_input)
            violation = Violation(
                file_path=Path("."),
                metric_type=MetricType.LINES_OF_CODE,
                value=99.0,
                threshold=1.0,
                comparison=ComparisonOperator.LE,
            )
            return [ProjectReport(subject=".", metrics=[], violations=[violation])]

        aggregator = MetricAggregator(
            AntipastaConfig(),
            cache=MetricsCache(enabled=False),
            derivers=[tree_cop],
        )
        result = aggregator.analyze([tmp_path / "module.py"], root=tmp_path)

        assert len(result.file_reports) == 1
        assert len(result.project_reports) == 1
        assert result.has_project_violations
        assert seen[0].root == tmp_path.resolve()
        assert seen[0].config is aggregator.config
        assert len(seen[0].file_reports) == 1

    def test_explicit_empty_derivers_means_no_project_reports(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text(SAMPLE_SOURCE)
        aggregator = MetricAggregator(
            AntipastaConfig(), cache=MetricsCache(enabled=False), derivers=[]
        )

        result = aggregator.analyze([tmp_path / "module.py"])

        assert result.project_reports == []
        assert not result.has_project_violations

    def test_default_derivers_emit_tree_shape_rows(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text(SAMPLE_SOURCE)
        aggregator = MetricAggregator(AntipastaConfig(), cache=MetricsCache(enabled=False))

        result = aggregator.analyze([tmp_path / "module.py"], root=tmp_path)

        subjects = [r.subject for r in result.project_reports]
        assert "." in subjects  # tree-shape root row from the default derivers
        assert not result.has_project_violations  # informational without config

    def test_analyze_files_still_returns_file_reports(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text(SAMPLE_SOURCE)
        aggregator = MetricAggregator(AntipastaConfig(), cache=MetricsCache(enabled=False))

        reports = aggregator.analyze_files([tmp_path / "module.py"])

        assert len(reports) == 1
        assert reports[0].file_path == tmp_path / "module.py"


class TestProfileConfig:
    """The strictness profile field validates and defaults."""

    def test_default_is_standard(self) -> None:
        assert AntipastaConfig().profile == "standard"

    def test_accepts_known_profiles(self) -> None:
        for name in ("extreme", "standard", "relaxed"):
            assert AntipastaConfig(profile=name).profile == name

    def test_rejects_unknown_profile(self) -> None:
        with pytest.raises(ValidationError):
            AntipastaConfig(profile="al_dente")  # type: ignore[arg-type]


class TestSnapshotV2:
    """Snapshots carry the project block under schema version 2."""

    def test_schema_version_bumped(self) -> None:
        assert SCHEMA_VERSION == 2

    def test_project_block_default_empty(self) -> None:
        snapshot = build_snapshot([], AntipastaConfig())

        assert snapshot["schema_version"] == 2
        assert snapshot["project"] == []

    def test_project_block_carries_reports(self) -> None:
        report = ProjectReport(subject="src/pkg", metrics=[], violations=[])
        snapshot = build_snapshot([], AntipastaConfig(), project_reports=[report])

        assert snapshot["project"] == [{"subject": "src/pkg", "metrics": [], "violations": []}]

    def test_metric_rows_still_rehydrate(self) -> None:
        # Guard the FactRow addition against regressing MetricResult's dict form.
        row = MetricResult(
            file_path=Path("a.py"),
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=3.0,
        )
        assert MetricResult.from_dict(Path("b.py"), row.to_dict()).value == 3.0
