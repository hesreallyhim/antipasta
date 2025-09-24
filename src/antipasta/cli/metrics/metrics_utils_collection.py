"""File collection helper functions for metrics command."""

from pathlib import Path

from antipasta.core.config import AntipastaConfig
from antipasta.core.config_override import ConfigOverride
from antipasta.core.detector import LanguageDetector


def collect_files(
    files: tuple[Path, ...],
    directory: Path | None,
    config: AntipastaConfig,
    override: ConfigOverride | None,
) -> list[Path]:
    """Collect all files to analyze, respecting gitignore patterns and overrides."""
    base_dir = directory or Path.cwd()
    detector = _create_language_detector(config, override, base_dir)
    _load_gitignore_if_enabled(config, base_dir, detector)

    file_paths = list(files)

    if directory:
        file_paths.extend(_collect_directory_files(directory, detector))

    # Remove duplicates
    return list(set(file_paths))


def _create_language_detector(
    config: AntipastaConfig, override: ConfigOverride | None, base_dir: Path
) -> LanguageDetector:
    """Create a language detector with appropriate patterns."""
    include_patterns = []
    if override and override.include_patterns:
        include_patterns = override.include_patterns

    return LanguageDetector(
        ignore_patterns=config.ignore_patterns,
        include_patterns=include_patterns,
        base_dir=base_dir,
    )


def _load_gitignore_if_enabled(
    config: AntipastaConfig, base_dir: Path, detector: LanguageDetector
) -> None:
    """Load .gitignore file if enabled in configuration."""
    if not config.use_gitignore:
        return

    gitignore_path = base_dir / ".gitignore"
    if gitignore_path.exists():
        detector.add_gitignore(gitignore_path)


def _collect_directory_files(directory: Path, detector: LanguageDetector) -> list[Path]:
    """Collect all supported files from a directory."""
    patterns = ["**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"]
    collected_files = []

    for pattern in patterns:
        for file_path in directory.glob(pattern):
            if not detector.should_ignore(file_path):
                collected_files.append(file_path)

    return collected_files
