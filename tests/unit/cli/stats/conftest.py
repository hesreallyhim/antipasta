"""Shared fixtures and utilities for stats tests."""

from collections.abc import Generator
from pathlib import Path
import tempfile

import pytest


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory with nested Python files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir) / "test_project"
        base.mkdir()

        # Create a nested directory structure with Python files
        # Root level
        (base / "main.py").write_text("def main():\n    pass\n")
        (base / "utils.py").write_text("def util():\n    return 42\n")

        # Level 1 - cli directory
        cli_dir = base / "cli"
        cli_dir.mkdir()
        (cli_dir / "commands.py").write_text(
            "def cmd():\n    for i in range(10):\n        print(i)\n"
        )
        (cli_dir / "options.py").write_text("OPTIONS = {}\n")

        # Level 1 - core directory
        core_dir = base / "core"
        core_dir.mkdir()
        (core_dir / "engine.py").write_text("class Engine:\n    def run(self):\n        pass\n")
        (core_dir / "config.py").write_text("CONFIG = {'debug': True}\n")

        # Level 2 - cli/subcommands
        sub_dir = cli_dir / "subcommands"
        sub_dir.mkdir()
        (sub_dir / "analyze.py").write_text(
            "def analyze():\n    if True:\n        return 1\n    return 0\n"
        )

        # Level 2 - core/modules
        mod_dir = core_dir / "modules"
        mod_dir.mkdir()
        (mod_dir / "parser.py").write_text("def parse(data):\n    return data\n")

        # Level 3 - deeper nesting
        deep_dir = mod_dir / "validators"
        deep_dir.mkdir()
        (deep_dir / "rules.py").write_text("RULES = []\n")

        # Level 4 - even deeper
        deeper_dir = deep_dir / "builtin"
        deeper_dir.mkdir()
        (deeper_dir / "basic.py").write_text("def validate():\n    pass\n")

        yield base
