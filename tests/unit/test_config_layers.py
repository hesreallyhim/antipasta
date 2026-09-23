"""Layer precedence must preserve explicit gates and useful provenance."""

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
import pytest
import yaml

from antipasta.cli.main import cli
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
    path = write_config(user_config_path(), **values)
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


def javascript_language() -> dict[str, object]:
    return {
        "name": "javascript",
        "extensions": [".js"],
        "metrics": [{"type": "cyclomatic_complexity", "threshold": 8}],
    }


@pytest.mark.parametrize("preset", [True, False])
def test_partial_project_language_inherits_user_metrics(root: Path, preset: bool) -> None:
    if preset:
        write_config(user_config_path(), preset="readable")
    else:
        write_config(user_config_path(), languages=[javascript_language()])
    write_config(
        root / ".antipasta.yaml", languages=[{"name": "javascript", "extensions": [".jsx"]}]
    )
    resolved = resolve_config(root)
    javascript = resolved.config.get_language_config("javascript")
    assert javascript is not None
    assert javascript.extensions == [".jsx"]
    assert javascript.metrics[0].threshold == 8
    assert resolved.sources["languages.javascript.metrics"].startswith("user (")


@pytest.mark.parametrize("active", [True, False])
def test_partial_user_projects_inherit_user_languages(root: Path, active: bool) -> None:
    project = root if active else root / "inactive"
    path = write_config(
        user_config_path(),
        languages=[javascript_language()],
        projects={str(project): {"languages": [{"name": "javascript", "extensions": [".jsx"]}]}},
    )
    assert validate_config_file(path) == []
    javascript = resolve_config(root).config.get_language_config("javascript")
    assert javascript is not None
    assert javascript.extensions == ([".jsx"] if active else [".js"])
    assert javascript.metrics[0].threshold == 8


def test_nested_project_language_inherits_parent_project(root: Path) -> None:
    child = root / "src"
    child.mkdir()
    path = write_config(
        user_config_path(),
        projects={
            str(root): {"languages": [javascript_language()]},
            str(child): {"languages": [{"name": "javascript", "extensions": [".jsx"]}]},
        },
    )
    assert validate_config_file(path) == []
    javascript = resolve_config(child).config.get_language_config("javascript")
    assert javascript is not None
    assert javascript.extensions == [".jsx"]
    assert javascript.metrics[0].threshold == 8


def test_inactive_partial_project_values_are_still_validated(root: Path) -> None:
    path = write_config(
        user_config_path(),
        languages=[javascript_language()],
        projects={
            str(root / "inactive"): {
                "languages": [
                    {"name": "javascript", "metrics": [{"type": "unknown", "threshold": 8}]}
                ]
            }
        },
    )
    with pytest.raises(ValueError, match="validation error"):
        validate_config_file(path)
    with pytest.raises(ValueError, match="validation error"):
        resolve_config(root)


def test_defaults_only_project_config_controls_actual_gate_and_view(root: Path) -> None:
    source = root / "branch.py"
    source.write_text(
        "def branch(a, b, c):\n    if a:\n        return 1\n"
        "    if b:\n        return 2\n    if c:\n        return 3\n    return 0\n"
    )
    write_config(root / ".antipasta.yaml", defaults={"max_cyclomatic_complexity": 2})
    runner = CliRunner()
    legacy = runner.invoke(cli, ["metrics", "-d", str(root), "--quiet"])
    assert legacy.exit_code == 2, legacy.output
    report = runner.invoke(cli, ["report", str(root), "--fail-on"])
    assert report.exit_code == 2, report.output
    row = next(
        line
        for line in report.stdout.splitlines()
        if line.startswith("cyclomatic_complexity [function]")
    )
    assert "over=1" in row
    assert "worst=4" in row
    view = runner.invoke(cli, ["config", "view", "--format", "json", "--sources"])
    assert view.exit_code == 0, view.output
    python = json.loads(view.stdout)["languages"][0]
    gates = {metric["type"]: metric for metric in python["metrics"]}
    assert gates["cyclomatic_complexity"]["threshold"] == 2
    assert "thresholds from project" in view.stderr


def test_inherited_gates_follow_defaults_from_each_layer(root: Path) -> None:
    write_config(
        user_config_path(),
        defaults={"max_halstead_difficulty": 4},
        projects={str(root): {"defaults": {"min_maintainability_index": 70}}},
    )
    write_config(root / ".antipasta.yaml", defaults={"max_cyclomatic_complexity": 2})
    config = resolve_config(root).config
    python = config.get_language_config("python")
    assert python is not None
    gates = {metric.type.value: metric for metric in python.metrics}
    assert gates["cyclomatic_complexity"].threshold == 2
    assert gates["halstead_difficulty"].threshold == 4
    assert gates["maintainability_index"].threshold == 70
    assert not gates["cognitive_complexity"].enabled


@pytest.mark.parametrize("preset", [False, True])
def test_default_changes_do_not_override_explicit_or_preset_gates(root: Path, preset: bool) -> None:
    if preset:
        write_config(user_config_path(), preset="readable")
    else:
        write_config(
            user_config_path(),
            languages=[
                {"name": "python", "metrics": [{"type": "cyclomatic_complexity", "threshold": 8}]}
            ],
        )
    write_config(root / ".antipasta.yaml", defaults={"max_cyclomatic_complexity": 2})
    python = resolve_config(root).config.get_language_config("python")
    assert python is not None
    assert python.metrics[0].threshold == 8


def test_project_projects_map_is_warned_and_ignored(root: Path) -> None:
    project = write_config(
        root / ".antipasta.yaml",
        projects={str(root): {"defaults": {"max_cyclomatic_complexity": 2}}},
    )
    resolved = resolve_config(root)
    assert resolved.config.defaults.max_cyclomatic_complexity == 10
    assert any(
        "only supported in the user configuration" in warning for warning in resolved.warnings
    )
    assert any("projects" in warning for warning in validate_config_file(project))


@pytest.mark.parametrize("command", ["view", "validate"])
def test_project_projects_warning_reaches_config_commands(root: Path, command: str) -> None:
    write_config(root / ".antipasta.yaml", projects="ignored even when not a valid user map")
    result = CliRunner().invoke(cli, ["config", command])
    assert result.exit_code == 0, result.output
    assert "'projects' is only supported" in result.stderr
