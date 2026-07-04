"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_metrics_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the metrics cache at a per-test directory.

    Keeps tests from reading or writing the user's real ~/.cache/antipasta:
    real cache behavior is still exercised (the cache is on by default), but
    every test starts cold and leaves nothing behind.
    """
    monkeypatch.setenv("ANTIPASTA_CACHE_DIR", str(tmp_path / "metrics-cache"))
