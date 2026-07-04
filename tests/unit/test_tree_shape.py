"""Tests for the Module Tree Shape deriver (tree half)."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.config import AntipastaConfig, TreeShapeConfig
from antipasta.core.derivation import DerivationInput
from antipasta.core.tree_shape import derive_tree_shape
from antipasta.core.violations import FileReport, ProjectReport


def _report(path: Path) -> FileReport:
    return FileReport(file_path=path, language="python", metrics=[], violations=[])


def _derivation_input(
    root: Path, relative_files: list[str], config: AntipastaConfig | None = None
) -> DerivationInput:
    return DerivationInput(
        file_reports=[_report(root / rel) for rel in relative_files],
        facts_by_file={},
        root=root,
        config=config or AntipastaConfig(),
    )


def _by_subject(reports: list[ProjectReport]) -> dict[str, float]:
    return {r.subject: r.metrics[0].value for r in reports}


class TestChildCounting:
    def test_counts_modules_and_subpackages(self, tmp_path: Path) -> None:
        files = ["a.py", "b.py", "pkg/__init__.py", "pkg/one.py", "pkg/two.py"]
        reports = derive_tree_shape(_derivation_input(tmp_path, files))

        counts = _by_subject(reports)
        # root: a.py + b.py + pkg/ = 3 (init files are plumbing, not children)
        assert counts["."] == 3.0
        assert counts["pkg"] == 2.0

    def test_nested_layers(self, tmp_path: Path) -> None:
        files = ["app/core/engine.py", "app/core/model.py", "app/cli.py"]
        reports = derive_tree_shape(_derivation_input(tmp_path, files))

        counts = _by_subject(reports)
        assert counts["."] == 1.0  # app/
        assert counts["app"] == 2.0  # cli.py + core/
        assert counts["app/core"] == 2.0

    def test_files_outside_root_are_ignored(self, tmp_path: Path) -> None:
        derivation_input = DerivationInput(
            file_reports=[_report(Path("/somewhere/else/x.py"))],
            facts_by_file={},
            root=tmp_path,
            config=AntipastaConfig(),
        )
        assert derive_tree_shape(derivation_input) == []


class TestGating:
    def test_informational_without_config(self, tmp_path: Path) -> None:
        files = [f"wide/mod_{i}.py" for i in range(12)]
        reports = derive_tree_shape(_derivation_input(tmp_path, files))

        wide = next(r for r in reports if r.subject == "wide")
        assert wide.metrics[0].value == 12.0
        assert wide.violations == []  # rows without config are observation-only

    def test_too_many_children_violates_with_config(self, tmp_path: Path) -> None:
        config = AntipastaConfig(tree_shape=TreeShapeConfig(fan_out_max=7))
        files = [f"wide/mod_{i}.py" for i in range(12)]
        reports = derive_tree_shape(_derivation_input(tmp_path, files, config))

        wide = next(r for r in reports if r.subject == "wide")
        assert wide.has_violations

    def test_too_few_children_violates_but_root_exempt(self, tmp_path: Path) -> None:
        config = AntipastaConfig(tree_shape=TreeShapeConfig(fan_out_min=2))
        files = ["lonely/only.py"]
        reports = derive_tree_shape(_derivation_input(tmp_path, files, config))

        by_subject = {r.subject: r for r in reports}
        assert by_subject["lonely"].has_violations  # pointless layer
        assert not by_subject["."].has_violations  # root exempt from the minimum

    def test_exclusion_patterns(self, tmp_path: Path) -> None:
        config = AntipastaConfig(
            tree_shape=TreeShapeConfig(fan_out_max=3, exclude=["tests*"])
        )
        files = [f"tests_fixtures/mod_{i}.py" for i in range(9)]
        reports = derive_tree_shape(_derivation_input(tmp_path, files, config))

        assert all(r.subject != "tests_fixtures" for r in reports)
