"""Command contracts for effective configuration and user config locations."""

import json
from pathlib import Path

from click.testing import CliRunner
import pytest
import yaml

from antipasta.cli.main import cli
from antipasta.core.model.config_paths import user_config_path


def test_view_effective_layers_and_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    user_dir = tmp_path / "settings"
    user_file = user_dir / "antipasta" / "config.yaml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text("defaults:\n  max_cognitive_complexity: 22\n")
    root = tmp_path / "project"
    root.mkdir()
    (root / ".antipasta.yaml").write_text(
        "defaults:\n  max_cyclomatic_complexity: 8\nnarrative: {}\n"
        "languages:\n  - name: python\n    metrics: []\n"
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_dir))
    result = CliRunner().invoke(
        cli, ["config", "view", "-d", str(root), "--sources", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["defaults"]["max_cyclomatic_complexity"] == 8
    assert data["defaults"]["max_cognitive_complexity"] == 22
    assert data["languages"][0]["metrics"] == []
    assert "languages.python.metrics:" in result.stderr
    assert str(user_file) in result.stderr
    assert str(root / ".antipasta.yaml") in result.stderr
    assert "narrative" in result.stderr


def test_validate_unknown_keys_and_unused_project_entries(tmp_path: Path) -> None:
    file = user_config_path()
    file.parent.mkdir(parents=True)
    file.write_text(
        yaml.safe_dump({"narrative": {}, "projects": {str(tmp_path): {"narrative": {}}}})
    )
    result = CliRunner().invoke(cli, ["config", "validate", str(file)])
    assert result.exit_code == 0, result.output
    assert "narrative" in result.stderr
    file.write_text(
        yaml.safe_dump({
            "projects": {str(tmp_path): {"defaults": {"max_cyclomatic_complexity": -1}}}
        })
    )
    result = CliRunner().invoke(cli, ["config", "validate", str(file)])
    assert result.exit_code == 1


def test_config_path_resolves_locations_without_creating_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "settings"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["config", "path", "-d", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert f"User config: {tmp_path / 'settings' / 'antipasta' / 'config.yaml'}" in result.output
    assert f"Project config: {tmp_path / '.antipasta.yaml'}" in result.output
    assert "Cache:" in result.output
    assert "Snapshot:" in result.output
    assert not (tmp_path / "settings").exists()


def test_generate_project_and_conflicting_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["config", "generate", "--project", "--non-interactive"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".antipasta.yaml").exists()
    result = CliRunner().invoke(cli, ["config", "generate", "--project", "--output", "custom.yaml"])
    assert result.exit_code == 2
    assert not (tmp_path / "custom.yaml").exists()


def test_generate_does_not_erase_user_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    file = tmp_path / "antipasta" / "config.yaml"
    file.parent.mkdir()
    content = yaml.safe_dump({"projects": {str(tmp_path): {"use_gitignore": False}}})
    file.write_text(content)
    result = CliRunner().invoke(cli, ["config", "generate", "--non-interactive"])
    assert result.exit_code == 1
    assert file.read_text() == content


def test_raw_requires_an_explicit_file() -> None:
    result = CliRunner().invoke(cli, ["config", "view", "--format", "raw"])
    assert result.exit_code == 2
    assert "requires --path" in result.output


def test_validate_partial_language_uses_builtins_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_dir = tmp_path / "settings"
    user_file = user_dir / "antipasta" / "config.yaml"
    user_file.parent.mkdir(parents=True)
    user_file.write_text("defaults:\n  max_cyclomatic_complexity: -1\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_dir))
    partial = tmp_path / "partial.yaml"
    partial.write_text("languages:\n  - name: python\n    extensions: [.py]\n")
    result = CliRunner().invoke(cli, ["config", "validate", str(partial)])
    assert result.exit_code == 0, result.output
    assert "python: 6 metrics" in result.stdout


@pytest.mark.parametrize("fmt", ["yaml", "json"])
@pytest.mark.parametrize("validate", ["--validate", "--no-validate"])
def test_invalid_view_never_serializes_defaults(tmp_path: Path, fmt: str, validate: str) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("defaults:\n  max_cyclomatic_complexity: -1\n")
    result = CliRunner().invoke(
        cli, ["config", "view", "--path", str(invalid), "--format", fmt, validate]
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Effective configuration is invalid" in result.stderr


def test_view_warns_for_inactive_user_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_dir = tmp_path / "settings"
    file = user_dir / "antipasta" / "config.yaml"
    file.parent.mkdir(parents=True)
    file.write_text(yaml.safe_dump({"projects": {str(tmp_path / "other"): {"narrative": {}}}}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(user_dir))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["config", "view"])
    assert result.exit_code == 0, result.output
    assert "narrative" in result.stderr
    assert str(tmp_path / "other") in result.stderr
