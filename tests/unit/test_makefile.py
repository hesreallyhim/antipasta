"""Exercise the diagnostics contract of the public Makefile gate target."""

from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest


def test_metrics_quiet_retains_diagnostics_when_gate_fails(tmp_path: Path) -> None:
    make = shutil.which("make")
    if make is None:
        pytest.skip("make is not installed")
    fake_cli = tmp_path / "antipasta.py"
    fake_cli.write_text(
        "import sys\n"
        "assert sys.argv[1:] == "
        "['report', 'src/', '--format', 'table', '--fail-on', '--quiet']\n"
        "print('cyclomatic_complexity [function] | over=1 | example.py:1 too_complex')\n"
        "print('Violations: 1 | Exit status: 2')\n"
        "sys.exit(2)\n"
    )
    result = subprocess.run(
        [
            make,
            "-f",
            str(Path(__file__).resolve().parents[2] / "Makefile"),
            "-o",
            "install",
            "metrics-quiet",
            f"ANTIPASTA={shlex.join([sys.executable, str(fake_cli)])}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "example.py:1 too_complex" in result.stdout
    assert "Violations: 1 | Exit status: 2" in result.stdout
