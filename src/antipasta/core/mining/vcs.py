"""Version-control mining: churn, change coupling, hotspots (track B).

Opt-in by design — this never runs on the default analysis path. One
``git log --numstat`` pass over a time window yields:

- **code churn** per file (lines added + deleted, commit count);
- **change coupling** (files that change together: co-commit support), the
  strongest coupling signal static analysis cannot see;
- **hotspots** — churn × worst cyclomatic complexity, joined against the
  committed metrics snapshot (``metrics/snapshot.json``) so no re-analysis
  is needed: the metrics-history convention feeds its sibling feature;
- **test-suite health D3**: test-churn ratio (test lines changed per source
  line changed) and co-churn multiplicity (median test files touched per
  source-touching commit) — the owner's "a hundred tests break" pain,
  measured from history.

Deviation recorded: keyed caching (HEAD + window) deferred until mining is
measured slow — a 90-day log on a repo this size costs tens of milliseconds.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import operator
from pathlib import Path
import statistics
import subprocess

from antipasta.core.model.detector import is_test_path
from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.core.model.violations import ProjectReport

#: Change-coupling pairs need at least this many co-commits to be reported.
MIN_COUPLING_SUPPORT = 3

#: At most this many rows per section (the long tail is noise).
_TOP_LIMIT = 20


@dataclass
class MinedHistory:
    """One window of history, reduced to what the metrics need."""

    window_days: int
    commit_count: int = 0
    added: Counter[str] = field(default_factory=Counter)
    deleted: Counter[str] = field(default_factory=Counter)
    commits_touching: Counter[str] = field(default_factory=Counter)
    co_changes: Counter[frozenset[str]] = field(default_factory=Counter)
    test_files_per_source_commit: list[int] = field(default_factory=list)

    def churn(self, path: str) -> int:
        return self.added[path] + self.deleted[path]


def mine_history(repo_root: Path, window_days: int = 90) -> MinedHistory:
    """Run the numstat pass and fold it into a MinedHistory."""
    output = _git_numstat(repo_root, window_days)
    history = MinedHistory(window_days=window_days)
    for commit_files in _split_commits(output):
        _fold_commit(history, commit_files)
    return history


def _git_numstat(repo_root: Path, window_days: int) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            f"--since={window_days} days ago",
            "--numstat",
            "--format=format:@@commit@@",
            "--no-merges",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _split_commits(output: str) -> list[list[tuple[int, int, str]]]:
    """[(added, deleted, path), ...] per commit; binary rows dropped."""
    commits: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    for line in output.splitlines():
        if line == "@@commit@@":
            if current:
                commits.append(current)
            current = []
            continue
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            current.append((int(parts[0]), int(parts[1]), parts[2]))
    if current:
        commits.append(current)
    return commits


def _fold_commit(history: MinedHistory, files: list[tuple[int, int, str]]) -> None:
    history.commit_count += 1
    paths = sorted({path for _, _, path in files})
    _fold_line_counts(history, files, paths)
    _fold_co_changes(history, paths)
    _fold_suite_split(history, paths)


def _fold_line_counts(
    history: MinedHistory, files: list[tuple[int, int, str]], paths: list[str]
) -> None:
    for added, deleted, path in files:
        history.added[path] += added
        history.deleted[path] += deleted
    for path in paths:
        history.commits_touching[path] += 1


def _fold_co_changes(history: MinedHistory, paths: list[str]) -> None:
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            history.co_changes[frozenset((first, second))] += 1


def _fold_suite_split(history: MinedHistory, paths: list[str]) -> None:
    source_paths = [path for path in paths if not is_test_path(path)]
    test_paths = [path for path in paths if is_test_path(path)]
    if source_paths:
        history.test_files_per_source_commit.append(len(test_paths))


# ── reports ─────────────────────────────────────────────────────────────────


def history_reports(
    history: MinedHistory, complexity_by_file: dict[str, float] | None = None
) -> list[ProjectReport]:
    """All version-control reports for one mined window."""
    return [
        *_churn_reports(history, complexity_by_file or {}),
        *_coupling_reports(history),
        _suite_health_report(history),
    ]


def _churn_reports(
    history: MinedHistory, complexity_by_file: dict[str, float]
) -> list[ProjectReport]:
    ranked = sorted(history.added, key=history.churn, reverse=True)[:_TOP_LIMIT]
    reports = []
    for path in ranked:
        rows = [
            MetricResult(
                file_path=Path(path),
                metric_type=MetricType.CODE_CHURN,
                value=float(history.churn(path)),
                details={
                    "added": history.added[path],
                    "deleted": history.deleted[path],
                    "commits": history.commits_touching[path],
                },
            )
        ]
        complexity = complexity_by_file.get(path)
        if complexity is not None:
            rows.append(
                MetricResult(
                    file_path=Path(path),
                    metric_type=MetricType.HOTSPOT,
                    value=round(history.churn(path) * complexity, 1),
                    details={"worst_cyclomatic": complexity},
                )
            )
        reports.append(ProjectReport(subject=path, metrics=rows, violations=[]))
    return reports


def _coupling_reports(history: MinedHistory) -> list[ProjectReport]:
    strong = [
        (count, pair)
        for pair, count in history.co_changes.items()
        if count >= MIN_COUPLING_SUPPORT
    ]
    strong.sort(reverse=True, key=operator.itemgetter(0))
    reports = []
    for count, pair in strong[:_TOP_LIMIT]:
        first, second = sorted(pair)
        confidence = count / min(
            history.commits_touching[first], history.commits_touching[second]
        )
        row = MetricResult(
            file_path=Path(first),
            metric_type=MetricType.CHANGE_COUPLING,
            value=float(count),
            details={"confidence": round(confidence, 2), "pair": [first, second]},
        )
        reports.append(
            ProjectReport(
                subject=f"co-change: {first} <-> {second}",
                metrics=[row],
                violations=[],
            )
        )
    return reports


def _suite_health_report(history: MinedHistory) -> ProjectReport:
    """Track D3: how hard does the suite resist change?"""
    source_lines = sum(
        history.churn(path) for path in history.added if not is_test_path(path)
    )
    test_lines = sum(
        history.churn(path) for path in history.added if is_test_path(path)
    )
    ratio = test_lines / source_lines if source_lines else 0.0
    multiplicity = (
        statistics.median(history.test_files_per_source_commit)
        if history.test_files_per_source_commit
        else 0.0
    )
    rows = [
        MetricResult(
            file_path=Path("."),
            metric_type=MetricType.TEST_CHURN_RATIO,
            value=round(ratio, 3),
            details={"test_lines": test_lines, "source_lines": source_lines},
        ),
        MetricResult(
            file_path=Path("."),
            metric_type=MetricType.CO_CHURN_MULTIPLICITY,
            value=float(multiplicity),
            details={"source_commits": len(history.test_files_per_source_commit)},
        ),
    ]
    return ProjectReport(subject="suite-health", metrics=rows, violations=[])


def complexity_from_snapshot(snapshot: dict) -> dict[str, float]:  # type: ignore[type-arg]
    """Worst per-file cyclomatic complexity out of a metrics snapshot,
    keyed by the snapshot's own relative paths prefixed with its root."""
    prefix = snapshot.get("root", "")
    worst: dict[str, float] = {}
    for entry in snapshot.get("files", []):
        values = [
            fn.get("metrics", {}).get("cyclomatic_complexity", 0.0)
            for fn in entry.get("functions", [])
        ]
        if values:
            path = f"{prefix}/{entry['path']}" if prefix else entry["path"]
            worst[path] = float(max(values))
    return worst
