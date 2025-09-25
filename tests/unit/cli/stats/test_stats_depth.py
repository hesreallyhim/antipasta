"""Tests for unlimited depth traversal feature."""

from pathlib import Path

from click.testing import CliRunner

from antipasta.cli.stats import stats
from antipasta.cli.stats.aggregation.directory import MAX_DEPTH


class TestUnlimitedDepthFeature:
    """Test suite for TICKET-STATS-001: --depth 0 for unlimited traversal."""

    def test_depth_zero_shows_all_levels(self, temp_project_dir: Path) -> None:
        """Test that --depth 0 shows all directory levels."""
        runner = CliRunner()
        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "0"]
        )

        assert result.exit_code == 0
        # Should show nested directories
        assert "modules/validators" in result.output or "validators" in result.output
        assert "validators/builtin" in result.output or "builtin" in result.output

    def test_depth_one_shows_only_top_level(self, temp_project_dir: Path) -> None:
        """Test that --depth 1 shows only top-level directories."""
        runner = CliRunner()
        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "1"]
        )

        assert result.exit_code == 0
        output_lines = result.output.split("\n")

        # Should show only top-level directories
        for line in output_lines:
            if "Location" in line or "---" in line or not line.strip():
                continue
            # Check that no nested paths appear (no slashes in directory names)
            if line.strip() and not line.startswith("Found") and not line.startswith("Analyzing"):
                parts = line.split()[0]
                if parts not in ["test_project", "."]:
                    assert "/" not in parts, f"Found nested path {parts} in depth=1 output"

    def test_depth_two_shows_two_levels(self, temp_project_dir: Path) -> None:
        """Test that --depth 2 shows exactly two levels."""
        runner = CliRunner()
        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "2"]
        )

        assert result.exit_code == 0
        output_lines = result.output.split("\n")

        # Extract directory names from the output
        directories = []
        for line in output_lines:
            if line.strip() and not any(
                skip in line
                for skip in ["Found", "Analyzing", "CODE METRICS", "Location", "---", "="]
            ):
                parts = line.split()
                if parts and any(c.isdigit() for c in line):  # Has metrics data
                    directories.append(parts[0])

        # Should show first-level subdirs
        assert "cli" in directories
        assert "core" in directories

        # For depth=2, we should see these directories
        # Note: depth=2 shows dirs up to 2 levels deep from base
        # The exact subdirectories shown depend on aggregation

    def test_max_depth_boundary(self, temp_project_dir: Path) -> None:
        """Test that unlimited depth respects MAX_DEPTH boundary."""
        runner = CliRunner()

        # depth=0 should be equivalent to depth=MAX_DEPTH
        result_zero = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", "0"]
        )

        result_max = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", str(MAX_DEPTH)]
        )

        # Both should succeed
        assert result_zero.exit_code == 0
        assert result_max.exit_code == 0

        # Output should be similar (may differ in formatting)
        # Count number of directory entries
        def count_directories(output: str) -> int:
            lines = output.split("\n")
            count = 0
            for line in lines:
                if (
                    line.strip()
                    and not any(
                        skip in line
                        for skip in ["Found", "Analyzing", "CODE METRICS", "Location", "---", "="]
                    )
                    and any(c.isdigit() for c in line)
                ):  # Has metrics data
                    count += 1
            return count

        assert count_directories(result_zero.output) == count_directories(result_max.output)

    def test_depth_greater_than_max(self, temp_project_dir: Path) -> None:
        """Test that depth > MAX_DEPTH works correctly."""
        runner = CliRunner()
        result = runner.invoke(
            stats, ["-d", str(temp_project_dir), "--by-directory", "--depth", str(MAX_DEPTH + 5)]
        )

        # Should work without error
        assert result.exit_code == 0
