"""Layer precedence must preserve explicit gates and useful provenance."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from antipasta.core.model.config_layers import resolve_config, validate_config_file
from antipasta.core.model.config_override import ConfigOverride
from antipasta.core.model.config_paths import resolve_paths, user_config_path


def write_config(path: Path, **values: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    return path


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    return repo


def test_missing_optional_layers_use_defaults(root: Path) -> None:
    resolved = resolve_config(root)
    assert resolved.config.defaults.max_cyclomatic_complexity == 10
    assert resolved.sources["languages.python.metrics"] == "defaults"
    assert not resolved.warnings


def test_nested_keys_and_lists_have_independent_precedence(root: Path) -> None:
    write_config(
        user_config_path(), defaults={"max_cyclomatic_complexity": 8}, ignore_patterns=["one"]
    )
    write_config(
        root / ".antipasta.yaml", defaults={"max_halstead_difficulty": 6}, ignore_patterns=[]
    )
    resolved = resolve_config(root)
    assert resolved.config.defaults.max_cyclomatic_complexity == 8
    assert resolved.config.defaults.max_halstead_difficulty == 6
    assert resolved.config.ignore_patterns == []
    assert resolved.sources["defaults.max_cyclomatic_complexity"].startswith("user (")
    assert resolved.sources["defaults.max_halstead_difficulty"].startswith("project (")
    assert resolved.sources["ignore_patterns"].startswith("project (")


def test_project_metric_list_removes_default_gates(root: Path) -> None:
    write_config(
        root / ".antipasta.yaml",
        languages=[
            {"name": "Python", "metrics": [{"type": "cyclomatic_complexity", "threshold": 7}]}
        ],
    )
    resolved = resolve_config(root)
    python = resolved.config.get_language_config("python")
    assert python is not None
    assert len(python.metrics) == 1
    assert python.extensions == [".py"]
    assert python.metrics[0].threshold == 7
    assert resolved.sources["languages.python.metrics"].startswith("project (")


def test_preset_expands_only_within_its_layer(root: Path) -> None:
    write_config(user_config_path(), preset="readable")
    write_config(
        root / ".antipasta.yaml",
        languages=[{"name": "python", "metrics": [{"type": "lines_of_code", "threshold": 900}]}],
    )
    resolved = resolve_config(root)
    python = resolved.config.get_language_config("python")
    javascript = resolved.config.get_language_config("javascript")
    assert python is not None
    assert javascript is not None
    assert [m.type.value for m in python.metrics] == ["lines_of_code"]
    assert javascript.metrics[0].threshold == 8
    override = ConfigOverride(disable_gitignore=True)
    overridden = resolved.config.apply_overrides(override).get_language_config("python")
    assert overridden is not None
    assert [m.type.value for m in overridden.metrics] == ["lines_of_code"]


def test_preset_overrides_materialized_builtin_values(root: Path) -> None:
    write_config(root / ".antipasta.yaml", preset="readable", profile="extreme")
    python = resolve_config(root).config.get_language_config("python")
    assert python is not None
    gates = {m.type.value: m for m in python.metrics}
    assert gates["cyclomatic_complexity"].threshold == 6
    assert gates["cognitive_complexity"].enabled
    assert gates["cognitive_complexity"].threshold == 8


def test_environment_replaces_project_and_explicit_path_wins(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(user_config_path(), defaults={"max_halstead_difficulty": 4})
    write_config(root / ".antipasta.yaml", ignore_patterns=["project"])
    env = write_config(root / "env.yaml", ignore_patterns=["environment"])
    explicit = write_config(root / "explicit.yaml", ignore_patterns=["explicit"])
    monkeypatch.setenv("ANTIPASTA_CONFIG", str(env))
    assert resolve_config(root).config.ignore_patterns == ["environment"]
    assert resolve_config(root).config.defaults.max_halstead_difficulty == 4
    assert resolve_config(root, explicit).config.ignore_patterns == ["explicit"]


def test_missing_explicit_environment_file_is_an_error(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTIPASTA_CONFIG", str(root / "missing.yaml"))
    with pytest.raises(FileNotFoundError):
        resolve_config(root)


def test_root_config_precedes_cwd_fallback(root: Path) -> None:
    nested = root / "src"
    nested.mkdir()
    write_config(root / ".antipasta.yaml", use_gitignore=False)
    assert not resolve_config(nested).config.use_gitignore
    write_config(nested / ".antipasta.yaml", use_gitignore=True)
    assert resolve_config(nested).config.use_gitignore


def test_projects_apply_parent_then_child_without_prefix_collisions(root: Path) -> None:
    child = root / "src"
    child.mkdir()
    write_config(
        user_config_path(),
        projects={
            str(root): {"defaults": {"max_cyclomatic_complexity": 7}},
            str(child): {"defaults": {"max_halstead_difficulty": 3}},
            str(root / "s"): {"use_gitignore": False},
        },
    )
    resolved = resolve_config(child)
    assert resolved.config.defaults.max_cyclomatic_complexity == 7
    assert resolved.config.defaults.max_halstead_difficulty == 3
    assert resolved.config.use_gitignore
    assert str(child) in resolved.sources["defaults.max_halstead_difficulty"]


def test_optional_block_defaults_get_declaring_source(root: Path) -> None:
    write_config(user_config_path(), duplication={})
    resolved = resolve_config(root)
    assert resolved.sources["duplication.min_count"].startswith("user (")


def test_invalid_lower_layer_not_masked_by_higher_layer(root: Path) -> None:
    write_config(user_config_path(), defaults={"max_cyclomatic_complexity": -1})
    write_config(root / ".antipasta.yaml", defaults={"max_cyclomatic_complexity": 10})
    with pytest.raises(ValueError, match="validation|must|Duplicate"):
        resolve_config(root)


@pytest.mark.parametrize(
    "values",
    [
        {"projects": {"relative/repo": {}}},
        {"projects": {"/repo": {"languages": "invalid"}}},
        {"projects": {"/repo": {"projects": {}}}},
        {"languages": [{"name": "python", "metrics": []}, {"name": "Python", "metrics": []}]},
    ],
)
def test_validate_rejects_invalid_envelopes(root: Path, values: dict[str, object]) -> None:
    path = write_config(root / "bad.yaml", **values)
    with pytest.raises(ValueError, match="validation|must|Duplicate"):
        validate_config_file(path)


def test_unknown_keys_warn_including_inactive_projects(root: Path) -> None:
    path = write_config(user_config_path(), narrative={}, projects={"/elsewhere": {"old_key": 1}})
    warnings = validate_config_file(path)
    assert any("narrative" in warning for warning in warnings)
    assert any("old_key" in warning for warning in warnings)
    assert any("narrative" in warning for warning in resolve_config(root).warnings)


def test_windows_config_and_snapshot_paths(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(root / "roaming"))
    with patch("antipasta.core.model.config_paths.platform.system", return_value="Windows"):
        assert user_config_path() == root / "roaming" / "antipasta" / "config.yaml"
    paths = resolve_paths(root)
    assert paths.snapshot.parent == paths.cache / "snapshots"


def test_config_home_fallback(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME")
    with patch("antipasta.core.model.config_paths.Path.home", return_value=root):
        assert user_config_path() == root / ".config" / "antipasta" / "config.yaml"
