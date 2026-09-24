"""Exercise the default table and previous-run cache through the public command."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
import pytest

from antipasta.cli.report import report
from antipasta.core.model.config_paths import snapshot_path
from antipasta.core.model.violations import FileReport

SIMPLE = "def work(a, b):\n    return 0\n"
BRANCH = "def work(a, b):\n    if a:\n        return 1\n    return 0\n"
TWO_BRANCHES = (
    "def work(a, b):\n    if a:\n        return 1\n    if b:\n        return 2\n    return 0\n"
)


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "sample.py"
    path.write_text(SIMPLE)
    return path


def metric_line(output: str) -> str:
    return next(
        line for line in output.splitlines() if line.startswith("cyclomatic_complexity [function]")
    )


def test_first_run_table_then_cached_delta(source: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(report, [str(source)])
    assert first.exit_code == 0, first.output
    assert "Complexity\n" in first.stdout
    assert " | Delta" not in first.stdout
    assert "Violations:" in first.stdout
    source.write_text(BRANCH)
    second = runner.invoke(report, [str(source)])
    assert second.exit_code == 0, second.output
    assert " | Delta" in second.stdout
    assert "worst=+1" in metric_line(second.stdout)
    snapshot = json.loads(snapshot_path(source.parent).read_text())
    assert snapshot["schema_version"] == 2
    assert snapshot["files"][0]["functions"][0]["metrics"]["cyclomatic_complexity"] == 2


def test_current_thresholds_apply_to_both_runs(source: Path) -> None:
    source.write_text(BRANCH)
    runner = CliRunner()
    first = runner.invoke(report, [str(source), "--threshold", "cyc=1", "--fail-on"])
    assert first.exit_code == 2
    assert "Exit status: 2" in first.stdout
    second = runner.invoke(report, [str(source), "--threshold", "cyc=10", "--fail-on"])
    assert second.exit_code == 0, second.output
    line = metric_line(second.stdout)
    assert "over=0" in line
    assert "over=+0" in line
    assert "worst=+0" in line


def test_explicit_baseline_wins_over_cache(source: Path) -> None:
    baseline = source.parent / "baseline.json"
    runner = CliRunner()
    first = runner.invoke(report, [str(source), "--format", "json", "-o", str(baseline)])
    assert first.exit_code == 0, first.output
    source.write_text(BRANCH)
    assert runner.invoke(report, [str(source)]).exit_code == 0
    source.write_text(TWO_BRANCHES)
    final = runner.invoke(report, [str(source), "--baseline", str(baseline)])
    assert final.exit_code == 0, final.output
    assert "worst=+2" in metric_line(final.stdout)


def test_selection_changes_suppress_delta(source: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(report, [str(source)]).exit_code == 0
    directory = runner.invoke(report, [str(source.parent)])
    assert directory.exit_code == 0, directory.output
    assert " | Delta" not in directory.stdout


def test_json_stays_pristine_while_cache_is_updated(source: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(report, [str(source)]).exit_code == 0
    source.write_text(BRANCH)
    result = runner.invoke(report, [str(source), "--format", "json"])
    assert result.exit_code == 0, result.output
    snapshot = json.loads(result.stdout)
    assert "baseline" not in snapshot
    assert "selection" not in snapshot
    assert json.loads(snapshot_path(source.parent).read_text()) == snapshot


def test_cache_corruption_and_deletion_reset_delta(source: Path) -> None:
    runner = CliRunner()
    assert runner.invoke(report, [str(source)]).exit_code == 0
    path = snapshot_path(source.parent)
    path.write_text("not json")
    corrupt = runner.invoke(report, [str(source)])
    assert corrupt.exit_code == 0, corrupt.output
    assert " | Delta" not in corrupt.stdout
    path.unlink()
    deleted = runner.invoke(report, [str(source)])
    assert deleted.exit_code == 0, deleted.output
    assert " | Delta" not in deleted.stdout


@pytest.mark.parametrize("grouping", [None, "directory", "module"])
def test_failed_analysis_does_not_replace_previous_snapshot(
    source: Path, monkeypatch: pytest.MonkeyPatch, grouping: str | None
) -> None:
    runner = CliRunner()
    assert runner.invoke(report, [str(source)]).exit_code == 0
    path = snapshot_path(source.parent)
    previous = path.read_bytes()
    command = importlib.import_module("antipasta.cli.report.command")
    results = {
        "reports": [
            FileReport(
                file_path=source,
                language="python",
                metrics=[],
                violations=[],
                error="parser failed",
            )
        ],
        "summary": {"total_files": 1, "total_violations": 0, "success": True},
    }
    monkeypatch.setattr(command, "execute_analysis", lambda *args, **kwargs: results)
    args = [str(source), "--fail-on"]
    if grouping:
        args.extend(["--by", grouping])
    failed = runner.invoke(report, args)
    assert failed.exit_code == 1, failed.output
    assert "Exit status: 1" in failed.stdout
    assert path.read_bytes() == previous


def test_cache_write_failure_does_not_fail_report(source: Path) -> None:
    with patch(
        "antipasta.core.store.snapshot_cache._atomic_write", side_effect=OSError("read-only")
    ):
        result = CliRunner().invoke(report, [str(source)])
    assert result.exit_code == 0, result.output
    assert "Violations:" in result.stdout


def test_invalid_yaml_config_is_clean_error(source: Path) -> None:
    (source.parent / ".antipasta.yaml").write_text("languages: [\n")
    result = CliRunner().invoke(report, [str(source)])
    assert result.exit_code == 1
    assert "Invalid YAML" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("write_output", [False, True])
def test_grouped_explicit_baseline_summary_stream(source: Path, write_output: bool) -> None:
    baseline = source.parent / "baseline.json"
    runner = CliRunner()
    assert (
        runner.invoke(report, [str(source), "--format", "json", "-o", str(baseline)]).exit_code == 0
    )
    source.write_text(BRANCH)
    args = [str(source), "--by", "directory", "--baseline", str(baseline)]
    if write_output:
        args.extend(["-o", str(source.parent / "grouped.txt")])
    result = runner.invoke(report, args)
    assert result.exit_code == 0, result.output
    summary_stream = result.stdout if write_output else result.stderr
    assert "Baseline diff vs" in summary_stream
    assert "Regressed functions" in summary_stream


def test_html_carries_previous_run_as_implicit_baseline(source: Path) -> None:
    runner = CliRunner()
    first = runner.invoke(report, [str(source), "--format", "html"])
    assert first.exit_code == 0, first.output
    assert '"baseline":' not in first.stdout
    source.write_text(BRANCH)
    second = runner.invoke(report, [str(source), "--format", "html"])
    assert second.exit_code == 0, second.output
    assert '"label":"previous run"' in second.stdout
    assert '"implicit":true' in second.stdout
    # The cached comparison never leaks into the JSON snapshot.
    third = runner.invoke(report, [str(source), "--format", "json"])
    assert "baseline" not in third.stdout
