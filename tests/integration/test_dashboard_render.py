"""Load the rendered HTML report in a headless Chromium and check it boots.

The Python tests can only assert that the assets were inlined. This test
executes report.js for real: it fails on any console error and on any
headline section that rendered empty. It runs when a Chromium binary can be
found (``ANTIPASTA_CHROME``, a Playwright browser cache, or a system Chrome)
and is skipped otherwise, so CI without a browser stays green.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

from antipasta.core.model.config import AntipastaConfig, ComparisonOperator
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import FileReport, Violation
from antipasta.core.store.snapshot import build_snapshot
from antipasta.report import render_report

_CHROME_GLOBS = [
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app"
    "/Contents/MacOS/Google Chrome for Testing",
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
_CHROME_NAMES = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]

#: Element ids whose rendered text must be non-empty for a populated snapshot.
_HEADLINE_IDS = [
    "meta-line",
    "overall-score",
    "hero-verdict",
    "kpi-strip",
    "fix-list",
    "focus-bar",
    "cat-grid",
    "hotspots",
    "worst-total",
    "viol-break",
    "foot",
]


def _find_chrome() -> str | None:
    configured = os.environ.get("ANTIPASTA_CHROME")
    if configured:
        return configured if Path(configured).exists() else None
    for pattern in _CHROME_GLOBS:
        matches = sorted(glob.glob(os.path.expanduser(pattern)))
        if matches:
            return matches[-1]
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = _find_chrome()
pytestmark = pytest.mark.skipif(CHROME is None, reason="no Chromium binary available")


def _metric(path: str, metric: MetricType, value: float, fn: str | None = None) -> MetricResult:
    return MetricResult(file_path=Path(path), metric_type=metric, value=value, function_name=fn)


def _report(path: str, language: str, cyclomatic: float) -> FileReport:
    metrics = [
        _metric(path, MetricType.LINES_OF_CODE, 120),
        _metric(path, MetricType.SOURCE_LINES_OF_CODE, 100),
        _metric(path, MetricType.CYCLOMATIC_COMPLEXITY, cyclomatic, "run"),
    ]
    violations = []
    if language == "python":
        metrics += [
            _metric(path, MetricType.MAINTAINABILITY_INDEX, 40),
            _metric(path, MetricType.HALSTEAD_VOLUME, 500),
            _metric(path, MetricType.COGNITIVE_COMPLEXITY, 20, "run"),
        ]
    if cyclomatic > 10:
        violations.append(
            Violation(
                file_path=Path(path),
                metric_type=MetricType.CYCLOMATIC_COMPLEXITY,
                value=cyclomatic,
                threshold=10,
                comparison=ComparisonOperator.LE,
                message=f"{path} (run): Cyclomatic Complexity is {cyclomatic} (threshold: <= 10)",
                function_name="run",
            )
        )
    return FileReport(
        file_path=Path(path), language=language, metrics=metrics, violations=violations
    )


def _snapshot() -> dict[str, Any]:
    reports = [
        _report("pkg/clean.py", "python", 3),
        _report("pkg/busy.py", "python", 14),
        _report("web/app.js", "javascript", 12),
    ]
    return build_snapshot(reports, AntipastaConfig.generate_default(), root=Path.cwd())


def _render_in_browser(html: str, tmp_path: Path) -> tuple[str, str]:
    page = tmp_path / "report.html"
    page.write_text(html, encoding="utf-8")
    assert CHROME is not None
    try:
        result = _run_chrome(page)
    except subprocess.TimeoutExpired:
        pytest.skip("Chromium did not finish; a system dialog may be blocking it")
    return result.stdout, result.stderr


def _run_chrome(page: Path) -> subprocess.CompletedProcess[str]:
    assert CHROME is not None
    return subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--enable-logging=stderr",
            "--v=0",
            "--virtual-time-budget=5000",
            "--window-size=1400,1000",
            "--dump-dom",
            page.resolve().as_uri(),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _console_errors(stderr: str) -> list[str]:
    # Chromium logs page console output as CONSOLE(<line>) "..." with a
    # severity prefix; keychain/GPU chatter from the browser itself is not
    # page output and carries no CONSOLE marker.
    return [line for line in stderr.splitlines() if "CONSOLE" in line and "ERROR" in line]


def _text_of(dom: str, element_id: str) -> str:
    start = dom.find(f'id="{element_id}"')
    assert start >= 0, f"missing #{element_id}"
    fragment = dom[start:].split(">", 1)[1][:20000]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


@pytest.mark.skipif(sys.platform == "win32", reason="headless flags are POSIX-tested only")
def test_dashboard_boots_without_console_errors(tmp_path: Path) -> None:
    dom, stderr = _render_in_browser(render_report(_snapshot()), tmp_path)
    assert _console_errors(stderr) == []
    for element_id in _HEADLINE_IDS:
        assert _text_of(dom, element_id), f"#{element_id} rendered empty"
    assert "2 threshold violations" in _text_of(dom, "hero-verdict")


@pytest.mark.skipif(sys.platform == "win32", reason="headless flags are POSIX-tested only")
def test_legacy_snapshot_without_gates_block_still_renders(tmp_path: Path) -> None:
    snapshot = _snapshot()
    del snapshot["gates"]
    dom, stderr = _render_in_browser(render_report(json.loads(json.dumps(snapshot))), tmp_path)
    assert _console_errors(stderr) == []
    assert _text_of(dom, "overall-score")
    legend = _text_of(dom, "legend")
    assert "over threshold" in legend or "over gate" in legend
