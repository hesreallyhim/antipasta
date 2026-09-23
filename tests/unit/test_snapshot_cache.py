"""Disposable snapshot storage and comparison identity."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from antipasta.core.model.config_paths import snapshot_path
from antipasta.core.store.snapshot_cache import SnapshotCache


def test_cache_round_trip_and_standalone_snapshot(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {"root": str(tmp_path), "files": []})
    snapshot = {"schema_version": 2, "files": [], "project": []}
    assert cache.load() is None
    cache.save(snapshot)
    assert cache.load() == snapshot
    assert json.loads(cache.path.read_text()) == snapshot
    cache.path.unlink()
    assert cache.load() is None


def test_selection_change_is_a_cache_miss(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {"files": ["one.py"]})
    cache.save({"schema_version": 2, "files": []})
    assert SnapshotCache(tmp_path, {"files": ["two.py"]}).load() is None


def test_corruption_and_stale_sidecar_are_misses(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {})
    cache.save({"schema_version": 2})
    cache.path.write_text('{"schema_version": 1}')
    assert cache.load() is None
    cache.path.write_text("{broken")
    assert cache.load() is None
    cache.context_path.write_text("[]")
    assert cache.load() is None


def test_schema_change_is_a_cache_miss(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {})
    cache.save({"schema_version": 999})
    assert cache.load() is None


def test_cache_can_be_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SnapshotCache(tmp_path, {})
    cache.save({"schema_version": 2})
    monkeypatch.setenv("ANTIPASTA_NO_CACHE", "1")
    assert cache.load() is None
    cache.save({"schema_version": 999})
    assert json.loads(cache.path.read_text())["schema_version"] == 2


def test_write_failure_is_nonfatal(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {})
    with patch(
        "antipasta.core.store.snapshot_cache._atomic_write", side_effect=OSError("read only")
    ):
        cache.save({"schema_version": 2})
    assert cache.load() is None


def test_failed_atomic_replace_cleans_up_temporary_file(tmp_path: Path) -> None:
    cache = SnapshotCache(tmp_path, {})
    with patch(
        "antipasta.core.store.snapshot_cache.Path.replace", side_effect=OSError("read only")
    ):
        cache.save({"schema_version": 2})
    assert list(cache.path.parent.iterdir()) == []


def test_nested_root_uses_checkout_key_but_worktrees_stay_separate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "src"
    nested.mkdir(parents=True)
    (repo / ".git").mkdir()
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: somewhere")
    assert snapshot_path(nested) == snapshot_path(repo)
    assert snapshot_path(worktree) != snapshot_path(repo)
