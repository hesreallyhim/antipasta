import re
from pathlib import Path

# Remaining test files with mypy errors
test_files = [
    "tests/unit/cli/test_config_view.py",
]

for file_path in test_files:
    path = Path(file_path)
    if not path.exists():
        print(f"Skipping {file_path} (not found)")
        continue

    content = path.read_text()

    # Pattern to match test functions without return type annotation
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

# Now fix the specific issue in test_stats.py - missing type annotation for temp_project_dir parameter
stats_file = Path("tests/unit/cli/test_stats.py")
if stats_file.exists():
    content = stats_file.read_text()
    # Fix the specific line with missing parameter type annotation
    content = content.replace(
        "def test_negative_depth(self, temp_project_dir) -> None:",
        "def test_negative_depth(self, temp_project_dir: Path) -> None:"
    )
    stats_file.write_text(content)
    print(f"Fixed parameter annotation in tests/unit/cli/test_stats.py")
