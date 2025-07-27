"""Terminal UI command for code-cop."""

import sys
from pathlib import Path
from typing import Optional

import click

from code_cop.terminal import TerminalDashboard


@click.command()
@click.option(
    "--path", "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Path to the project to analyze",
)
@click.option(
    "--watch", "-w",
    is_flag=True,
    help="Enable file watching for live updates",
)
@click.option(
    "--theme",
    type=click.Choice(["default", "dark", "light", "solarized"], case_sensitive=False),
    default="default",
    help="Color theme for the dashboard",
)
@click.option(
    "--no-unicode",
    is_flag=True,
    help="Disable Unicode characters (use ASCII only)",
)
def tui(
    path: Path,
    watch: bool,
    theme: str,
    no_unicode: bool,
) -> None:
    """Launch the terminal UI dashboard for code quality visualization.

    This provides an interactive terminal interface to explore code metrics,
    view complexity heatmaps, and analyze trends in your codebase.

    Examples:
        code-cop tui
        code-cop tui --path ./src
        code-cop tui --watch --theme solarized
    """
    try:
        # TODO: Pass additional options to dashboard (watch, theme, no_unicode)
        app = TerminalDashboard(project_path=str(path))
        app.run()
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error launching terminal dashboard: {e}", err=True)
        sys.exit(1)