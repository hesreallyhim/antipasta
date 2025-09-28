"""Generate JSON schema from Pydantic models."""

import json
from pathlib import Path
from typing import Any

from antipasta.core.config import AntipastaConfig


def generate_config_schema(output_path: Path | None = None) -> dict[str, Any]:
    """Generate JSON schema for the configuration."""
    schema = AntipastaConfig.model_json_schema()

    # Add some additional metadata
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["title"] = "Antipasta Configuration Schema"
    schema["description"] = "Schema for .antipasta.yaml configuration files"

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(schema, f, indent=2)

    return schema


if __name__ == "__main__":
    # Generate the schema file when run as a script
    schema_path = Path(__file__).parent.parent / "schemas" / "metrics-config.schema.json"
    generate_config_schema(schema_path)
    print(f"Schema generated at: {schema_path}")
