"""Tests for the duplication deriver (track A, pydry engine)."""

from __future__ import annotations

from pathlib import Path

import pytest

from antipasta.core.derive.duplication import derive_duplication, pydry_available
from antipasta.core.model.config import AntipastaConfig, DuplicationConfig
from antipasta.core.model.derivation import DerivationInput
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import FileReport, ProjectReport

TWIN_A = (
    "def alpha(x):\n"
    "    y = x + 1\n"
    "    z = y * 2\n"
    "    return z\n"
)
TWIN_B = (
    "def beta(q):\n"
    "    w = q + 1\n"
    "    v = w * 2\n"
    "    return v\n"
)
LONER = "def gamma(n):\n    return n - 1\n"


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, source in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)


def _file_report(root: Path, rel: str, sloc: float) -> FileReport:
    return FileReport(
        file_path=root / rel,
        language="python",
        metrics=[
            MetricResult(
                file_path=root / rel,
                metric_type=MetricType.SOURCE_LINES_OF_CODE,
                value=sloc,
            )
        ],
        violations=[],
    )


def _derive(root: Path, config: AntipastaConfig) -> list[ProjectReport]:
    reports = [_file_report(root, "a.py", 4.0), _file_report(root, "b.py", 6.0)]
    return derive_duplication(
        DerivationInput(
            file_reports=reports, facts_by_file={}, root=root, config=config
        )
    )


requires_pydry = pytest.mark.skipif(not pydry_available(), reason="pydry not installed")


class TestDuplicationDeriver:
    def test_disabled_without_config(self, tmp_path: Path) -> None:
        _write(tmp_path, {"a.py": TWIN_A, "b.py": TWIN_B})

        assert _derive(tmp_path, AntipastaConfig()) == []

    @requires_pydry
    def test_twins_form_a_clone_group(self, tmp_path: Path) -> None:
        _write(tmp_path, {"a.py": TWIN_A, "b.py": TWIN_B + "\n" + LONER})
        config = AntipastaConfig(duplication=DuplicationConfig())

        reports = _derive(tmp_path, config)

        groups = [r for r in reports if r.subject.startswith("clone-group:")]
        assert len(groups) == 1
        assert groups[0].metrics[0].value == 2.0
        members = (groups[0].metrics[0].details or {})["members"]
        assert any("alpha" in m for m in members)
        assert any("beta" in m for m in members)

    @requires_pydry
    def test_per_file_ratio_rows(self, tmp_path: Path) -> None:
        _write(tmp_path, {"a.py": TWIN_A, "b.py": TWIN_B})
        config = AntipastaConfig(duplication=DuplicationConfig())

        reports = _derive(tmp_path, config)

        a_report = next(r for r in reports if r.subject == "a.py")
        assert a_report.metrics[0].metric_type is MetricType.DUPLICATION_RATIO
        assert a_report.metrics[0].value == 1.0  # the whole file is one clone

    @requires_pydry
    def test_ratio_gate(self, tmp_path: Path) -> None:
        _write(tmp_path, {"a.py": TWIN_A, "b.py": TWIN_B})
        config = AntipastaConfig(duplication=DuplicationConfig(max_ratio=0.5))

        reports = _derive(tmp_path, config)

        a_report = next(r for r in reports if r.subject == "a.py")
        assert a_report.has_violations

    @requires_pydry
    def test_no_clones_no_reports(self, tmp_path: Path) -> None:
        _write(tmp_path, {"a.py": TWIN_A, "b.py": LONER})
        config = AntipastaConfig(duplication=DuplicationConfig())

        assert _derive(tmp_path, config) == []

    def test_unavailable_engine_reports_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import antipasta.core.derive.duplication as duplication_module

        monkeypatch.setattr(duplication_module, "pydry_available", lambda: False)
        _write(tmp_path, {"a.py": TWIN_A})
        config = AntipastaConfig(duplication=DuplicationConfig())

        reports = derive_duplication(
            DerivationInput(file_reports=[], facts_by_file={}, root=tmp_path, config=config)
        )

        assert len(reports) == 1
        assert "unavailable" in (reports[0].metrics[0].details or {})
