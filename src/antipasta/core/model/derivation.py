"""The derivation stage: whole-program metrics over per-file facts.

Derivers are the derive half of the extract/derive split: pure functions
that receive every
file's cached facts plus the live directory tree and produce project- or
directory-scoped reports (dependency cycles, module tree shape, ...). They
run on every analysis, uncached — measured at roughly three orders of
magnitude cheaper than extraction, and recomputation is what keeps
structure-only changes (renames, moves) always visible.

The engine registers the built-in derivers; experimental ones join only when
their feature is enabled (see docs/experimental_metrics.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from antipasta.core.model.config import AntipastaConfig
    from antipasta.core.model.metrics import FactRow
    from antipasta.core.model.violations import FileReport, ProjectReport


@dataclass
class DerivationInput:
    """Everything a deriver may consult. Derivers must not perform I/O
    beyond reading the directory tree under ``root``."""

    file_reports: list[FileReport]
    facts_by_file: dict[Path, list[FactRow]]
    root: Path
    config: AntipastaConfig


Deriver = Callable[[DerivationInput], "list[ProjectReport]"]


@dataclass
class AnalysisResult:
    """Combined outcome of one analysis run: per-file and project-scoped."""

    file_reports: list[FileReport]
    project_reports: list[ProjectReport] = field(default_factory=list)
    #: JSON-serializable module dependency graph for the HTML report's SOLID
    #: view: ``{"modules": {name: {...}}, "edges": [[src, tgt], ...]}``. Empty
    #: when no derivers run (Phase 0) or no import facts were collected.
    import_graph: dict[str, object] = field(default_factory=dict)

    @property
    def has_project_violations(self) -> bool:
        """Check if any project-scoped subject has violations."""
        return any(report.has_violations for report in self.project_reports)
