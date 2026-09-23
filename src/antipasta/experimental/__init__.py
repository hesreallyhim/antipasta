"""Experimental metrics: opinionated, opt-in, never part of a default run.

Everything under this package measures conformance to a deliberate style
rather than a defect most reviewers would flag. The metrics are computed
only when the configuration's ``experimental`` block (or the
``--experimental`` flag) enables them, every row they emit carries
``details.experimental = true``, and no preset turns them on. See
``docs/experimental_metrics.md`` for what each feature is trying to measure
and why it is held apart from the core metrics.
"""
