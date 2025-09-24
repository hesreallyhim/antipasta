"""Tests for path display styles.""" ""

from pathlib import Path

from click.testing import CliRunner

from antipasta.cli.stats import stats


class TestPathDisplayStyles:
    """Test suite for TICKET-STATS-003: Path display styles."""

    def test_relative_style_default(self, temp_project_dir: Path) -> None:
        """Test that relative style is the default and truncates long paths."""
        runner = CliRunner()

        # Don't specify --path-style, should default to relative
        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "3"]
        )

        assert result.exit_code == 0

        # Look for truncation indicators in deep paths
        lines = result.output.split("\n")
        for line in lines:
            if (
                line.strip()
                and "/" in line
                and not any(skip in line for skip in ["Found", "Analyzing", "CODE METRICS"])
            ):
                # If path is long, should be truncated with "..."
                parts = line.split()
                if parts:
                    path = parts[0]
                    if len(path) > 30:
                        assert path.startswith("..."), f"Long path not truncated: {path}"

    def test_parent_style_shows_last_two_components(self, temp_project_dir: Path) -> None:
        """Test that parent style shows only last 2 path components."""
        runner = CliRunner()

        result = runner.invoke(
            stats,
            [
                "-d",
                str(temp_project_dir),
                "--by-directory",
                "--depth",
                "3",
                "--path-style",
                "parent",
            ],
        )

        assert result.exit_code == 0

        # For deep paths, should show only last 2 components
        lines = result.output.split("\n")
        for line in lines:
            if "modules/validators" in line:
                # In parent style, this should appear as just "terminal/widgets"
                # or "widgets" depending on context
                parts = line.split()[0]
                # Should not have more than 2 path components
                path_parts = parts.split("/")
                if len(path_parts) > 2:
                    # If truncated, should start with ...
                    assert parts.startswith("..."), f"Parent style showing >2 components: {parts}"

    def test_full_style_no_truncation(self, temp_project_dir: Path) -> None:
        """Test that full style shows complete paths without truncation."""
        runner = CliRunner()

        result = runner.invoke(
            stats,
            ["-d", str(temp_project_dir), "--by-directory", "--depth", "4", "--path-style", "full"],
        )

        assert result.exit_code == 0

        # Full paths should NOT be truncated (no "..." prefix)
        lines = result.output.split("\n")
        for line in lines:
            if line.strip() and not any(
                skip in line
                for skip in ["Found", "Analyzing", "CODE METRICS", "Location", "---", "="]
            ):
                parts = line.split()
                if parts:
                    path = parts[0]
                    # Full style should never truncate
                    assert not path.startswith("..."), f"Full style path truncated: {path}"

    def test_relative_style_explicit(self, temp_project_dir: Path) -> None:
        """Test explicitly specifying relative style."""
        runner = CliRunner()

        result = runner.invoke(
            stats,
            [
                "-d",
                str(temp_project_dir),
                "--by-directory",
                "--depth",
                "3",
                "--path-style",
                "relative",
            ],
        )

        assert result.exit_code == 0

        # Should behave same as default (truncate long paths)
        lines = result.output.split("\n")
        for line in lines:
            if "/" in line and not any(
                skip in line for skip in ["Found", "Analyzing", "CODE METRICS"]
            ):
                parts = line.split()
                if parts:
                    path = parts[0]
                    if len(path) > 30:
                        assert path.startswith("..."), f"Relative style not truncating: {path}"

    def test_path_style_only_affects_directory_mode(self, temp_project_dir: Path) -> None:
        """Test that --path-style only works with --by-directory."""
        runner = CliRunner()

        # Use relative path pattern that works with pathlib glob
        # Change to the temp directory first
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)

            # Try with --by-module (should not affect output)
            result = runner.invoke(
                stats,
                ["-p", "**/*.py", "--by-module", "--path-style", "full"],  # This should be ignored
            )

            # Should work without error
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

        # Try without any grouping
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_dir)

            result = runner.invoke(
                stats,
                ["-p", "cli/*.py", "--path-style", "parent"],  # This should be ignored
            )

            # Should work without error
            assert result.exit_code == 0
        finally:
            os.chdir(original_cwd)

    def test_truncation_length(self, temp_project_dir: Path) -> None:
        """Test that truncation is exactly 30 characters for relative/parent."""
        runner = CliRunner()

        # Test with relative
        result = runner.invoke(
            stats,
            [
                "-d",
                str(temp_project_dir),
                "--by-directory",
                "--depth",
                "4",
                "--path-style",
                "relative",
            ],
        )

        assert result.exit_code == 0

        lines = result.output.split("\n")
        for line in lines:
            if line.strip() and line.startswith("..."):
                parts = line.split()
                if parts:
                    path = parts[0]
                    # Truncated paths should be exactly 30 chars
                    assert len(path) == 30, f"Truncated path wrong length: {len(path)} - {path}"
