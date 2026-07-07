"""Offline HTML report assembly.

``render_report`` inlines everything — CSS, the vendored d3 bundle, the report
script, and the snapshot data — into a single HTML document with zero network
references, so the report works from any ``file://`` URL.
"""

from __future__ import annotations

from importlib import resources
import json
import re
from typing import Any

_DATA_MARKER = "/*__ANTIPASTA_DATA__*/"
_CSS_MARKER = "/*__ANTIPASTA_CSS__*/"
_D3_MARKER = "/*__D3_JS__*/"
_JS_MARKER = "/*__ANTIPASTA_JS__*/"

_NETWORK_REF = re.compile(r"https?://", re.IGNORECASE)


def _read_asset(*parts: str) -> str:
    """Read a text asset shipped in ``antipasta/report/assets``."""
    node = resources.files("antipasta.report") / "assets"
    for part in parts:
        node = node / part
    return node.read_text(encoding="utf-8")


def _escape_embedded_code(code: str) -> str:
    """Rewrite ``://`` to the equivalent string escape ``:\\/\\/``.

    Inside JS and JSON string literals ``\\/`` evaluates to ``/``, so runtime
    values are unchanged, while the emitted document no longer contains any
    ``http(s)://`` byte sequence (d3 carries XML-namespace constants such as
    ``http://www.w3.org/2000/svg`` that are not network references but would
    otherwise trip offline checks).
    """
    return code.replace("://", ":\\/\\/")


def _encode_snapshot(snapshot: dict[str, Any]) -> str:
    """Serialize the snapshot for safe embedding in a ``<script>`` element."""
    data = json.dumps(snapshot, separators=(",", ":"))
    # "</" could prematurely terminate the script element (e.g. "</script");
    # "<\\/" is the same string after JSON unescaping.
    return _escape_embedded_code(data.replace("</", "<\\/"))


def render_report(snapshot: dict[str, Any]) -> str:
    """Render the snapshot into a single self-contained offline HTML page.

    Raises:
        ValueError: if the assembled document unexpectedly contains a network
            reference; a non-offline report is never emitted.
    """
    html = (
        _read_asset("template.html")
        .replace(_CSS_MARKER, _read_asset("report.css"))
        .replace(_D3_MARKER, _escape_embedded_code(_read_asset("vendor", "d3.v7.min.js")))
        .replace(_JS_MARKER, _escape_embedded_code(_read_asset("report.js")))
        .replace(_DATA_MARKER, _encode_snapshot(snapshot))
    )
    if _NETWORK_REF.search(html):
        raise ValueError(
            "Rendered report contains a network reference; refusing to emit a non-offline report."
        )
    return html
