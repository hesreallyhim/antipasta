"""Tests for the content-addressed metrics cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.cache import MetricsCache
from antipasta.core.config import AntipastaConfig
from antipasta.core.metrics import MetricResult, MetricType

SAMPLE_SOURCE = """\
def helper(value):
    if value > 3:
        return value * 2
    return value
"""


def _sample_metrics(file_path: Path) -> list[MetricResult]:
    return [
        MetricResult(
            file_path=file_path,
            metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
            value=2.0,
            line_number=1,
            function_name="helper",
            details={"type": "function", "classname": None, "rank": "A"},
        ),
        MetricResult(
            file_path=file_path,
            metric_type=MetricType.MAINTAINABILITY_INDEX,
            value=87.5,
            details={"rank": "A"},
        ),
    ]


class TestMetricsCache:
    """Unit tests for MetricsCache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> MetricsCache:
        return MetricsCache(cache_dir=tmp_path / "store")

    def test_roundtrip_rehydrates_against_new_path(
        self, cache: MetricsCache, tmp_path: Path
    ) -> None:
        original = tmp_path / "a.py"
        key = cache.key_for(b"content", "python")
        cache.put(key, _sample_metrics(original), [], [])

        renamed = tmp_path / "b" / "renamed.py"
        result = cache.get(key, renamed)

        assert result is not None
        metrics, facts, errors = result
        assert errors == []
        assert facts == []
        assert [m.to_dict() for m in metrics] == [m.to_dict() for m in _sample_metrics(original)]
        assert all(m.file_path == renamed for m in metrics)

    def test_miss_on_absent_key(self, cache: MetricsCache, tmp_path: Path) -> None:
        assert cache.get(cache.key_for(b"never stored", "python"), tmp_path / "x.py") is None

    def test_content_changes_key(self, cache: MetricsCache) -> None:
        assert cache.key_for(b"one", "python") != cache.key_for(b"two", "python")

    def test_language_changes_key(self, cache: MetricsCache) -> None:
        assert cache.key_for(b"same", "python") != cache.key_for(b"same", "javascript")

    def test_corrupt_entry_is_a_miss(self, cache: MetricsCache, tmp_path: Path) -> None:
        key = cache.key_for(b"content", "python")
        cache.put(key, _sample_metrics(tmp_path / "a.py"), [], [])
        entry_path = cache._entry_path(key)
        entry_path.write_text("{not json")

        assert cache.get(key, tmp_path / "a.py") is None

    def test_error_results_are_not_cached(self, cache: MetricsCache, tmp_path: Path) -> None:
        key = cache.key_for(b"content", "python")
        cache.put(key, [], [], ["runner exploded"])

        assert cache.get(key, tmp_path / "a.py") is None

    def test_disabled_cache_never_stores(self, tmp_path: Path) -> None:
        cache = MetricsCache(cache_dir=tmp_path / "store", enabled=False)
        key = cache.key_for(b"content", "python")
        cache.put(key, _sample_metrics(tmp_path / "a.py"), [], [])

        assert cache.get(key, tmp_path / "a.py") is None
        assert not (tmp_path / "store").exists()

    def test_no_cache_env_disables(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTIPASTA_NO_CACHE", "1")
        cache = MetricsCache(cache_dir=tmp_path / "store")

        assert cache.enabled is False

    def test_clear_removes_store(self, cache: MetricsCache, tmp_path: Path) -> None:
        key = cache.key_for(b"content", "python")
        cache.put(key, _sample_metrics(tmp_path / "a.py"), [], [])
        assert cache.get(key, tmp_path / "a.py") is not None

        cache.clear()

        assert cache.get(key, tmp_path / "a.py") is None


class TestAggregatorCacheIntegration:
    """The aggregator serves warm runs from the cache without re-analysis."""

    def test_second_run_skips_collection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for index in range(3):
            (tmp_path / f"module_{index}.py").write_text(SAMPLE_SOURCE)
        files = sorted(tmp_path.glob("*.py"))
        aggregator = MetricAggregator(
            AntipastaConfig(), cache=MetricsCache(cache_dir=tmp_path / "store")
        )

        calls: list[tuple[str, str]] = []
        import antipasta.core.aggregator as aggregator_module

        real_collect = aggregator_module._collect_file_metrics

        def counting_collect(task: tuple[str, str]) -> object:
            calls.append(task)
            return real_collect(task)

        monkeypatch.setattr(aggregator_module, "_collect_file_metrics", counting_collect)

        cold = aggregator.analyze_files(files)
        cold_calls = len(calls)
        warm = aggregator.analyze_files(files)

        assert cold_calls == 3
        assert len(calls) == 3  # warm run added zero collection calls
        assert [r.file_path for r in cold] == [r.file_path for r in warm]
        for cold_report, warm_report in zip(cold, warm, strict=True):
            assert [m.to_dict() for m in cold_report.metrics] == [
                m.to_dict() for m in warm_report.metrics
            ]
            assert len(cold_report.violations) == len(warm_report.violations)

    def test_edited_file_misses_and_reanalyzes(
        self, tmp_path: Path
    ) -> None:
        source_file = tmp_path / "module.py"
        source_file.write_text(SAMPLE_SOURCE)
        aggregator = MetricAggregator(
            AntipastaConfig(), cache=MetricsCache(cache_dir=tmp_path / "store")
        )

        first = aggregator.analyze_files([source_file])
        source_file.write_text(SAMPLE_SOURCE + "\n\ndef extra():\n    return 1\n")
        second = aggregator.analyze_files([source_file])

        first_functions = {m.function_name for m in first[0].metrics if m.function_name}
        second_functions = {m.function_name for m in second[0].metrics if m.function_name}
        assert "extra" not in first_functions
        assert "extra" in second_functions

    def test_threshold_change_reuses_cache_but_rechecks(self, tmp_path: Path) -> None:
        source_file = tmp_path / "module.py"
        source_file.write_text(SAMPLE_SOURCE)
        store = tmp_path / "store"

        lenient = MetricAggregator(AntipastaConfig(), cache=MetricsCache(cache_dir=store))
        assert lenient.analyze_files([source_file])[0].violations == []

        strict_config = AntipastaConfig()
        strict_config.defaults.max_cyclomatic_complexity = 1
        strict = MetricAggregator(strict_config, cache=MetricsCache(cache_dir=store))
        violations = strict.analyze_files([source_file])[0].violations

        assert violations  # cached metrics, fresh verdicts
