"""Normalize the two snapshot row shapes without discarding scope."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from antipasta.cli.report.table_policy import (
    CLASS_METRICS,
    GROUP_METRICS,
    PROJECT_FILE_METRICS,
    SUITE_METRICS,
)


@dataclass(frozen=True)
class TableRow:
    """A single measured unit, before aggregation or threshold evaluation."""

    metric: str
    scope: str
    value: float
    subject: str
    language: str = ""
    project: bool = False
    members: tuple[str, ...] = ()


def _file_rows(entry: dict[str, Any]) -> list[TableRow]:
    path = str(entry["path"])
    language = str(entry.get("language", ""))
    rows = [
        TableRow(metric, "file", float(value), path, language)
        for metric, value in entry.get("metrics", {}).items()
    ]
    for function in entry.get("functions", []):
        subject = f"{path}:{function.get('line') or '?'} {function['name']}"
        rows.extend(
            TableRow(metric, _function_scope(metric), float(value), subject, language)
            for metric, value in function.get("metrics", {}).items()
        )
    return rows


def _function_scope(metric: str) -> str:
    return "class" if metric in CLASS_METRICS else "function"


def _project_scope(metric: str, subject: str) -> str:
    if metric in CLASS_METRICS:
        return "class"
    if metric in GROUP_METRICS:
        return "group"
    if metric in SUITE_METRICS:
        return "suite"
    if metric in PROJECT_FILE_METRICS:
        return "file"
    if metric == "directory_children":
        return "directory"
    return "package" if subject.startswith("package ") else "module"


def _project_rows(entry: dict[str, Any]) -> list[TableRow]:
    subject = str(entry["subject"])
    rows = []
    for metric in entry.get("metrics", []):
        details = metric.get("details") or {}
        if details.get("unavailable"):
            continue
        name = str(metric["type"])
        members = details.get("members", details.get("pair", ()))
        rows.append(
            TableRow(
                name,
                _project_scope(name, subject),
                float(metric["value"]),
                subject,
                project=True,
                members=tuple(str(member) for member in members),
            )
        )
    return rows


def collect_rows(snapshot: dict[str, Any]) -> dict[tuple[str, str], list[TableRow]]:
    """Index measured values by metric and scope; metadata never affects deltas."""
    grouped: dict[tuple[str, str], list[TableRow]] = defaultdict(list)
    rows = [row for entry in snapshot.get("files", []) for row in _file_rows(entry)]
    rows.extend(row for entry in snapshot.get("project", []) for row in _project_rows(entry))
    for row in rows:
        grouped[row.metric, row.scope].append(row)
    return dict(grouped)
