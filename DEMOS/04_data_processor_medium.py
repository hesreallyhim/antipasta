"""Demo 4: Data Processor - Medium Complexity

Metrics:
- Cyclomatic Complexity: 5-8 (moderate)
- Cognitive Complexity: 4-6
- Maintainability Index: ~65
- Halstead Volume: Moderate-High

This shows realistic business logic with moderate complexity.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class DataProcessor:
    """Process data from various sources with validation and transformation."""

    def __init__(self, validate_strict: bool = True):
        self.validate_strict = validate_strict
        self.errors: list[str] = []
        self.processed_count = 0

    def process_file(self, file_path: str | Path) -> dict[str, Any]:
        """Process a data file based on its extension."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extension = path.suffix.lower()

        if extension == ".json":
            return self._process_json(path)
        if extension == ".csv":
            return self._process_csv(path)
        if extension in [".txt", ".log"]:
            return self._process_text(path)
        raise ValueError(f"Unsupported file type: {extension}")

    def _process_json(self, path: Path) -> dict[str, Any]:
        """Process JSON file with validation."""
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {path}: {e}")
            return {"error": "Invalid JSON", "details": str(e)}

        if isinstance(data, dict):
            return self._transform_dict_data(data)
        if isinstance(data, list):
            results = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    results.append(self._transform_dict_data(item))
                else:
                    self.errors.append(f"Item {i} is not a dictionary")
            return {"items": results, "count": len(results)}
        return {"raw_data": data}

    def _process_csv(self, path: Path) -> dict[str, Any]:
        """Process CSV file with data type inference."""
        records = []

        with open(path, newline="") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, 1):
                try:
                    processed_row = self._process_csv_row(row, row_num)
                    if processed_row:
                        records.append(processed_row)
                        self.processed_count += 1
                except Exception as e:
                    self.errors.append(f"Error in row {row_num}: {e}")
                    if self.validate_strict:
                        raise

        return {
            "records": records,
            "total_rows": row_num,
            "processed": self.processed_count,
            "errors": len(self.errors),
        }

    def _process_csv_row(self, row: dict[str, str], row_num: int) -> dict[str, Any] | None:
        """Process and validate a single CSV row."""
        processed = {}

        for key, value in row.items():
            if not value:  # Handle empty values
                processed[key] = None
                continue

            # Try to infer data type
            if value.isdigit():
                processed[key] = int(value)
            elif value.replace(".", "", 1).isdigit():
                processed[key] = float(value)
            elif value.lower() in ["true", "false"]:
                processed[key] = value.lower() == "true"
            elif self._is_date(value):
                processed[key] = self._parse_date(value)
            else:
                processed[key] = value.strip()

        # Validate required fields
        if self.validate_strict and not processed.get("id"):
            self.errors.append(f"Row {row_num} missing required field: id")
            return None

        return processed

    def _process_text(self, path: Path) -> dict[str, Any]:
        """Process text file with pattern extraction."""
        patterns_found = {
            "errors": [],
            "warnings": [],
            "info": [],
            "timestamps": [],
        }

        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                if "ERROR" in line or "CRITICAL" in line:
                    patterns_found["errors"].append(
                        {
                            "line": line_num,
                            "content": line[:100],  # Truncate long lines
                        }
                    )
                elif "WARNING" in line or "WARN" in line:
                    patterns_found["warnings"].append({"line": line_num, "content": line[:100]})
                elif "INFO" in line:
                    patterns_found["info"].append({"line": line_num, "content": line[:100]})

                # Extract timestamps
                if self._extract_timestamp(line):
                    patterns_found["timestamps"].append(self._extract_timestamp(line))

        return {
            "file": str(path),
            "lines_processed": line_num,
            "patterns": patterns_found,
            "summary": {
                "errors": len(patterns_found["errors"]),
                "warnings": len(patterns_found["warnings"]),
                "info": len(patterns_found["info"]),
            },
        }

    def _transform_dict_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform dictionary data with nested handling."""
        transformed = {}

        for key, value in data.items():
            # Normalize keys
            clean_key = key.lower().replace(" ", "_").replace("-", "_")

            if isinstance(value, dict):
                transformed[clean_key] = self._transform_dict_data(value)
            elif isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    transformed[clean_key] = [self._transform_dict_data(item) for item in value]
                else:
                    transformed[clean_key] = value
            elif isinstance(value, str):
                # Clean string values
                transformed[clean_key] = value.strip()
            else:
                transformed[clean_key] = value

        return transformed

    def _is_date(self, value: str) -> bool:
        """Check if string looks like a date."""
        date_patterns = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]

        for pattern in date_patterns:
            try:
                datetime.strptime(value, pattern)
                return True
            except ValueError:
                continue

        return False

    def _parse_date(self, value: str) -> str | None:
        """Parse date string to ISO format."""
        date_patterns = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]

        for pattern in date_patterns:
            try:
                dt = datetime.strptime(value, pattern)
                return dt.isoformat()
            except ValueError:
                continue

        return None

    def _extract_timestamp(self, line: str) -> str | None:
        """Extract timestamp from log line."""
        # Simple pattern matching for ISO-like timestamps
        import re

        patterns = [
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
            r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",
        ]

        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group()

        return None

    def get_report(self) -> dict[str, Any]:
        """Get processing report."""
        return {
            "processed_count": self.processed_count,
            "error_count": len(self.errors),
            "errors": self.errors[-10:] if self.errors else [],  # Last 10 errors
            "validation_mode": "strict" if self.validate_strict else "lenient",
        }
