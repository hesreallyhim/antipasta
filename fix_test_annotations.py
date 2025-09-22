import re
from pathlib import Path

# List of test files with mypy errors
test_files = [
    "tests/unit/cli/test_validate_config.py",
    "tests/unit/cli/test_ignore_patterns.py",
    "tests/unit/cli/test_generate_config.py",
    "tests/unit/cli/test_metrics.py",
    "tests/unit/cli/test_config.py",
    "tests/unit/cli/test_stats.py",
]

for file_path in test_files:
    path = Path(file_path)
    if not path.exists():
        print(f"Skipping {file_path} (not found)")
        continue

    content = path.read_text()

    # Pattern to match test functions without return type annotation
    # Matches: def test_name(self): or def test_name(self, ...):
    pattern = r'(\s+def test_[^(]+\(self[^)]*\))(\s*:)'

    def replacer(match):
        # Add -> None before the colon
        return match.group(1) + ' -> None' + match.group(2)

    # Apply the replacement
    new_content = re.sub(pattern, replacer, content)

    if new_content != content:
        path.write_text(new_content)
        print(f"Fixed {file_path}")
    else:
        print(f"No changes needed for {file_path}")
