"""Content-addressed metric cache.

Static metrics are pure functions of file content, which makes them ideal
cache citizens: an entry is keyed by a sha256 over (analyzer fingerprint,
language, file bytes) and stores path-independent metric rows. Warm runs skip
the parsers entirely — including the process pool, since only cache misses are
dispatched to workers.

Correctness properties:
- The fingerprint folds in the antipasta version, the Python major.minor, and
  the radon/complexipy/lizard versions, so upgrading any analyzer naturally
  misses the old entries (no manual invalidation step).
- Entries never store the file path; metric rows are rehydrated against the
  path being analyzed, so renames and repo clones still hit.
- Results carrying runner errors are never cached (an error may be transient —
  a missing analyzer, an unreadable file — and must be re-observed).
- The cache is best-effort: unreadable or corrupt entries are treated as
  misses, and failed writes are swallowed. Writes are atomic (temp file +
  rename), so concurrent antipasta runs can share a cache directory.

The store is unbounded (content-addressed entries are a few KB each); `clear`
exists for hygiene. Default location: $ANTIPASTA_CACHE_DIR, else
$XDG_CACHE_HOME/antipasta, else ~/.cache/antipasta. Set ANTIPASTA_NO_CACHE=1
to disable entirely.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys

from antipasta.__version__ import __version__
from antipasta.core.metrics import FactRow, MetricResult

# v2 (2026-07-04): entries carry a `facts` array (path-independent fact rows
# for the derivation stage). Bumping this constant shifts the fingerprint,
# so all v1 entries become natural misses — no migration code.
_ENTRY_VERSION = 2
_ANALYZER_PACKAGES = ("radon", "complexipy", "lizard")


@lru_cache(maxsize=1)
def _fingerprint() -> str:
    """The analyzer-environment fingerprint folded into every cache key."""
    parts = [
        f"entry=v{_ENTRY_VERSION}",
        f"antipasta={__version__}",
        f"python={sys.version_info.major}.{sys.version_info.minor}",
    ]
    for package in _ANALYZER_PACKAGES:
        try:
            parts.append(f"{package}={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            parts.append(f"{package}=absent")
    return ";".join(parts)


def _default_cache_dir() -> Path:
    env_dir = os.environ.get("ANTIPASTA_CACHE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "antipasta"


class MetricsCache:
    """Content-addressed store for per-file metric collection results."""

    def __init__(self, cache_dir: Path | None = None, enabled: bool = True) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Store location (default: see module docstring)
            enabled: Master switch; ANTIPASTA_NO_CACHE=1 also disables
        """
        self.cache_dir = cache_dir if cache_dir is not None else _default_cache_dir()
        no_cache_env = os.environ.get("ANTIPASTA_NO_CACHE", "").strip()
        self.enabled = enabled and no_cache_env not in ("1", "true", "yes")

    def key_for(self, content: bytes, language: str) -> str:
        """Cache key for one file's content in one language."""
        hasher = hashlib.sha256()
        hasher.update(_fingerprint().encode())
        hasher.update(b"\x00")
        hasher.update(language.encode())
        hasher.update(b"\x00")
        hasher.update(content)
        return hasher.hexdigest()

    def get(
        self, key: str, file_path: Path
    ) -> tuple[list[MetricResult], list[FactRow], list[str]] | None:
        """Look up a collection result, rehydrated against ``file_path``.

        Returns None on any miss condition: disabled, absent, corrupt, or an
        entry-version mismatch.
        """
        if not self.enabled:
            return None
        try:
            data = json.loads(self._entry_path(key).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict) or data.get("v") != _ENTRY_VERSION:
            return None
        try:
            metrics = [MetricResult.from_dict(file_path, item) for item in data["metrics"]]
            facts = [FactRow.from_dict(item) for item in data["facts"]]
            errors = [str(item) for item in data["errors"]]
        except (KeyError, TypeError, ValueError):
            return None
        return metrics, facts, errors

    def put(
        self,
        key: str,
        metrics: list[MetricResult],
        facts: list[FactRow],
        errors: list[str],
    ) -> None:
        """Store a collection result. Error-bearing results are not cached."""
        if not self.enabled or errors:
            return
        entry_path = self._entry_path(key)
        payload = json.dumps(
            {
                "v": _ENTRY_VERSION,
                "errors": errors,
                "metrics": [metric.to_dict() for metric in metrics],
                "facts": [fact.to_dict() for fact in facts],
            }
        )
        try:
            entry_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = entry_path.with_name(f"{entry_path.name}.tmp-{os.getpid()}")
            temp_path.write_text(payload, encoding="utf-8")
            os.replace(temp_path, entry_path)
        except OSError:
            # Best-effort store: a failed write is a future miss, nothing more.
            return

    def clear(self) -> None:
        """Remove the whole store (hygiene; entries are otherwise unbounded)."""
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def _entry_path(self, key: str) -> Path:
        # Two-character sharding keeps directory listings sane at scale.
        return self.cache_dir / key[:2] / f"{key}.json"
