"""Tests for metric inclusion logic.""" ""

from pathlib import Path

from click.testing import CliRunner

from antipasta.cli.stats import stats


class TestMetricInclusionLogic:
    """Test suite for TICKET-STATS-002: Fix LOC always showing bug."""

    def test_loc_not_shown_when_other_metric_requested(self, temp_project_dir: Path) -> None:
        """Test that LOC is NOT shown when only other metrics are requested."""
        runner = CliRunner()

        # Request only cyclomatic complexity
        with runner.isolated_filesystem():
            # Create test files in isolated filesystem
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test1.py").write_text("def func():\n    if True:\n        return 1\n")
            (cli_dir / "test2.py").write_text(
                "def func2():\n    for i in range(10):\n        pass\n"
            )

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "cyc"])

        assert result.exit_code == 0

        # LOC should NOT appear in output
        assert "Total LOC" not in result.output
        assert "Avg File LOC" not in result.output
        assert "avg_file_loc" not in result.output.lower()

        # But cyclomatic should appear
        assert "Cyclomat" in result.output or "cyclomat" in result.output.lower()

    def test_loc_shown_by_default_no_flags(self, temp_project_dir: Path) -> None:
        """Test that LOC IS shown by default when no -m flags."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    pass\n")

            result = runner.invoke(stats, ["-p", "cli/*.py"])

        assert result.exit_code == 0

        # LOC should appear
        assert "Total LOC" in result.output or "total_loc" in result.output.lower()

    def test_loc_shown_when_explicitly_requested(self, temp_project_dir: Path) -> None:
        """Test that LOC IS shown when explicitly requested with -m loc."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    pass\n")

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "loc"])

        assert result.exit_code == 0

        # LOC should appear
        assert "Total LOC" in result.output or "total_loc" in result.output.lower()

    def test_loc_shown_with_all_metrics(self, temp_project_dir: Path) -> None:
        """Test that LOC IS shown when -m all is used."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    pass\n")

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "all"])

        assert result.exit_code == 0

        # LOC should appear along with other metrics
        assert "Total LOC" in result.output or "total_loc" in result.output.lower()
        assert "Cyclomat" in result.output or "cyclomat" in result.output.lower()
        assert "Cognitive" in result.output or "cognitive" in result.output.lower()

    def test_multiple_metrics_without_loc(self, temp_project_dir: Path) -> None:
        """Test requesting multiple metrics without LOC."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    if True:\n        return 1\n")

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "cyc", "-m", "cog"])

        assert result.exit_code == 0

        # LOC should NOT appear
        assert "Total LOC" not in result.output
        assert "Avg File LOC" not in result.output

        # But requested metrics should appear
        assert "Cyclomat" in result.output or "cyclomat" in result.output.lower()
        assert "Cognitive" in result.output or "cognitive" in result.output.lower()

    def test_loc_only_when_requested(self, temp_project_dir: Path) -> None:
        """Test that ONLY LOC metrics show when -m loc is used."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    pass\n")

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "loc"])

        assert result.exit_code == 0

        # LOC should appear
        assert "LOC" in result.output or "loc" in result.output.lower()

        # Other metrics should NOT appear unless part of LOC
        if "Cyclomat" in result.output:
            # Only acceptable if it's in a header or description
            assert "Avg Cyclomat" not in result.output

    def test_halstead_without_loc(self, temp_project_dir: Path) -> None:
        """Test Halstead metrics without LOC."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create test files
            cli_dir = Path("cli")
            cli_dir.mkdir()
            (cli_dir / "test.py").write_text("def func():\n    return 1 + 2\n")

            result = runner.invoke(stats, ["-p", "cli/*.py", "-m", "hal"])

        assert result.exit_code == 0

        # LOC should NOT appear
        assert "Total LOC" not in result.output
        assert "Avg File LOC" not in result.output

        # Halstead metrics should appear
        assert "Halstead" in result.output or "halstead" in result.output.lower()
