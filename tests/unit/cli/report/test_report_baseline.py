"""Tests for `antipasta report --baseline` and `--save-baseline`.

Covers the two-command trend workflow: snapshot once, change the code, run
again against the saved baseline — for both output formats, plus the output
stream discipline and schema-drift warnings.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from click.testing import CliRunner, Result
import pytest

from antipasta.cli.report import report

SIMPLE_SOURCE = "def hello():\n    return 'world'\n"

BRANCHY_SOURCE = (
    "def hello(a=0, b=0):\n"
    "    if a:\n"
    "        if b:\n"
    "            return 'both'\n"
    "        return 'a'\n"
    "    if b:\n"
    "        return 'b'\n"
    "    return 'world'\n"
)


def _run(args: list[str], cwd: Path) -> Result:
    """Invoke the report command against a missing config (defaults)."""
    runner = CliRunner()
    return runner.invoke(report, [*args, "-c", str(cwd / "missing.yaml")])


def _write_baseline(directory: Path, baseline_path: Path, source: str = SIMPLE_SOURCE) -> None:
    """Analyze `source` in `directory` and save the JSON snapshot."""
    (directory / "sample.py").write_text(source)
    result = _run(
        ["-d", str(directory), "--format", "json", "-o", str(baseline_path)], directory
    )
    assert result.exit_code == 0, result.output


class TestBaselineOption:
    """`--baseline` diffing behavior."""

    def test_delta_summary_shows_regression(self, tmp_path: Path) -> None:
        """Growing a function's complexity shows up as a regressed function."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        (tmp_path / "sample.py").write_text(BRANCHY_SOURCE)
        out = tmp_path / "snap2.json"

        result = _run(
            [
                "-d",
                str(tmp_path),
                "--format",
                "json",
                "-o",
                str(out),
                "--baseline",
                str(baseline_path),
            ],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        # Data went to a file, so the summary shares stdout.
        assert "Baseline diff vs" in result.stdout
        assert "Regressed functions" in result.stdout
        assert "hello" in result.stdout

    def test_summary_goes_to_stderr_when_data_on_stdout(self, tmp_path: Path) -> None:
        """Without -o the JSON stays clean on stdout; the summary uses stderr."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        (tmp_path / "sample.py").write_text(BRANCHY_SOURCE)

        result = _run(
            ["-d", str(tmp_path), "--format", "json", "--baseline", str(baseline_path)],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        snapshot = json.loads(result.stdout)  # stdout must still parse as JSON
        assert snapshot["schema_version"] == 1
        assert "baseline" not in snapshot  # JSON snapshot format is unchanged
        assert "Baseline diff vs" in result.stderr

    def test_identical_runs_report_no_differences(self, tmp_path: Path) -> None:
        """Re-running unchanged code against its own snapshot shows no drift."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        out = tmp_path / "snap2.json"

        result = _run(
            [
                "-d",
                str(tmp_path),
                "--format",
                "json",
                "-o",
                str(out),
                "--baseline",
                str(baseline_path),
            ],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert "No differences" in result.stdout

    def test_html_gets_vs_baseline_mode_and_stays_offline(self, tmp_path: Path) -> None:
        """HTML embeds the baseline payload without breaking the offline guard."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        (tmp_path / "sample.py").write_text(BRANCHY_SOURCE)
        out = tmp_path / "report.html"

        result = _run(
            ["-d", str(tmp_path), "-o", str(out), "--baseline", str(baseline_path)],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        html = out.read_text()
        assert '"baseline":{"label":"base.json"' in html
        assert '"regressions":[' in html
        assert re.search(r"https?://", html, re.IGNORECASE) is None
        assert "<script src" not in html

    def test_schema_drift_warns_on_stderr(self, tmp_path: Path) -> None:
        """A baseline from another schema version warns but still diffs."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        drifted: dict[str, Any] = json.loads(baseline_path.read_text())
        drifted["schema_version"] = 0
        baseline_path.write_text(json.dumps(drifted))
        out = tmp_path / "snap2.json"

        result = _run(
            [
                "-d",
                str(tmp_path),
                "--format",
                "json",
                "-o",
                str(out),
                "--baseline",
                str(baseline_path),
            ],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        assert "schema_version" in result.stderr
        assert "Warning" in result.stderr

    @pytest.mark.parametrize("content", ["not json at all", "[1, 2, 3]"])
    def test_unreadable_baseline_is_a_clean_error(self, tmp_path: Path, content: str) -> None:
        """Invalid baseline files fail with a message, not a traceback."""
        (tmp_path / "sample.py").write_text(SIMPLE_SOURCE)
        baseline_path = tmp_path / "bad.json"
        baseline_path.write_text(content)

        result = _run(
            ["-d", str(tmp_path), "--format", "json", "--baseline", str(baseline_path)],
            tmp_path,
        )

        assert result.exit_code != 0
        assert "baseline snapshot" in result.stderr.lower()
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestSaveBaseline:
    """`--save-baseline` snapshot persistence."""

    def test_written_next_to_output(self, tmp_path: Path) -> None:
        """report.html gets a sibling report.baseline.json (pristine snapshot)."""
        (tmp_path / "sample.py").write_text(SIMPLE_SOURCE)
        out = tmp_path / "report.html"

        result = _run(
            ["-d", str(tmp_path), "-o", str(out), "--save-baseline"],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        saved = json.loads((tmp_path / "report.baseline.json").read_text())
        assert saved["schema_version"] == 1
        assert saved["summary"]["total_files"] == 1

    def test_saved_snapshot_never_contains_embedded_diff(self, tmp_path: Path) -> None:
        """Even with --baseline in the same run, the saved snapshot stays pure."""
        baseline_path = tmp_path / "base.json"
        _write_baseline(tmp_path, baseline_path)
        (tmp_path / "sample.py").write_text(BRANCHY_SOURCE)
        out = tmp_path / "report.html"

        result = _run(
            [
                "-d",
                str(tmp_path),
                "-o",
                str(out),
                "--baseline",
                str(baseline_path),
                "--save-baseline",
            ],
            tmp_path,
        )

        assert result.exit_code == 0, result.output
        saved = json.loads((tmp_path / "report.baseline.json").read_text())
        assert "baseline" not in saved

    def test_defaults_to_report_baseline_json_without_output(self, tmp_path: Path) -> None:
        """With data on stdout there is no 'next to', so report.baseline.json."""
        (tmp_path / "sample.py").write_text(SIMPLE_SOURCE)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as fs:
            result = runner.invoke(
                report,
                [
                    "-d",
                    str(tmp_path),
                    "--format",
                    "json",
                    "--save-baseline",
                    "-c",
                    str(tmp_path / "missing.yaml"),
                ],
            )

            assert result.exit_code == 0, result.output
            saved = json.loads((Path(fs) / "report.baseline.json").read_text())
            assert saved["schema_version"] == 1
            # stdout still carries the clean snapshot
            assert json.loads(result.stdout)["schema_version"] == 1

    def test_roundtrip_save_then_diff(self, tmp_path: Path) -> None:
        """The advertised two-command workflow works end to end."""
        (tmp_path / "sample.py").write_text(SIMPLE_SOURCE)
        out = tmp_path / "report.html"
        first = _run(["-d", str(tmp_path), "-o", str(out), "--save-baseline"], tmp_path)
        assert first.exit_code == 0, first.output

        (tmp_path / "sample.py").write_text(BRANCHY_SOURCE)
        second = _run(
            [
                "-d",
                str(tmp_path),
                "-o",
                str(out),
                "--baseline",
                str(tmp_path / "report.baseline.json"),
            ],
            tmp_path,
        )

        assert second.exit_code == 0, second.output
        assert "Regressed functions" in second.stdout
        assert '"baseline":{"label":"report.baseline.json"' in out.read_text()
