"""Tests for edge cases and error conditions.""" ""

from pathlib import Path

from click.testing import CliRunner

from antipasta.cli.stats import stats


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions."""

    def test_invalid_path_style(self) -> None:
        """Test that invalid path style is rejected."""
        runner = CliRunner()

        result = runner.invoke(stats, ["-d", ".", "--by-directory", "--path-style", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_negative_depth(self, temp_project_dir: Path) -> None:
        """Test that negative depth values are handled."""
        runner = CliRunner()

        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "-1"]
        )

        # Should either error or treat as 0/1
        # Implementation might vary
        assert result.exit_code == 0 or "Invalid" in result.output

    def test_very_large_depth(self, temp_project_dir: Path) -> None:
        """Test extremely large depth values."""
        runner = CliRunner()

        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "999999"]
        )

        # Should work (capped by actual directory depth)
        assert result.exit_code == 0

    def test_nonexistent_directory(self) -> None:
        """Test with non-existent directory."""
        runner = CliRunner()

        result = runner.invoke(
            stats, ["-d", "/nonexistent/directory/path", "--by-directory", "--depth", "2"]
        )

        assert result.exit_code != 0

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test with empty directory."""
        runner = CliRunner()

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(stats, ["-d", str(empty_dir), "--by-directory", "--depth", "1"])

        # Should handle gracefully
        assert "No files found" in result.output or "No analyzable files" in result.output

    def test_mixed_file_types(self, tmp_path: Path) -> None:
        """Test directory with non-Python files."""
        runner = CliRunner()

        mixed_dir = tmp_path / "mixed"
        mixed_dir.mkdir()

        # Create various file types
        (mixed_dir / "test.py").write_text("def hello(): pass")
        (mixed_dir / "readme.md").write_text("# README")
        (mixed_dir / "data.json").write_text("{}")

        result = runner.invoke(stats, ["-d", str(mixed_dir), "--by-directory", "--depth", "1"])

        assert result.exit_code == 0
        # Should only analyze Python files
        assert "1 python files" in result.output.lower()
