#!/usr/bin/env python3
"""
ccguard_metrics.py - A hook script for Claude Code to enforce code quality
using a variety of metrics beyond simple lines-of-code counting.

This script is designed to be invoked as a `PreToolUse` hook in Claude Code.
It reads hook input JSON from stdin and evaluates the proposed file operation
against a set of configurable thresholds.  If the operation increases
complexity metrics beyond the allowed thresholds or drops maintainability
below acceptable levels, the script returns a blocking decision.  Otherwise
it approves the operation.

The script attempts to support both Python and TypeScript/JavaScript files.
For Python files it leverages the open source `radon` library to compute
Cyclomatic Complexity, Maintainability Index, Halstead metrics and raw
metrics.  Radon is widely used for static analysis of Python code and its
documentation describes the definitions of these metrics.
For TypeScript/JavaScript files, where a mature cross-platform library is
not available in this environment, the script falls back to a heuristic
analysis that approximates cyclomatic complexity by counting common control
flow keywords and calculates a basic Halstead volume and difficulty from
tokens.  Maintainability index is then estimated using the standard formula
based on these values.

Configuration
-------------

Thresholds can be adjusted via a JSON configuration file named
`.ccguard.metrics.config.json` located in the project root (as defined by
the `CLAUDE_PROJECT_DIR` environment variable).  If the file is absent
defaults are used.  A typical configuration might look like:

```
{
  "thresholds": {
    "max_cyclomatic_increase": 0,
    "max_halstead_volume_increase": 0,
    "min_maintainability_index": 50.0,
    "max_loc_increase": 0,
    "max_class_count": 5
  }
}
```

The metrics are interpreted as follows:

* **max_cyclomatic_increase** - The maximum allowed increase in total
  cyclomatic complexity between the old and new code for the affected
  fragments.  Cyclomatic complexity counts the number of linearly
  independent execution paths through the code【347414987174434†L36-L52】.
* **max_halstead_volume_increase** - The maximum allowed increase in
  Halstead volume, a measure of algorithmic complexity based on token
  usage【347414987174434†L132-L153】.
* **min_maintainability_index** - The minimum maintainability index after
  the change.  Maintainability index combines Halstead volume, cyclomatic
  complexity and lines of code into a score from 0 to 100; higher is
  better【347414987174434†L63-L99】.
* **max_loc_increase** - The maximum allowed increase in source lines of
  code (SLOC).  This supplements the existing LOC guard and prevents
  operations from adding excessive blank/comment lines.
* **max_class_count** - An optional structural metric limiting the total
  number of class declarations introduced by the edit (across all edits).

Usage
-----

Add this script as a PreToolUse hook for `Write|Edit|MultiEdit` tools in
Claude Code:

```
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
              "type": "command",
              "command": "python3 $CLAUDE_PROJECT_DIR/ccguard_metrics.py"
           }
        ]
      }
    ]
  }
}
```

Ensure that the `radon` Python package is installed in the environment if
you want full Python analysis.  Without radon the script will still run
but will fall back to a heuristic analysis for Python files.
"""

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    # Import radon modules if available
    from radon.complexity import cc_visit  # type: ignore
    from radon.metrics import mi_visit  # type: ignore
    from radon.raw import analyze  # type: ignore
    from radon.metrics import h_visit  # type: ignore

    RADON_AVAILABLE = True
except Exception:
    RADON_AVAILABLE = False


@dataclass
class Metrics:
    cyclomatic: float
    halstead_volume: float
    halstead_difficulty: float
    halstead_effort: float
    maintainability_index: float
    loc: int
    classes: int


