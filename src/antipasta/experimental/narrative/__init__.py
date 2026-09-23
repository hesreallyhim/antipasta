"""The Narrative Index: does code read like prose?

An opinionated model of function-level readability built around one style:
functions either narrate (a sequence of named steps) or compute (a small
leaf), names carry meaning, and modules read top to bottom. It comprises the
mixed-altitude classification with its narrator and computer budgets,
step-down ordering, expression flatness, pipeline linearity, and lexicon-based
name clarity.

Held as experimental because the style it measures is uncommon in practice:
benchmarked against the standard library and widely used packages, most
substantive functions classify as mixed and the name-clarity ranking is led
by lexicon gaps rather than unclear names. The rules are kept whole rather
than watered down; a project that adopts the style deliberately can enable
them with ``experimental: {narrative: {}}``.
"""

from antipasta.experimental.narrative.deriver import derive_narrative

__all__ = ["derive_narrative"]
