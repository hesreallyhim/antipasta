"""Behavioral contracts for the unified report surface and legacy commands."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from click.testing import CliRunner
import pytest

from antipasta.cli.main import cli
from antipasta.cli.report import report
from antipasta.core.model.violations import FileReport


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A function with complexity two, usable for deterministic gating."""
    path = tmp_path / "sample.py"
    path.write_text("def branch(flag):\n    if flag:\n        return 1\n    return 0\n")
    return path


@pytest.mark.parametrize(("fail_on", "exit_code"), [(False, 0), (True, 2)])
def test_gating_is_opt_in(source: Path, fail_on: bool, exit_code: int) -> None:
    args = [str(source), "--format", "json", "--threshold", "cyc=1"]
    if fail_on:
        args.append("--fail-on")
    result = CliRunner().invoke(report, args)
    assert result.exit_code == exit_code, result.output
    assert json.loads(result.stdout)["summary"]["total_violations"] > 0


def test_positional_file_does_not_collect_siblings(source: Path) -> None:
    (source.parent / "sibling.py").write_text("value = 1\n")
    result = CliRunner().invoke(report, [str(source), "--format", "json"])
    assert result.exit_code == 0, result.output
    snapshot = json.loads(result.stdout)
    assert [file["path"] for file in snapshot["files"]] == ["sample.py"]


def test_positional_directory_uses_its_project_config(source: Path) -> None:
    (source.parent / ".antipasta.yaml").write_text(
        "languages:\n  - name: python\n    metrics:\n"
        "      - type: cyclomatic_complexity\n        threshold: 1\n"
    )
    result = CliRunner().invoke(report, [str(source.parent), "--format", "json", "--fail-on"])
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout)["files"][0]["violations"][0]["threshold"] == 1


@pytest.mark.parametrize("flag", ["--files", "--directory"])
def test_positional_and_legacy_targets_cannot_be_mixed(source: Path, flag: str) -> None:
    value = source if flag == "--files" else source.parent
    result = CliRunner().invoke(report, [str(source), flag, str(value)])
    assert result.exit_code == 2
    assert "cannot be combined" in result.stderr


@pytest.mark.parametrize("output_format", ["html", "json"])
def test_grouping_rejects_snapshot_formats(source: Path, output_format: str) -> None:
    result = CliRunner().invoke(
        report, [str(source), "--format", output_format, "--by", "directory"]
    )
    assert result.exit_code == 2
    assert "--by requires --format table" in result.stderr


@pytest.mark.parametrize("grouping", ["directory", "module"])
def test_grouping_reuses_single_analysis(
    source: Path, monkeypatch: pytest.MonkeyPatch, grouping: str
) -> None:
    command = importlib.import_module("antipasta.cli.report.command")
    spy = Mock(wraps=command.execute_analysis)
    monkeypatch.setattr(command, "execute_analysis", spy)
    result = CliRunner().invoke(report, [str(source.parent), "--format", "table", "--by", grouping])
    assert result.exit_code == 0, result.output
    assert "CODE METRICS BY" in result.stdout
    assert spy.call_count == 1


def test_quiet_preserves_report_data(source: Path) -> None:
    result = CliRunner().invoke(report, [str(source), "--format", "json", "--quiet"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["summary"]["total_files"] == 1
    assert "Analyzing" not in result.stderr


def test_analysis_errors_remain_failures(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    command = importlib.import_module("antipasta.cli.report.command")
    failed = FileReport(
        file_path=source, language="python", metrics=[], violations=[], error="parser failed"
    )
    results: dict[str, Any] = {
        "reports": [failed],
        "summary": {"total_files": 1, "total_violations": 0, "success": True},
    }
    monkeypatch.setattr(command, "execute_analysis", lambda *args, **kwargs: results)
    result = CliRunner().invoke(report, [str(source), "--format", "json"])
    assert result.exit_code == 1
    assert "parser failed" in result.stderr
    assert json.loads(result.stdout)["files"][0]["error"] == "parser failed"


def test_help_hides_legacy_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    command_lines = result.stdout.split("Commands:", 1)[1]
    assert "\n  metrics " not in command_lines
    assert "\n  stats " not in command_lines
    assert "report" in command_lines
    empty = CliRunner().invoke(cli, [])
    assert "Usage:" in empty.output


def test_legacy_metrics_still_gates_and_warns_only_on_stderr(source: Path) -> None:
    result = CliRunner().invoke(
        cli, ["metrics", "-f", str(source), "--threshold", "cyc=1", "--format", "json", "--quiet"]
    )
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout)["summary"]["total_violations"] > 0
    assert "report --fail-on" in result.stderr
    assert "deprecated" not in result.stdout


def test_legacy_stats_retains_json_and_warns_on_stderr(source: Path) -> None:
    result = CliRunner().invoke(cli, ["stats", "-d", str(source.parent), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"files"' in result.stdout
    assert "deprecated" in result.stderr
    assert "deprecated" not in result.stdout


def test_explicit_missing_config_fails(source: Path) -> None:
    result = CliRunner().invoke(
        report, [str(source), "--config", str(source.parent / "missing.yaml")]
    )
    assert result.exit_code == 1
    assert "missing.yaml" in result.stderr
