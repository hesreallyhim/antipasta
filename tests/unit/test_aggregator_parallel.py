"""Tests for parallel metric collection in MetricAggregator."""

from __future__ import annotations

from pathlib import Path

import pytest

from antipasta.core.aggregator import (
    PARALLEL_THRESHOLD,
    MetricAggregator,
    _collect_file_metrics,
    _resolve_jobs,
)
from antipasta.core.cache import MetricsCache
from antipasta.core.config import AntipastaConfig
from antipasta.core.metrics import MetricType

SAMPLE_SOURCE = """\
def helper(value):
    if value > 3:
        return value * 2
    return value


def caller(items):
    return [helper(item) for item in items]
"""


class TestResolveJobs:
    """Tests for the worker-count resolution policy."""

    def test_small_task_count_stays_sequential(self) -> None:
        assert _resolve_jobs(None, PARALLEL_THRESHOLD - 1) == 1

    def test_large_task_count_goes_parallel(self) -> None:
        assert _resolve_jobs(None, PARALLEL_THRESHOLD * 10) > 1

    def test_explicit_request_wins_over_threshold(self) -> None:
        assert _resolve_jobs(4, 5) == 4

    def test_request_capped_to_task_count(self) -> None:
        assert _resolve_jobs(16, 3) == 3

    def test_env_variable_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTIPASTA_JOBS", "2")
        assert _resolve_jobs(None, 5) == 2

    def test_garbage_env_variable_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTIPASTA_JOBS", "lots")
        assert _resolve_jobs(None, 5) == 1

    def test_never_below_one(self) -> None:
        assert _resolve_jobs(0, 5) == 1


class TestWorkerTask:
    """Tests for the module-level worker function."""

    def test_collects_metrics_for_python_file(self, tmp_path: Path) -> None:
        source_file = tmp_path / "sample.py"
        source_file.write_text(SAMPLE_SOURCE)

        metrics, facts, errors = _collect_file_metrics((str(source_file), "python"))

        assert errors == []
        types = {m.metric_type for m in metrics}
        assert MetricType.CYCLOMATIC_COMPLEXITY in types
        assert MetricType.COGNITIVE_COMPLEXITY in types
        assert MetricType.MAINTAINABILITY_INDEX in types

    def test_returns_picklable_payload(self, tmp_path: Path) -> None:
        import pickle

        source_file = tmp_path / "sample.py"
        source_file.write_text(SAMPLE_SOURCE)

        payload = _collect_file_metrics((str(source_file), "python"))

        assert pickle.loads(pickle.dumps(payload)) is not None


class TestParallelEquivalence:
    """Parallel and sequential runs must produce identical reports."""

    def test_parallel_matches_sequential(self, tmp_path: Path) -> None:
        for index in range(6):
            (tmp_path / f"module_{index}.py").write_text(SAMPLE_SOURCE)
        files = sorted(tmp_path.glob("*.py"))
        # Cache disabled: the second run must actually exercise the pool,
        # not serve the first run's results back.
        aggregator = MetricAggregator(AntipastaConfig(), cache=MetricsCache(enabled=False))

        sequential = aggregator.analyze_files(files, jobs=1)
        parallel = aggregator.analyze_files(files, jobs=2)

        assert len(sequential) == len(parallel) == 6
        for seq_report, par_report in zip(sequential, parallel, strict=False):
            assert seq_report.file_path == par_report.file_path
            assert [m.to_dict() for m in seq_report.metrics] == [
                m.to_dict() for m in par_report.metrics
            ]
            assert len(seq_report.violations) == len(par_report.violations)
            assert seq_report.error == par_report.error
