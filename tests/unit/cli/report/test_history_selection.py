"""Report history compares compatible file-collection modes."""

from pathlib import Path

from click.testing import CliRunner
import pytest

from antipasta.cli.report import report


def test_adding_directory_collection_suppresses_file_selection_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    selected = tmp_path / "selected.py"
    selected.write_text("value = 1\n")
    (tmp_path / "other.py").write_text("value = 2\n")
    runner = CliRunner()
    first = runner.invoke(report, ["-f", str(selected)])
    assert first.exit_code == 0, first.output
    mixed = runner.invoke(report, ["-f", str(selected), "-d", str(tmp_path)])
    assert mixed.exit_code == 0, mixed.output
    assert " | Delta" not in mixed.stdout
    assert "lines_of_code [file] | units=2" in mixed.stdout
    again = runner.invoke(report, ["-f", str(selected), "-d", str(tmp_path)])
    assert again.exit_code == 0, again.output
    assert " | Delta" in again.stdout
    selected_only = runner.invoke(report, ["-f", str(selected)])
    assert selected_only.exit_code == 0, selected_only.output
    assert " | Delta" not in selected_only.stdout


def test_default_and_explicit_directory_collection_share_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "source.py").write_text("value = 1\n")
    runner = CliRunner()
    first = runner.invoke(report, [])
    assert first.exit_code == 0, first.output
    explicit = runner.invoke(report, [str(tmp_path)])
    assert explicit.exit_code == 0, explicit.output
    assert " | Delta" in explicit.stdout


def test_alternating_repository_subdirectories_preserves_each_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".antipasta.yaml").write_text("ignore_patterns: []\n")
    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()
    source = src / "sample.py"
    source.write_text("def work(value):\n    return value\n")
    (tests / "sample.py").write_text("value = 1\n")
    runner = CliRunner()
    first = runner.invoke(report, [str(src)])
    assert first.exit_code == 0, first.output
    other = runner.invoke(report, [str(tests)])
    assert other.exit_code == 0, other.output
    source.write_text("def work(value):\n    if value:\n        return 1\n    return 0\n")
    changed = runner.invoke(report, [str(src)])
    assert changed.exit_code == 0, changed.output
    assert " | Delta" in changed.stdout
    assert "worst=+1" in changed.stdout
    other_again = runner.invoke(report, [str(tests)])
    assert other_again.exit_code == 0, other_again.output
    assert " | Delta" in other_again.stdout
