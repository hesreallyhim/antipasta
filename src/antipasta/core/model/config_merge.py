"""Merge already expanded configuration layers without introducing new gates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def mark_sources(value: Any, prefix: str, source: str, sources: dict[str, str]) -> None:
    """Attribute leaves and container defaults to their declaring layer."""
    sources[prefix] = source
    if isinstance(value, dict):
        for key, item in value.items():
            mark_sources(item, f"{prefix}.{key}".lstrip("."), source, sources)


def merge_layer(
    target: dict[str, Any],
    layer: dict[str, Any],
    source: str,
    sources: dict[str, str],
    prefix: str = "",
) -> None:
    """Merge blocks recursively; lists replace except the named language registry."""
    for key, value in layer.items():
        path = f"{prefix}.{key}".lstrip(".")
        if key == "languages" and not prefix:
            target[key] = merge_languages(target.get(key, []), value, source, sources)
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_layer(target[key], value, source, sources, path)
        else:
            target[key] = deepcopy(value)
            replace_sources(value, path, source, sources)


def replace_sources(value: Any, path: str, source: str, sources: dict[str, str]) -> None:
    """Discard provenance under a replaced container."""
    for key in list(sources):
        if key == path or key.startswith(path + "."):
            del sources[key]
    mark_sources(value, path, source, sources)


def merge_languages(
    inherited: list[dict[str, Any]],
    incoming: Any,
    source: str,
    sources: dict[str, str],
) -> list[dict[str, Any]]:
    """Overlay languages by case-insensitive name and replace metric lists whole."""
    if not isinstance(incoming, list):
        raise ValueError("languages must be a list")
    languages = {str(item["name"]).lower(): deepcopy(item) for item in inherited}
    seen: set[str] = set()
    for item in incoming:
        name = language_name(item)
        if name in seen:
            raise ValueError(f"Duplicate language: {name}")
        seen.add(name)
        entry = languages.setdefault(name, {})
        merge_layer(entry, item, source, sources, f"languages.{name}")
    return list(languages.values())


def language_name(item: Any) -> str:
    """Require named language mappings before merging partial entries."""
    if not isinstance(item, dict) or not isinstance(item.get("name"), str):
        raise ValueError("Each language must be a mapping with a name")
    name = str(item["name"]).strip().lower()
    if not name:
        raise ValueError("Language name must not be empty")
    return name


def leaf_sources(data: dict[str, Any], sources: dict[str, str]) -> dict[str, str]:
    """Resolve provenance for validated defaults as well as explicit leaves."""
    leaves: dict[str, str] = {}
    collect_leaves(data, "", leaves)
    return {path: find_source(path, sources) for path in leaves}


def collect_leaves(data: Any, prefix: str, leaves: dict[str, str]) -> None:
    """List output keys; metric lists are intentionally single attribution units."""
    if prefix == "languages":
        for language in data:
            collect_leaves(language, f"languages.{language['name'].lower()}", leaves)
    elif isinstance(data, dict) and data:
        for key, value in data.items():
            collect_leaves(value, f"{prefix}.{key}".lstrip("."), leaves)
    else:
        leaves[prefix] = ""


def find_source(path: str, sources: dict[str, str]) -> str:
    """Model-filled block defaults belong to the layer introducing the block."""
    while path:
        if path in sources:
            return sources[path]
        path = path.rpartition(".")[0]
    return "defaults"
