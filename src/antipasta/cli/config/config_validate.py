"""Configuration validation command."""

from pathlib import Path
import sys

import click
from pydantic import ValidationError

from antipasta.core.config import AntipastaConfig


@click.command()
@click.argument(
    "config_file",
    type=click.Path(exists=True, path_type=Path),
    default=".antipasta.yaml",
    required=False,
)
def validate(config_file: Path) -> None:
    """Validate an antipasta configuration file.

    CONFIG_FILE defaults to .antipasta.yaml if not specified.

    Exits with code 0 if valid, 1 if invalid.
    """
    try:
        config = AntipastaConfig.from_yaml(config_file)
        click.echo(f"✅ Configuration file is valid: {config_file}")

        # Print summary
        click.echo("\nConfiguration summary:")
        click.echo(f"  Languages: {len(config.languages)}")
        for lang in config.languages:
            click.echo(f"    - {lang.name}: {len(lang.metrics)} metrics")
        click.echo(f"  Ignore patterns: {len(config.ignore_patterns)}")

        sys.exit(0)
    except ValidationError as e:
        click.echo(f"❌ Configuration validation failed: {config_file}", err=True)
        click.echo("\nValidation errors:", err=True)
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            click.echo(f"  - {loc}: {error['msg']}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error loading configuration: {e}", err=True)
        sys.exit(1)
