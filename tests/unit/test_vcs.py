"""Tests for version-control mining (track B + suite-health D3)."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from antipasta.core.mining.vcs import (
    complexity_from_snapshot,
    history_reports,
    mine_history,
)
from antipasta.core.model.detector import is_test_path
from antipasta.core.model.metrics import MetricType


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin",
            "HOME": str(repo),
        },
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    for round_number in range(4):
        (tmp_path / "engine.py").write_text(f"x = {round_number}\n" * (round_number + 2))
        (tmp_path / "config.py").write_text(f"y = {round_number}\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_engine.py").write_text(f"assert {round_number} >= 0\n" * 3)
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", f"round {round_number}")
    return tmp_path


class TestMining:
    def test_churn_counts(self, repo: Path) -> None:
        history = mine_history(repo, window_days=30)

        assert history.commit_count == 4
        assert history.churn("engine.py") > 0
        assert history.commits_touching["engine.py"] == 4

    def test_change_coupling_pair(self, repo: Path) -> None:
        history = mine_history(repo, window_days=30)
        reports = history_reports(history)

        coupled = [r for r in reports if r.subject.startswith("co-change:")]
        assert coupled  # engine.py and config.py always change together
        top = coupled[0].metrics[0]
        assert top.value >= 3.0
        assert (top.details or {})["confidence"] == 1.0

    def test_suite_health_rows(self, repo: Path) -> None:
        history = mine_history(repo, window_days=30)
        reports = history_reports(history)

        suite = next(r for r in reports if r.subject == "suite-health")
        by_type = {m.metric_type: m for m in suite.metrics}
        assert by_type[MetricType.TEST_CHURN_RATIO].value > 0.0
        assert by_type[MetricType.CO_CHURN_MULTIPLICITY].value == 1.0

    def test_window_excludes_nothing_recent(self, repo: Path) -> None:
        history = mine_history(repo, window_days=1)

        assert history.commit_count == 4  # all commits are from "now"


class TestHotspotJoin:
    def test_join_against_snapshot(self, repo: Path) -> None:
        history = mine_history(repo, window_days=30)
        snapshot = {
            "root": "",
            "files": [
                {
                    "path": "engine.py",
                    "functions": [{"metrics": {"cyclomatic_complexity": 9.0}}],
                }
            ],
        }
        reports = history_reports(history, complexity_from_snapshot(snapshot))

        engine = next(r for r in reports if r.subject == "engine.py")
        hotspot = next(m for m in engine.metrics if m.metric_type is MetricType.HOTSPOT)
        assert hotspot.value == history.churn("engine.py") * 9.0

    def test_snapshot_root_prefixing(self) -> None:
        snapshot = {
            "root": "src/pkg",
            "files": [
                {"path": "mod.py", "functions": [{"metrics": {"cyclomatic_complexity": 4.0}}]}
            ],
        }
        assert complexity_from_snapshot(snapshot) == {"src/pkg/mod.py": 4.0}


class TestPathClassification:
    def test_test_paths(self) -> None:
        assert is_test_path("tests/unit/test_x.py")
        assert is_test_path("pkg/tests/helper.py")
        assert is_test_path("test_root.py")
        assert not is_test_path("src/pkg/engine.py")
