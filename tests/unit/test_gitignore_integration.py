"""Tests for .gitignore integration."""

from typing import Any

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig


class TestGitignoreIntegration:
    """Tests for .gitignore integration feature."""

    def test_use_gitignore_default_true(self) -> None:
        """Test that use_gitignore defaults to true."""
        config = AntipastaConfig()
        assert config.use_gitignore is True

    def test_use_gitignore_can_be_disabled(self) -> None:
        """Test that use_gitignore can be disabled."""
        config = AntipastaConfig(use_gitignore=False)
        assert config.use_gitignore is False

    def test_aggregator_loads_gitignore_when_enabled(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that aggregator loads .gitignore patterns when enabled."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            """
# Python
__pycache__/
*.pyc
build/
dist/

# IDE
.vscode/
.idea/
"""
        )

        # Create test files
        main_file = tmp_path / "main.py"
        main_file.write_text("def main(): pass")

        cache_file = tmp_path / "__pycache__" / "main.pyc"
        cache_file.parent.mkdir()
        cache_file.write_text("compiled")

        build_file = tmp_path / "build" / "output.py"
        build_file.parent.mkdir()
        build_file.write_text("def output(): pass")

        # Create config with use_gitignore=true
        config = AntipastaConfig(use_gitignore=True)
        aggregator = MetricAggregator(config)

        # Analyze files - gitignored files should be skipped
        reports = aggregator.analyze_files([main_file, cache_file, build_file])

        # Only main.py should be analyzed
        assert len(reports) == 1
        assert reports[0].file_path == main_file

    def test_aggregator_ignores_gitignore_when_disabled(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        """Test that aggregator ignores .gitignore when disabled."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.py")  # Ignore all Python files

        # Create test file
        main_file = tmp_path / "main.py"
        main_file.write_text("def main(): pass")

        # Create config with use_gitignore=false
        config = AntipastaConfig(use_gitignore=False)
        aggregator = MetricAggregator(config)

        # Analyze files - .gitignore should be ignored
        reports = aggregator.analyze_files([main_file])

        # main.py should be analyzed despite being in .gitignore
        assert len(reports) == 1
        assert reports[0].file_path == main_file

    def test_gitignore_combined_with_ignore_patterns(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that .gitignore patterns are combined with ignore_patterns."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("build/")

        # Create test files
        main_file = tmp_path / "main.py"
        main_file.write_text("def main(): pass")

        test_file = tmp_path / "test_main.py"
        test_file.write_text("def test(): pass")

        build_file = tmp_path / "build" / "output.py"
        build_file.parent.mkdir()
        build_file.write_text("def output(): pass")

        # Create config with both .gitignore and ignore_patterns
        config = AntipastaConfig(use_gitignore=True, ignore_patterns=["test_*.py"])
        aggregator = MetricAggregator(config)

        # Analyze files
        reports = aggregator.analyze_files([main_file, test_file, build_file])

        # Only main.py should be analyzed
        # test_file is ignored by ignore_patterns
        # build_file is ignored by .gitignore
        assert len(reports) == 1
        assert reports[0].file_path == main_file

    def test_missing_gitignore_file(self, tmp_path: Any, monkeypatch: Any) -> None:
        """Test that missing .gitignore file doesn't cause errors."""
        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Create test file (no .gitignore)
        main_file = tmp_path / "main.py"
        main_file.write_text("def main(): pass")

        # Create config with use_gitignore=true
        config = AntipastaConfig(use_gitignore=True)
        aggregator = MetricAggregator(config)

        # Should work without errors
        reports = aggregator.analyze_files([main_file])
        assert len(reports) == 1

    def test_from_yaml_preserves_use_gitignore(self, tmp_path: Any) -> None:
        """Test that loading from YAML preserves use_gitignore setting."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
use_gitignore: false

defaults:
  max_cyclomatic_complexity: 10
"""
        )

        config = AntipastaConfig.from_yaml(config_file)
        assert config.use_gitignore is False

    def test_default_config_includes_use_gitignore(self) -> None:
        """Test that default generated config has use_gitignore=true."""
        config = AntipastaConfig.generate_default()
        assert config.use_gitignore is True
