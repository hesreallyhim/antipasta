"""Best-effort previous-run snapshots with separate comparison metadata.

The snapshot file remains a normal, portable JSON baseline. A small sidecar
records selection compatibility and the content digest; mismatched concurrent
writes therefore lose a comparison rather than comparing unrelated runs.
"""

from __future__ import annotations

from contextlib import suppress
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from antipasta.core.model.config_paths import snapshot_path
from antipasta.core.store.snapshot import SCHEMA_VERSION


def _enabled() -> bool:
    return os.environ.get("ANTIPASTA_NO_CACHE", "").strip() not in {"1", "true", "yes"}


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, payload: str) -> None:
    """Replace an entry only after all bytes have been written successfully."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, encoding="utf-8", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        temporary.replace(path)
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


class SnapshotCache:
    """Store the last complete analysis for one repository checkout."""

    def __init__(self, root: Path, selection: dict[str, Any]) -> None:
        self.path = snapshot_path(root)
        self.context_path = self.path.with_suffix(".context.json")
        self.selection = selection

    def load(self) -> dict[str, Any] | None:
        """Miss on deletion, damage, incompatible selection, or schema changes."""
        if not _enabled():
            return None
        try:
            payload = self.path.read_text(encoding="utf-8")
            context = json.loads(self.context_path.read_text(encoding="utf-8"))
            return self._decode(payload, context)
        except (OSError, ValueError, TypeError):
            return None

    def _decode(self, payload: str, context: Any) -> dict[str, Any] | None:
        """Require a matching digest before using comparison metadata."""
        if not isinstance(context, dict):
            return None
        if context.get("selection") != self.selection or context.get("sha256") != _digest(payload):
            return None
        snapshot = json.loads(payload)
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != SCHEMA_VERSION:
            return None
        return snapshot

    def save(self, snapshot: dict[str, Any]) -> None:
        """Cache I/O must never turn successful analysis into an error."""
        if not _enabled():
            return
        payload = json.dumps(snapshot, indent=2)
        context = json.dumps({"selection": self.selection, "sha256": _digest(payload)})
        with suppress(OSError):
            _atomic_write(self.path, payload)
            _atomic_write(self.context_path, context)
