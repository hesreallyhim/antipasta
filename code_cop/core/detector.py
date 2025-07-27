"""Language detection and file filtering."""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from pathlib import Path

import pathspec


class Language(str, Enum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    UNKNOWN = "unknown"


# Extension to language mapping
EXTENSION_MAP = {
    ".py": Language.PYTHON,
    ".pyw": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".ipynb": Language.PYTHON,  # Jupyter notebooks
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".mts": Language.TYPESCRIPT,
    ".cts": Language.TYPESCRIPT,
}


class LanguageDetector:
    """Detects programming language from file paths and respects .gitignore."""

    def __init__(self, ignore_patterns: list[str] | None = None) -> None:
        """Initialize the detector with optional ignore patterns.

        Args:
            ignore_patterns: List of gitignore-style patterns to exclude files
        """
        self.ignore_patterns = ignore_patterns or []
        self._pathspec: pathspec.PathSpec | None = None
        self._gitignore_patterns: list[str] = []  # Track patterns from .gitignore

    @property
    def pathspec(self) -> pathspec.PathSpec:
        """Get or create the pathspec instance."""
        if self._pathspec is None:
            all_patterns = self.ignore_patterns + self._gitignore_patterns
            self._pathspec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)
        return self._pathspec

    def add_gitignore(self, gitignore_path: Path) -> None:
        """Add patterns from a .gitignore file.

        Args:
            gitignore_path: Path to .gitignore file
        """
        if gitignore_path.exists():
            with open(gitignore_path) as f:
                patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                self._gitignore_patterns.extend(patterns)
                self._pathspec = None  # Reset to rebuild with new patterns

    def detect_language(self, file_path: Path) -> Language | None:
        """Detect the language of a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            Language enum or None if file should be ignored
        """
        # Check if file should be ignored
        if self.should_ignore(file_path):
            return None

        # Get file extension
        extension = file_path.suffix.lower()
        return EXTENSION_MAP.get(extension, Language.UNKNOWN)

    def should_ignore(self, file_path: Path) -> bool:
        """Check if a file should be ignored based on patterns.

        Args:
            file_path: Path to check

        Returns:
            True if file should be ignored
        """
        if not self.ignore_patterns and not self._gitignore_patterns:
            return False

        # Convert to string for matching
        if file_path.is_absolute():
            try:
                # Try to get relative path from current directory
                relative_path = file_path.relative_to(Path.cwd())
                path_str = str(relative_path)
            except ValueError:
                # Path is outside current directory
                # Only apply non-gitignore patterns to files outside the project
                if self.ignore_patterns:
                    spec = pathspec.PathSpec.from_lines("gitwildmatch", self.ignore_patterns)
                    # Use just the filename for matching outside project files
                    return spec.match_file(file_path.name)
                return False
        else:
            # Already relative, use as is
            path_str = str(file_path)

        return self.pathspec.match_file(path_str)

    def group_by_language(self, file_paths: list[Path]) -> dict[Language, list[Path]]:
        """Group files by their detected language.

        Args:
            file_paths: List of file paths to group

        Returns:
            Dictionary mapping languages to lists of file paths
        """
        groups: dict[Language, list[Path]] = defaultdict(list)

        for file_path in file_paths:
            language = self.detect_language(file_path)
            if language is not None and language != Language.UNKNOWN:
                groups[language].append(file_path)

        return dict(groups)

    def filter_files(self, file_paths: list[Path], language: Language) -> list[Path]:
        """Filter files by a specific language.

        Args:
            file_paths: List of file paths to filter
            language: Language to filter by

        Returns:
            List of file paths for the specified language
        """
        return [path for path in file_paths if self.detect_language(path) == language]
