"""Table format display for antipasta configuration."""

from collections.abc import Callable

import click

from antipasta.core.config import AntipastaConfig, LanguageConfig

# Table formatting constants
_TABLE_WIDTH = 60


def echo_box(box: Callable[[str, str], str], content: tuple[str, str]) -> None:
    """Echo a line of the box."""
    border, text = content
    click.echo(box(border, text))


def _create_box_renderer(width: int) -> Callable[[str, str], str]:
    """Create a box rendering function with fixed width."""

    def box(border: str, text: str = "") -> str:
        if text:
            return "║" + text.ljust(width) + "║"
        return border[0] + border[1] * width + border[2]

    return box


def _render_table_header(box: Callable[[str, str], str], width: int) -> None:
    """Render the table header section."""
    echo_box(box, ("╔═╗", ""))
    echo_box(box, ("", " ANTIPASTA CONFIGURATION ".center(width)))
    echo_box(box, ("╠═╣", ""))


def _render_thresholds_section(box: Callable[[str, str], str], config: AntipastaConfig) -> None:
    """Render the thresholds section of the table."""
    echo_box(box, ("", " DEFAULT THRESHOLDS"))
    echo_box(box, ("╟─╢", ""))

    for key, value in config.defaults.model_dump().items():
        display_key = key.replace("_", " ").title()
        op = ">=" if key.startswith("min_") else "<="
        echo_box(box, ("", f"  {display_key:<35} {op} {value:>10.1f}"))


def _render_languages_section(
    box: Callable[[str, str], str], languages: list[LanguageConfig]
) -> None:
    """Render the languages section if languages are configured."""
    if not languages:
        return

    echo_box(box, ("╟─╢", ""))
    echo_box(box, ("", " LANGUAGES"))
    echo_box(box, ("╟─╢", ""))

    for lang in languages:
        text = f"  {lang.name}: {len(lang.metrics)} metrics, {len(lang.extensions)} extensions"
        echo_box(box, ("", text))


def _truncate_text(text: str, max_width: int) -> str:
    """Truncate text if it exceeds max width."""
    if len(text) <= max_width:
        return text
    return text[: max_width - 3] + "..."


def _render_ignore_patterns_section(
    box: Callable[[str, str], str], patterns: list[str], width: int
) -> None:
    """Render the ignore patterns section if patterns are configured."""
    if not patterns:
        return

    echo_box(box, ("╟─╢", ""))
    echo_box(box, ("", f" IGNORE PATTERNS ({len(patterns)})"))
    echo_box(box, ("╟─╢", ""))

    # Display first 5 patterns
    display_limit = 5
    for pattern in patterns[:display_limit]:
        text = _truncate_text(f"  {pattern}", width)
        echo_box(box, ("", text))

    # Show count of remaining patterns
    remaining = len(patterns) - display_limit
    if remaining > 0:
        echo_box(box, ("", f"  ... and {remaining} more"))


def display_table(config: AntipastaConfig) -> None:
    """Display configuration in table format."""
    width = _TABLE_WIDTH
    box = _create_box_renderer(width)

    _render_table_header(box, width)
    _render_thresholds_section(box, config)
    _render_languages_section(box, config.languages)
    _render_ignore_patterns_section(box, config.ignore_patterns, width)

    echo_box(box, ("╚═╝", ""))
