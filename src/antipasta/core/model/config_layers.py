"""Resolve partial configuration layers and retain their per-key provenance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from itertools import starmap
import os
from pathlib import Path
from typing import Any

import yaml

from antipasta.core.model.config import AntipastaConfig
from antipasta.core.model.config_defaults import bind_default_gates
from antipasta.core.model.config_merge import leaf_sources, merge_layer
from antipasta.core.model.config_paths import (
    ConfigPaths,
    analysis_root,
    resolve_paths as resolve_paths,
    user_config_path as user_config_path,
)
from antipasta.core.model.presets import expand_preset_config


@dataclass(frozen=True)
class ResolvedConfig:
    """Validated effective config plus inspectable diagnostics and locations."""

    config: AntipastaConfig
    sources: dict[str, str]
    warnings: list[str]
    paths: ConfigPaths


def read_layer(path: Path) -> dict[str, Any]:
    """Read YAML as a mapping, without materializing model defaults."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML configuration {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
        raise ValueError(f"Configuration must be a mapping with string keys: {path}")
    return data


def unknown_keys(data: dict[str, Any], label: str, *, allow_projects: bool = False) -> list[str]:
    """Keep obsolete config keys visible without breaking otherwise valid input."""
    allowed = set(AntipastaConfig.model_fields) | {"projects"}
    warnings = [f"{label}: unknown top-level key '{key}'" for key in data if key not in allowed]
    if not allow_projects:
        if "projects" in data:
            warnings.append(
                f"{label}: 'projects' is only supported in the user configuration; ignored"
            )
        return warnings
    for root, layer in project_layers(data):
        warnings.extend(unknown_keys(layer, f"{label}:projects[{root}]"))
    return warnings


def expanded_layer(data: dict[str, Any]) -> dict[str, Any]:
    """Expand presets within one layer and drop envelope/unknown keys."""
    values = {key: value for key, value in data.items() if key in AntipastaConfig.model_fields}
    return expand_preset_config(values)


def validate_partial(data: dict[str, Any], base: dict[str, Any] | None = None) -> None:
    """Validate against inherited values before a higher layer can hide bad input."""
    config_from_layer(data, base)


def project_layers(data: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    """Validate the user-file projects envelope, including inactive entries."""
    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        raise ValueError("projects must be a mapping keyed by absolute repository path")
    entries = list(starmap(project_entry, projects.items()))
    if entries:
        validate_projects(entries, config_from_layer(data))
    return entries


def project_entry(key: Any, value: Any) -> tuple[Path, dict[str, Any]]:
    """Reject relative keys and recursive envelopes instead of silently ignoring them."""
    if not isinstance(key, str) or not Path(key).is_absolute():
        raise ValueError(f"Project key must be an absolute path: {key}")
    if not isinstance(value, dict) or "projects" in value:
        raise ValueError(f"Project '{key}' must be a partial config without a projects map")
    return Path(key).resolve(), value


def validate_config_file(path: Path) -> list[str]:
    """Validate a file and every project entry; return non-fatal key warnings."""
    data = read_layer(path)
    validate_partial(data)
    return unknown_keys(
        data, str(path), allow_projects=path.resolve() == user_config_path().resolve()
    )


def file_layers(paths: ConfigPaths, root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Collect user, matching parent-to-child project settings, then project file."""
    layers: list[tuple[str, dict[str, Any]]] = []
    if paths.user.exists():
        user = read_layer(paths.user)
        layers.append((f"user ({paths.user})", user))
        projects = sorted(project_layers(user), key=lambda item: (len(item[0].parts), str(item[0])))
        for project, layer in projects:
            if root.is_relative_to(project):
                layers.append((f"user projects[{project}]", layer))
    if paths.project.exists():
        layers.append((f"project ({paths.project})", read_layer(paths.project)))
    return layers


def layer_label(label: str, config_path: Path | None) -> str:
    """Identify explicit and environment-selected files in provenance output."""
    if not label.startswith("project ("):
        return label
    if config_path is not None:
        return label.replace("project (", "--config (", 1)
    if os.environ.get("ANTIPASTA_CONFIG"):
        return label.replace("project (", "ANTIPASTA_CONFIG (", 1)
    return label


def resolve_config(root: Path | None = None, config_path: Path | None = None) -> ResolvedConfig:
    """Resolve effective config without reading or writing analysis caches."""
    root_path = analysis_root(root)
    paths = resolve_paths(root_path, config_path)
    if (
        config_path is not None or os.environ.get("ANTIPASTA_CONFIG")
    ) and not paths.project.exists():
        raise FileNotFoundError(f"Configuration file not found: {paths.project}")
    data: dict[str, Any] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    defaults = AntipastaConfig.generate_default().model_dump(exclude_none=True, mode="json")
    merge_layer(data, defaults, "defaults", sources)
    for label, layer in file_layers(paths, root_path):
        label = layer_label(label, config_path)
        validate_partial(layer, data)
        if not label.startswith("user projects["):
            warnings.extend(unknown_keys(layer, label, allow_projects=label.startswith("user (")))
        merge_layer(data, expanded_layer(layer), label, sources)
    config = AntipastaConfig.model_validate(data, context={"presets_expanded": True})
    bind_default_gates(config, sources)
    effective = config.model_dump(exclude_none=True, mode="json")
    return ResolvedConfig(config, leaf_sources(effective, sources), warnings, paths)


def config_from_layer(data: dict[str, Any], base: dict[str, Any] | None = None) -> AntipastaConfig:
    """Materialize a partial layer over its inherited configuration or built-ins."""
    if base is None:
        base = AntipastaConfig.generate_default().model_dump(exclude_none=True, mode="json")
    merged = deepcopy(base)
    merge_layer(merged, expanded_layer(data), "validation", {})
    return AntipastaConfig.model_validate(merged, context={"presets_expanded": True})


def validate_projects(entries: list[tuple[Path, dict[str, Any]]], base: AntipastaConfig) -> None:
    """Validate each branch against the user layer and its ancestor project overrides."""
    inherited: dict[Path, AntipastaConfig] = {}
    for root, layer in sorted(entries, key=lambda item: len(item[0].parts)):
        parent = next((inherited[path] for path in root.parents if path in inherited), base)
        values = parent.model_dump(exclude_none=True, mode="json")
        inherited[root] = config_from_layer(layer, values)
