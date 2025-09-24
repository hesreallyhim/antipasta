"""Tests for temporary file handling in detector.

This test was created to debug and verify the fix for an issue where
temporary test files (e.g., in /tmp or pytest's tmp_path) were being
incorrectly ignored by the language detector.

The issue occurred because:
1. Temporary files have paths outside the project directory
2. The detector's should_ignore() method was using absolute paths for matching
3. Ignore patterns like 'tmp/' were matching against paths containing '/tmp/'

The fix ensures that only the filename is used for pattern matching when
the file is outside the project directory.
"""

from pathlib import Path
import tempfile

from antipasta.core.aggregator import MetricAggregator
from antipasta.core.config import AntipastaConfig
from antipasta.core.detector import Language, LanguageDetector


class TestTempFileHandling:
    """Tests for handling files in temporary directories."""

    def test_temp_files_not_ignored(self) -> None:
        """Test that files in system temp directories are not incorrectly ignored."""
        # Create a file in the system temp directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test.py"
            file_path.write_text("def hello(): pass")

            detector = LanguageDetector()

            # File should not be ignored just because it's in /tmp
            assert not detector.should_ignore(file_path)

            # Language should be detected correctly
            assert detector.detect_language(file_path) == Language.PYTHON

    def test_pytest_tmp_path_files_analyzed(self, tmp_path: Path) -> None:
        """Test that files in pytest's tmp_path are analyzed correctly."""
        # Create a Python file in pytest's temp directory
        file_path = tmp_path / "simple.py"
        file_path.write_text(
            """
def hello():
    print("Hello, World!")
"""
        )

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        # File should be detected and analyzed
        reports = aggregator.analyze_files([file_path])

        assert len(reports) == 1
        assert reports[0].language == "python"
        assert len(reports[0].metrics) > 0

    def test_relative_path_patterns_still_work(self) -> None:
        """Test that ignore patterns still work for files within the project."""
        # This test ensures our fix didn't break normal ignore pattern functionality
        detector = LanguageDetector(ignore_patterns=["tests/**"])

        # A file in the tests directory should be ignored
        test_file = Path("tests/test_something.py")

        # The file should be ignored based on the pattern
        assert detector.should_ignore(test_file)

    def test_debug_output(self, tmp_path: Path) -> None:
        """Test that demonstrates the fix with debug output.

        This test replicates the original debug script to show how
        temporary files are now properly handled.
        """
        file_path = tmp_path / "example.py"
        file_path.write_text(
            """
def hello():
    return "Hello from temp file!"
"""
        )

        config = AntipastaConfig.generate_default()
        aggregator = MetricAggregator(config)

        # Verify file detection
        lang = aggregator.detector.detect_language(file_path)
        assert lang == Language.PYTHON

        # Verify file grouping
        files_by_language = aggregator.detector.group_by_language([file_path])
        assert Language.PYTHON in files_by_language
        assert file_path in files_by_language[Language.PYTHON]

        # Verify runner availability
        runners = aggregator.runners.get(Language.PYTHON)
        assert runners is not None
        assert len(runners) > 0
        assert all(runner.is_available() for runner in runners)

        # Verify analysis works
        reports = aggregator.analyze_files([file_path])
        assert len(reports) == 1

        report = reports[0]
        assert report.file_path == file_path
        assert report.language == "python"
        assert len(report.metrics) > 0
        assert not report.has_violations  # Simple function should pass
