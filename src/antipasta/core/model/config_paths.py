"""Locations for user configuration and disposable analysis snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import platform

from antipasta.core.store.cache import _default_cache_dir


@dataclass(frozen=True)
class ConfigPaths:
    """Resolved locations, including optional files that may not yet exist."""

    user: Path
    project: Path
    cache: Path
    snapshot: Path


def user_config_path() -> Path:
    """Follow native Windows roaming config or the XDG config convention."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base.expanduser() / "antipasta" / "config.yaml"


def analysis_root(root: Path | None = None) -> Path:
    """Normalize a file or directory target before locating configuration."""
    path = (root or Path.cwd()).expanduser().resolve()
    return path.parent if path.is_file() else path


def repository_root(root: Path) -> Path:
    """Keep different worktree checkouts separate, including Git's .git files."""
    path = analysis_root(root)
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return parent
    return path


def snapshot_path(root: Path) -> Path:
    """Give each canonical analysis root its own previous-run slot per checkout."""
    target = analysis_root(root)
    identity = os.fsencode(repository_root(target)) + b"\0" + os.fsencode(target)
    key = hashlib.sha256(identity).hexdigest()
    return _default_cache_dir() / "snapshots" / f"{key}.json"


def resolve_paths(root: Path | None = None, config_path: Path | None = None) -> ConfigPaths:
    """Select root config before cwd; explicit paths override the environment."""
    project = analysis_root(root) / ".antipasta.yaml"
    if not project.exists():
        project = Path.cwd() / ".antipasta.yaml"
    selected = config_path or os.environ.get("ANTIPASTA_CONFIG")
    if selected:
        project = Path(selected).expanduser().resolve()
    return ConfigPaths(
        user_config_path(), project, _default_cache_dir(), snapshot_path(analysis_root(root))
    )
