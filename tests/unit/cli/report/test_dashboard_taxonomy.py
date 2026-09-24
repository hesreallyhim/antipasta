"""The dashboard's metric buckets must match the documented taxonomy.

report.js keeps its own copy of the Category column from
docs/supported_metrics.md (an installed wheel has no docs checkout and the
report must work offline). table_policy.py is tested against the docs; this
test closes the loop by parsing the JavaScript literals and comparing them
with table_policy, so neither copy can drift without failing a test.
"""

from __future__ import annotations

from importlib import resources
import re

from antipasta.cli.report.table_policy import CATEGORIES, METRIC_CATEGORIES


def _report_js() -> str:
    return (resources.files("antipasta.report") / "assets" / "report.js").read_text("utf-8")


def _literal_block(source: str, name: str) -> str:
    match = re.search(rf"const {name} = (?:\{{|\[)(.*?)\n  (?:\}}|\]);", source, re.DOTALL)
    assert match, f"{name} literal not found in report.js"
    return match.group(1)


def _dashboard_buckets() -> dict[str, str]:
    """Bucket id -> display name, from the CATS literal."""
    block = _literal_block(_report_js(), "CATS")
    return dict(re.findall(r'id: "([a-z]+)", name: "([^"]+)"', block))


def _dashboard_metric_categories() -> dict[str, str]:
    """Metric -> documented category name, from the METRIC_CAT literal."""
    buckets = _dashboard_buckets()
    block = _literal_block(_report_js(), "METRIC_CAT")
    return {metric: buckets[bucket] for metric, bucket in re.findall(r"(\w+): \"([a-z]+)\"", block)}


def test_dashboard_buckets_are_the_documented_categories() -> None:
    assert tuple(_dashboard_buckets().values()) == CATEGORIES


def test_dashboard_metric_buckets_match_the_terminal_taxonomy() -> None:
    assert _dashboard_metric_categories() == METRIC_CATEGORIES
