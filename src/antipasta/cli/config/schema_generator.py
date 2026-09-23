"""Generate JSON schema from Pydantic models."""

import json
from pathlib import Path
from typing import Any

from antipasta.core.model.config import AntipastaConfig

PACKAGE_SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "metrics-config.schema.json"


def generate_config_schema(output_path: Path | None = None) -> dict[str, Any]:
    """Generate JSON schema for the configuration."""
    schema = AntipastaConfig.model_json_schema()

    # A file can inherit the remaining language fields from lower config layers.
    schema["$defs"]["LanguageConfig"]["required"] = ["name"]
    schema["properties"]["projects"] = {
        "type": "object",
        "description": "User-only partial configurations keyed by absolute repository path",
        "additionalProperties": {
            "type": "object",
            "properties": dict(schema["properties"]),
        },
    }

    # Add some additional metadata
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["title"] = "Antipasta Configuration Schema"
    schema["description"] = "Schema for .antipasta.yaml configuration files"

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)
            f.write("\n")

    return schema


if __name__ == "__main__":
    # Generate the schema file when run as a script
    generate_config_schema(PACKAGE_SCHEMA_PATH)
    print(f"Schema generated at: {PACKAGE_SCHEMA_PATH}")
