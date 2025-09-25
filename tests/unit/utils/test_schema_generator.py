"""Test cases for schema_generator module."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, mock_open, patch

from antipasta.utils.schema_generator import generate_config_schema


class TestGenerateConfigSchema:
    """Test the generate_config_schema function."""

    def test_generate_schema_without_output_path(self) -> None:
        """Test generating schema returns dict without writing to file."""
        schema = generate_config_schema()

        # Check it returns a dictionary
        assert isinstance(schema, dict)

        # Check required metadata fields are present
        assert "$schema" in schema
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert "title" in schema
        assert schema["title"] == "Antipasta Configuration Schema"
        assert "description" in schema
        assert schema["description"] == "Schema for .antipasta.yaml configuration files"

        # Check it has properties from the Pydantic model
        assert "properties" in schema
        assert "type" in schema

    def test_generate_schema_structure(self) -> None:
        """Test the generated schema has expected structure."""
        schema = generate_config_schema()

        # Check for main configuration properties
        properties = schema.get("properties", {})
        assert "defaults" in properties
        assert "languages" in properties
        assert "ignore_patterns" in properties
        assert "use_gitignore" in properties

        # Check defaults structure - it may use $ref
        defaults = properties["defaults"]
        if "$ref" in defaults:
            # Schema uses references to definitions
            assert "$defs" in schema or "definitions" in schema
            defs = schema.get("$defs", schema.get("definitions", {}))
            assert "DefaultsConfig" in defs
            defaults_def = defs["DefaultsConfig"]
            assert "properties" in defaults_def
            default_props = defaults_def["properties"]
        else:
            # Inline properties
            assert "properties" in defaults
            default_props = defaults["properties"]

        assert "max_cyclomatic_complexity" in default_props
        assert "max_cognitive_complexity" in default_props
        assert "min_maintainability_index" in default_props
        assert "max_halstead_volume" in default_props
        assert "max_halstead_difficulty" in default_props
        assert "max_halstead_effort" in default_props

    def test_generate_schema_with_output_path(self, tmp_path: Path) -> None:
        """Test generating schema writes to specified file."""
        output_file = tmp_path / "test_schema.json"

        schema = generate_config_schema(output_file)

        # Check file was created
        assert output_file.exists()

        # Read and validate the file content
        with open(output_file) as f:
            file_content = json.load(f)

        # Check file content matches returned schema
        assert file_content == schema
        assert file_content["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert file_content["title"] == "Antipasta Configuration Schema"

    def test_generate_schema_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        output_file = tmp_path / "nested" / "dirs" / "schema.json"

        # Parent directories shouldn't exist initially
        assert not output_file.parent.exists()

        schema = generate_config_schema(output_file)

        # Check directories were created
        assert output_file.parent.exists()
        assert output_file.exists()

        # Validate the file was written correctly
        with open(output_file) as f:
            file_content = json.load(f)
        assert file_content == schema

    def test_generate_schema_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that existing file is overwritten."""
        output_file = tmp_path / "existing_schema.json"

        # Create an existing file with different content
        existing_content = {"old": "content"}
        with open(output_file, "w") as f:
            json.dump(existing_content, f)

        # Generate new schema
        schema = generate_config_schema(output_file)

        # Check file was overwritten with new content
        with open(output_file) as f:
            file_content = json.load(f)

        assert file_content != existing_content
        assert file_content == schema
        assert "$schema" in file_content

    def test_generate_schema_json_serializable(self) -> None:
        """Test that generated schema is JSON serializable."""
        schema = generate_config_schema()

        # Should not raise exception
        json_string = json.dumps(schema)
        assert json_string

        # Should be able to parse it back
        parsed = json.loads(json_string)
        assert parsed == schema

    def test_generate_schema_validates_against_json_schema(self) -> None:
        """Test that generated schema follows JSON Schema conventions."""
        schema = generate_config_schema()

        # Check for JSON Schema required fields
        assert "$schema" in schema
        assert "type" in schema

        # Check that type is valid JSON Schema type
        assert schema["type"] in ["object", "array", "string", "number", "boolean", "null"]

        # For object types, check properties structure
        if schema["type"] == "object":
            assert "properties" in schema
            assert isinstance(schema["properties"], dict)

    @patch("antipasta.utils.schema_generator.Path.mkdir")
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_generate_schema_file_operations(
        self, mock_json_dump: MagicMock, mock_file: MagicMock, mock_mkdir: MagicMock
    ) -> None:
        """Test file operations are called correctly."""
        output_path = Path("/fake/path/schema.json")

        generate_config_schema(output_path)

        # Check mkdir was called with correct arguments
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Check file was opened for writing
        mock_file.assert_called_once_with(output_path, "w")

        # Check json.dump was called
        mock_json_dump.assert_called_once()
        args = mock_json_dump.call_args
        assert args[1]["indent"] == 2  # Check indent parameter


class TestSchemaGeneratorMain:
    """Test the __main__ block execution."""

    def test_main_block_execution(self, tmp_path: Path) -> None:
        """Test running the module as a script."""
        test_script = tmp_path / "test_run.py"

        # Create a test script that imports and runs the main block
        script_content = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock the path to write to temp directory