def load_config() -> Dict[str, float]:
    """Load metric thresholds from the config file, returning defaults if not found."""
    defaults = {
        "max_cyclomatic_increase": 0.0,
        "max_halstead_volume_increase": 0.0,
        "min_maintainability_index": 50.0,
        "max_loc_increase": 0.0,
        "max_class_count": 9999999.0,
    }
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    config_path = os.path.join(project_dir, ".ccguard.metrics.config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            thresholds = data.get("thresholds", {})
            for key, value in thresholds.items():
                if key in defaults and isinstance(value, (int, float)):
                    defaults[key] = float(value)
        except Exception:
            # Ignore config errors and use defaults
            pass
    return defaults


def detect_language(file_path: Optional[str]) -> str:
    """Infer the language from the file extension."""
    if not file_path:
        return "unknown"
    lower = file_path.lower()
    if lower.endswith(".py"):
        return "python"
    if lower.endswith((".ts", ".tsx")):
        return "typescript"
    if lower.endswith((".js", ".jsx")):
        return "javascript"
    return "unknown"


def radon_metrics(source: str) -> Metrics:
    """Compute metrics for Python code using radon.
    Fall back to heuristics if radon is unavailable."""
    if RADON_AVAILABLE:
        try:
            # Cyclomatic complexity: sum of block complexities
            blocks = cc_visit(source)
            cyclomatic = sum(block.complexity for block in blocks)
            # Maintainability index: radon returns a score per module
            mi_scores = mi_visit(source, multi=True)
            maintainability_index = mi_scores
            # Raw metrics: returns (loc, lloc, sloc, comments, multi, blank,
            # comments percent, comments lines)
            raw = analyze(source)
            loc = raw.loc
            # Halstead metrics: h_visit returns a Halstead namedtuple with total and functions
            halstead_result = h_visit(source)
            # Use the total metrics for the entire file
            total_volume = halstead_result.total.volume
            total_difficulty = halstead_result.total.difficulty
            total_effort = halstead_result.total.effort
            # Structural metrics: count class declarations
            class_count = len(re.findall(r"^\s*class\s+", source, re.MULTILINE))
            return Metrics(
                cyclomatic=float(cyclomatic),
                halstead_volume=float(total_volume),
                halstead_difficulty=float(total_difficulty),
                halstead_effort=float(total_effort),
                maintainability_index=float(maintainability_index),
                loc=int(loc),
                classes=class_count,
            )
        except Exception:
            # If radon raises an error (e.g., syntax error), fall back
            pass
    # Fallback heuristic for Python
    return heuristic_metrics(source)


def heuristic_metrics(source: str) -> Metrics:
    """Approximate metrics for non‑Python languages or when radon is unavailable."""
    lines = [line for line in source.split("\n")
             if line.strip() and not line.strip().startswith("//")]
    loc = len(lines)
    # Approximate cyclomatic complexity: 1 + count of decision points
    cyclomatic = 1.0
    decision_keywords = ["if", "for", "while", "switch", "case", "catch",
                        "&&", "||", "?", "elif", "except"]
    for line in lines:
        # Remove string literals to avoid counting keywords inside strings
        stripped = re.sub(r"(['\"]).*?\1", "", line)
        for kw in decision_keywords:
            cyclomatic += stripped.count(kw)
    # Tokenize for Halstead metrics: split on non‑alphanumeric
    tokens = [tok for tok in re.split(r"[^A-Za-z0-9_]+", source) if tok]
    unique_tokens = set(tokens)
    n1 = len(unique_tokens)
    N1 = len(tokens)
    if n1 > 0:
        halstead_volume = N1 * math.log2(n1)
        halstead_difficulty = (n1 / 2.0) * (N1 / n1)
    else:
        halstead_volume = halstead_difficulty = 0.0
    halstead_effort = halstead_volume * halstead_difficulty
    # Maintainability index (approximate using original formula with natural log)
    # Avoid log(0) by using max()
    MI = (171.0 - 5.2 * math.log(max(halstead_volume, 1e-8))
          - 0.23 * cyclomatic - 16.2 * math.log(max(loc, 1)))
    maintainability_index = max(0.0, 100.0 * MI / 171.0)
    # Structural metric: count classes and extends keywords
    class_count = len(re.findall(r"\bclass\b", source))
    return Metrics(
        cyclomatic=float(cyclomatic),
        halstead_volume=float(halstead_volume),
        halstead_difficulty=float(halstead_difficulty),
        halstead_effort=float(halstead_effort),
        maintainability_index=float(maintainability_index),
        loc=int(loc),
        classes=class_count,
    )


def compute_diff(old: Metrics, new: Metrics) -> Dict[str, float]:
    """Compute differences between new and old metrics."""
    return {
        "cyclomatic": new.cyclomatic - old.cyclomatic,
        "halstead_volume": new.halstead_volume - old.halstead_volume,
        "maintainability_index": new.maintainability_index - old.maintainability_index,
        "loc": new.loc - old.loc,
        "class_count": new.classes - old.classes,
    }


def evaluate_operation(
        tool_name: str,
        tool_input: Dict[str, Any],
        thresholds: Dict[str, float]
     ) -> Tuple[str, str]:
    """
    Evaluate the change implied by an operation and return a (decision, reason)
    tuple.  The decision is either "approve" or "block".

    tool_input is the JSON payload for Edit, MultiEdit, or Write as defined by
    Claude Code.  thresholds holds the configured limits.
    """
    file_path = tool_input.get("file_path")
    language = detect_language(file_path)
    # Helper to compute metrics for a snippet

    def compute_metrics_for_snippet(source: str) -> Metrics:
        if language == "python":
            return radon_metrics(source)
        else:
            return heuristic_metrics(source)

    total_diff = {
        "cyclomatic": 0.0,
        "halstead_volume": 0.0,
        "maintainability_index": 0.0,
        "loc": 0.0,
        "class_count": 0.0,
    }
    # Process according to tool
    if tool_name == "Write":
        content = tool_input.get("content", "") or ""
        new_metrics = compute_metrics_for_snippet(content)
        # Old metrics are zero for new file
        old_metrics = Metrics(0.0, 0.0, 0.0, 0.0, 100.0, 0, 0)
        diff = compute_diff(old_metrics, new_metrics)
        for key in total_diff:
            total_diff[key] += diff[key]
    elif tool_name == "Edit":
        old_src = tool_input.get("old_string", "") or ""
        new_src = tool_input.get("new_string", "") or ""
        old_metrics = compute_metrics_for_snippet(old_src)
        new_metrics = compute_metrics_for_snippet(new_src)
        diff = compute_diff(old_metrics, new_metrics)
        for key in total_diff:
            total_diff[key] += diff[key]
    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        for edit in edits:
            old_src = edit.get("old_string", "") or ""
            new_src = edit.get("new_string", "") or ""
            old_metrics = compute_metrics_for_snippet(old_src)
            new_metrics = compute_metrics_for_snippet(new_src)
            diff = compute_diff(old_metrics, new_metrics)
            for key in total_diff:
                total_diff[key] += diff[key]
    else:
        # Unknown tool - approve by default
        return "approve", "Tool not handled"
    # Evaluate against thresholds
    reasons = []
    decision = "approve"
    # Cyclomatic complexity increase
    if total_diff["cyclomatic"] > thresholds["max_cyclomatic_increase"]:
        decision = "block"
        reasons.append(
            f"Cyclomatic complexity increase {total_diff['cyclomatic']:.2f} "
            f"exceeds allowed {thresholds['max_cyclomatic_increase']}"
        )
    # Halstead volume increase
    if total_diff["halstead_volume"] > (
        thresholds["max_halstead_volume_increase"]
    ):
        decision = "block"
        reasons.append(
            f"Halstead volume increase {total_diff['halstead_volume']:.2f} "
            f"exceeds allowed {thresholds['max_halstead_volume_increase']}"
        )
    # Maintainability index drop
    # (we use negative difference - drop is negative)
    final_mi = None
    # We need the final maintainability index after all edits.
    # For Write or Edit we can compute new_metrics.
    # For MultiEdit we cannot easily know final MI across entire file,
    # so we estimate by applying diffs to baseline 100.
    # In absence of full file context we treat the new MI as 100 + diff.
    final_mi = 100.0 + total_diff["maintainability_index"]
    if final_mi < thresholds["min_maintainability_index"]:
        decision = "block"
        reasons.append(
            f"Maintainability index would be {final_mi:.2f}, "
            f"below minimum {thresholds['min_maintainability_index']}"
        )
    # LOC increase
    if total_diff["loc"] > thresholds["max_loc_increase"]:
        decision = "block"
        reasons.append(
            f"Lines of code increase {total_diff['loc']} "
            f"exceeds allowed {thresholds['max_loc_increase']}"
        )
    # Class count
    if total_diff["class_count"] > thresholds["max_class_count"]:
        decision = "block"
        reasons.append(
            f"Class declarations increase {total_diff['class_count']} "
            f"exceeds allowed {thresholds['max_class_count']}"
        )
    reason = ("Operation approved" if decision == "approve"
              else "Operation blocked: " + "; ".join(reasons))
    # Append summary of diffs
    summary_parts = []
    for k, v in total_diff.items():
        summary_parts.append(f"{k} change={v:+.2f}")
    reason += "\nMetrics delta: " + ", ".join(summary_parts)
    return decision, reason


def main():
    # Read entire stdin
    input_data = sys.stdin.read()
    try:
        hook_data = json.loads(input_data)
    except Exception:
        # If input is not valid JSON, approve by default
        print(json.dumps({"decision": "approve", "reason": "Invalid input"}))
        return
    event = hook_data.get("hook_event_name", "")
    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {}) or {}
    # Only act on PreToolUse events
    if event != "PreToolUse":
        print(json.dumps({"decision": "approve",
                         "reason": "Not a PreToolUse event"}))
        return
    # Load thresholds
    thresholds = load_config()
    decision, reason = evaluate_operation(tool_name, tool_input, thresholds)
    print(json.dumps({"decision": decision, "reason": reason}))


if __name__ == "__main__":
    main()
