"""Tests for language detection and file filtering."""

from pathlib import Path

from antipasta.core.detector import Language, LanguageDetector


class TestLanguageDetector:
    """Tests for LanguageDetector class."""

    def test_detect_python_files(self) -> None:
        """Test detection of Python files."""
        detector = LanguageDetector()

        assert detector.detect_language(Path("script.py")) == Language.PYTHON
        assert detector.detect_language(Path("gui.pyw")) == Language.PYTHON
        assert detector.detect_language(Path("types.pyi")) == Language.PYTHON
        assert detector.detect_language(Path("notebook.ipynb")) == Language.PYTHON

    def test_detect_javascript_files(self) -> None:
        """Test detection of JavaScript files."""
        detector = LanguageDetector()

        assert detector.detect_language(Path("script.js")) == Language.JAVASCRIPT
        assert detector.detect_language(Path("module.mjs")) == Language.JAVASCRIPT
        assert detector.detect_language(Path("common.cjs")) == Language.JAVASCRIPT
        assert detector.detect_language(Path("component.jsx")) == Language.JAVASCRIPT

    def test_detect_typescript_files(self) -> None:
        """Test detection of TypeScript files."""
        detector = LanguageDetector()

        assert detector.detect_language(Path("app.ts")) == Language.TYPESCRIPT
        assert detector.detect_language(Path("component.tsx")) == Language.TYPESCRIPT
        assert detector.detect_language(Path("module.mts")) == Language.TYPESCRIPT
        assert detector.detect_language(Path("common.cts")) == Language.TYPESCRIPT

    def test_detect_unknown_files(self) -> None:
        """Test detection of unknown file types."""
        detector = LanguageDetector()

        assert detector.detect_language(Path("readme.md")) == Language.UNKNOWN
        assert detector.detect_language(Path("config.yaml")) == Language.UNKNOWN
        assert detector.detect_language(Path("data.json")) == Language.UNKNOWN

    def test_case_insensitive_extensions(self) -> None:
        """Test that extension detection is case-insensitive."""
        detector = LanguageDetector()

        assert detector.detect_language(Path("SCRIPT.PY")) == Language.PYTHON
        assert detector.detect_language(Path("App.TS")) == Language.TYPESCRIPT
        assert detector.detect_language(Path("Component.JSX")) == Language.JAVASCRIPT

    def test_ignore_patterns(self) -> None:
        """Test that files matching ignore patterns return None."""
        detector = LanguageDetector(ignore_patterns=["*.test.py", "tests/**", "__pycache__/**"])

        # These should be ignored
        assert detector.detect_language(Path("file.test.py")) is None
        assert detector.detect_language(Path("tests/test_something.py")) is None
        assert detector.detect_language(Path("__pycache__/module.py")) is None

        # These should not be ignored
        assert detector.detect_language(Path("main.py")) == Language.PYTHON
        assert detector.detect_language(Path("src/module.py")) == Language.PYTHON

    def test_group_by_language(self) -> None:
        """Test grouping files by language."""
        detector = LanguageDetector()
        files = [
            Path("main.py"),
            Path("utils.py"),
            Path("app.js"),
            Path("index.tsx"),
            Path("types.ts"),
            Path("readme.md"),
            Path("test.java"),
        ]

        groups = detector.group_by_language(files)

        assert len(groups) == 3
        assert set(groups[Language.PYTHON]) == {Path("main.py"), Path("utils.py")}
        assert set(groups[Language.JAVASCRIPT]) == {Path("app.js")}
        assert set(groups[Language.TYPESCRIPT]) == {Path("index.tsx"), Path("types.ts")}
        assert Language.UNKNOWN not in groups  # Unknown files are excluded

    def test_group_by_language_with_ignores(self) -> None:
        """Test grouping with some files ignored."""
        detector = LanguageDetector(ignore_patterns=["test_*.py", "*.spec.js"])
        files = [
            Path("main.py"),
            Path("test_main.py"),  # Should be ignored
            Path("app.js"),
            Path("app.spec.js"),  # Should be ignored
            Path("types.ts"),
        ]

        groups = detector.group_by_language(files)

        assert len(groups) == 3
        assert groups[Language.PYTHON] == [Path("main.py")]
        assert groups[Language.JAVASCRIPT] == [Path("app.js")]
        assert groups[Language.TYPESCRIPT] == [Path("types.ts")]

    def test_filter_files(self) -> None:
        """Test filtering files by language."""
        detector = LanguageDetector()
        files = [
            Path("main.py"),
            Path("utils.py"),
            Path("app.js"),
            Path("index.tsx"),
            Path("readme.md"),
        ]

        python_files = detector.filter_files(files, Language.PYTHON)
        assert set(python_files) == {Path("main.py"), Path("utils.py")}

        js_files = detector.filter_files(files, Language.JAVASCRIPT)
        assert js_files == [Path("app.js")]

        ts_files = detector.filter_files(files, Language.TYPESCRIPT)
        assert ts_files == [Path("index.tsx")]

    def test_add_gitignore(self, tmp_path: Path) -> None:
        """Test adding patterns from a .gitignore file."""
        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            """
# Python
__pycache__/
*.pyc
.pytest_cache/

# Node
node_modules/
*.log
"""
        )

        detector = LanguageDetector()
        detector.add_gitignore(gitignore)

        # Test that patterns from .gitignore are respected
        assert detector.should_ignore(Path("__pycache__/file.py"))
        assert detector.should_ignore(Path("module.pyc"))
        assert detector.should_ignore(Path(".pytest_cache/data"))
        assert detector.should_ignore(Path("node_modules/package/index.js"))
        assert detector.should_ignore(Path("error.log"))

        # These should not be ignored
        assert not detector.should_ignore(Path("main.py"))
        assert not detector.should_ignore(Path("src/app.js"))

    def test_should_ignore_relative_paths(self) -> None:
        """Test that should_ignore works with relative paths."""
        detector = LanguageDetector(ignore_patterns=["build/**", "*.tmp"])

        assert detector.should_ignore(Path("build/output.js"))
        assert detector.should_ignore(Path("build/dist/app.py"))
        assert detector.should_ignore(Path("temp.tmp"))
        assert not detector.should_ignore(Path("src/main.py"))

    def test_empty_patterns_ignores_nothing(self) -> None:
        """Test that empty ignore patterns don't filter anything."""
        detector = LanguageDetector(ignore_patterns=[])

        assert not detector.should_ignore(Path("any/file.py"))
        assert not detector.should_ignore(Path("test.js"))
        assert detector.detect_language(Path("main.py")) == Language.PYTHON
