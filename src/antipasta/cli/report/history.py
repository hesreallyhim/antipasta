"""Previous-run comparison identity for the report command."""

from pathlib import Path

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_override import ConfigOverride
from antipasta.core.store.snapshot_cache import SnapshotCache


def snapshot_cache_for(
    root: Path,
    files: tuple[Path, ...],
    config: AntipastaConfig,
    override: ConfigOverride,
    directory: Path | None,
) -> SnapshotCache:
    """Compare like selections while allowing values, gates and files to change.

    Directory membership may evolve naturally between runs. Explicit file
    selections and filtering policies must match, and worktrees never share a
    last-run slot. Thresholds are intentionally absent: tables evaluate both
    snapshots with current thresholds.
    """
    selection = {
        "root": str(root.resolve()),
        "files": sorted(str(file.resolve()) for file in files),
        "collect_directory": directory is not None or not files,
        "ignore_patterns": config.ignore_patterns,
        "include_patterns": override.include_patterns,
        "use_gitignore": config.use_gitignore,
        "languages": {language.name: language.extensions for language in config.languages},
        "experimental_narrative": config.experimental_enabled("narrative"),
    }
    return SnapshotCache(root, selection)