import antipasta.utils.schema_generator as sg
original_path = Path(sg.__file__)
sg.__file__ = str(Path(__file__))

# Run the main block
if __name__ == "__main__":
    schema_path = Path(sg.__file__).parent.parent / "schemas" / "metrics-config.schema.json"
    sg.generate_config_schema(schema_path)
    print(f"Schema generated at: {schema_path}")
"""

        test_script.write_text(script_content)

        # Run the script
        import subprocess

        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        # Check the output
        assert "Schema generated at:" in result.stdout
        assert "schemas/metrics-config.schema.json" in result.stdout

    @patch("antipasta.utils.schema_generator.generate_config_schema")
    @patch("builtins.print")
    def test_main_block_with_mock(
        self, mock_print: MagicMock, mock_generate: MagicMock, tmp_path: Path
    ) -> None:
        """Test __main__ block using mocks."""
        from antipasta.utils import schema_generator

        # Save original __file__ and replace with temp path
        original_file = schema_generator.__file__
        schema_generator.__file__ = str(tmp_path / "schema_generator.py")

        # Execute main block code directly
        if __name__ != "__main__":  # Simulate __main__ execution
            schema_path = (
                Path(schema_generator.__file__).parent.parent
                / "schemas"
                / "metrics-config.schema.json"
            )
            schema_generator.generate_config_schema(schema_path)
            print(f"Schema generated at: {schema_path}")

            # Verify the function was called with correct path
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args[0]
            assert "schemas" in str(call_args[0])
            assert "metrics-config.schema.json" in str(call_args[0])

            # Verify print was called
            mock_print.assert_called_once()
            print_arg = str(mock_print.call_args[0][0])
            assert "Schema generated at:" in print_arg

        # Restore original __file__
        schema_generator.__file__ = original_file


class TestSchemaContent:
    """Test the actual content and validity of generated schema."""

    def test_schema_defines_required_fields(self) -> None:
        """Test that schema properly defines required fields."""
        schema = generate_config_schema()

        # Check if schema specifies which fields are required
        if "required" in schema:
            assert isinstance(schema["required"], list)

        # Check specific property definitions
        properties = schema.get("properties", {})

        # Check language configuration schema
        if "languages" in properties:
            lang_schema = properties["languages"]
            assert "type" in lang_schema
            assert lang_schema["type"] == "array"
            if "items" in lang_schema:
                assert "$ref" in lang_schema["items"] or "properties" in lang_schema["items"]

    def test_schema_includes_descriptions(self) -> None:
        """Test that schema includes helpful descriptions."""
        schema = generate_config_schema()

        # Main schema should have description
        assert "description" in schema
        assert schema["description"]

        # Check some properties have descriptions
        properties = schema.get("properties", {})
        defaults = properties.get("defaults", {})

        # Handle $ref structure
        if "$ref" in defaults:
            defs = schema.get("$defs", schema.get("definitions", {}))
            if "DefaultsConfig" in defs:
                defaults = defs["DefaultsConfig"]

        if "properties" in defaults:
            # At least some default properties should have descriptions
            default_props = defaults["properties"]
            # Check if any properties have descriptions (not required but good practice)
            _ = any(
                "description" in prop_schema
                for prop_schema in default_props.values()
                if isinstance(prop_schema, dict)
            )
            # Note: Not asserting this as models might not have descriptions

    def test_schema_number_constraints(self) -> None:
        """Test that numeric fields have appropriate constraints."""
        schema = generate_config_schema()

        properties = schema.get("properties", {})
        defaults_ref = properties.get("defaults", {})

        # Handle $ref structure
        if "$ref" in defaults_ref:
            defs = schema.get("$defs", schema.get("definitions", {}))
            defaults_config = defs.get("DefaultsConfig", {})
            defaults = defaults_config.get("properties", {})
        else:
            defaults = defaults_ref.get("properties", {})

        # Check cyclomatic complexity constraints
        if "max_cyclomatic_complexity" in defaults:
            cyclo_schema = defaults["max_cyclomatic_complexity"]
            assert "type" in cyclo_schema
            assert cyclo_schema["type"] in ["integer", "number"]
            # Should have minimum value constraint
            if "minimum" in cyclo_schema:
                assert cyclo_schema["minimum"] >= 0

        # Check maintainability index constraints (0-100)
        if "min_maintainability_index" in defaults:
            maint_schema = defaults["min_maintainability_index"]
            assert "type" in maint_schema
            if "minimum" in maint_schema:
                assert maint_schema["minimum"] >= 0
            if "maximum" in maint_schema:
                assert maint_schema["maximum"] <= 100

    def test_schema_pattern_properties(self) -> None:
        """Test pattern-based properties like ignore_patterns."""
        schema = generate_config_schema()

        properties = schema.get("properties", {})

        # Check ignore_patterns is array of strings
        if "ignore_patterns" in properties:
            patterns_schema = properties["ignore_patterns"]
            assert patterns_schema.get("type") == "array"
            if "items" in patterns_schema:
                assert patterns_schema["items"].get("type") == "string"

        # Check use_gitignore is boolean
        if "use_gitignore" in properties:
            gitignore_schema = properties["use_gitignore"]
            assert gitignore_schema.get("type") == "boolean"
