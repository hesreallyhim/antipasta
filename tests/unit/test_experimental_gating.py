"""Experimental metrics are computed only when their feature is enabled."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.model.config import AntipastaConfig, ExperimentalConfig, NarrativeConfig
from antipasta.core.model.metrics import EXPERIMENTAL_METRICS, MetricType
from antipasta.core.store.cache import MetricsCache
from antipasta.engine import MetricAggregator

SOURCE = (
    "def publish(directory):\n"
    "    users = fetch_users(directory)\n"
    "    active = keep_active(users)\n"
    "    return render(active)\n\n"
    "def fetch_users(directory):\n    return list(directory)\n\n"
    "def keep_active(users):\n    return [u for u in users if u]\n\n"
    "def render(users):\n    return len(users)\n"
)


def _types(result: object) -> set[MetricType]:
    reports = result.file_reports  # type: ignore[attr-defined]
    return {metric.metric_type for report in reports for metric in report.metrics}


def _project_types(result: object) -> set[MetricType]:
    reports = result.project_reports  # type: ignore[attr-defined]
    return {metric.metric_type for report in reports for metric in report.metrics}


def _run(tmp_path: Path, config: AntipastaConfig) -> object:
    path = tmp_path / "m.py"
    path.write_text(SOURCE)
    aggregator = MetricAggregator(config, cache=MetricsCache(enabled=False))
    return aggregator.analyze([path], root=tmp_path)


class TestExperimentalGating:
    def test_default_run_has_no_experimental_rows(self, tmp_path: Path) -> None:
        result = _run(tmp_path, AntipastaConfig())

        narrative = EXPERIMENTAL_METRICS["narrative"]
        assert not (_types(result) & narrative)
        assert not (_project_types(result) & narrative)
        assert MetricType.FUNCTION_ARITY in _types(result)  # core rows unaffected

    def test_enabled_feature_emits_labeled_rows(self, tmp_path: Path) -> None:
        config = AntipastaConfig(experimental=ExperimentalConfig(narrative=NarrativeConfig()))
        result = _run(tmp_path, config)

        assert MetricType.EXPRESSION_FLATNESS in _types(result)
        assert MetricType.NARRATIVE_MIXED_FUNCTIONS in _project_types(result)
        labeled = [
            metric
            for report in result.file_reports  # type: ignore[attr-defined]
            for metric in report.metrics
            if metric.metric_type is MetricType.EXPRESSION_FLATNESS
        ]
        assert all((metric.details or {}).get("experimental") is True for metric in labeled)

    def test_enable_experimental_switches_a_feature_on(self) -> None:
        config = AntipastaConfig()
        assert not config.experimental_enabled("narrative")
        config.enable_experimental("narrative")
        assert config.experimental_enabled("narrative")
        assert isinstance(config.experimental.narrative, NarrativeConfig)  # type: ignore[union-attr]
