"""Tests for the Narrative Index deriver (adoption plan, Phase 4)."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.config import AntipastaConfig, NarrativeConfig
from antipasta.core.derivation import DerivationInput
from antipasta.core.narrative import _ambient_names, classify, derive_narrative
from antipasta.core.violations import ProjectReport
from antipasta.runners.python.house_style import HouseStyleRunner

PROSE_MODULE = """\
def publish(directory):
    users = fetch_users(directory)
    active_users = keep_active(users)
    return render(active_users)


def fetch_users(directory):
    return list(directory)


def keep_active(users):
    active = [user for user in users if user]
    count = len(active)
    return active[:count]


def render(users):
    return len(users)
"""

MIXED_MODULE = """\
def publish(directory):
    users = fetch_users(directory)
    active = [u for u in users if u.get("status") == "active"]
    return len(active) > 3


def fetch_users(directory):
    return list(directory)
"""


def _derive(
    root: Path, sources: dict[str, str], config: AntipastaConfig | None = None
) -> list[ProjectReport]:
    runner = HouseStyleRunner()
    facts_by_file = {
        root / rel: runner.analyze(root / rel, content=src).facts
        for rel, src in sources.items()
    }
    return derive_narrative(
        DerivationInput(
            file_reports=[],
            facts_by_file=facts_by_file,
            root=root,
            config=config or AntipastaConfig(),
        )
    )


def _rows(reports: list[ProjectReport], subject: str) -> dict[str, float]:
    report = next(r for r in reports if r.subject == subject)
    return {m.metric_type.value: m.value for m in report.metrics}


class TestClassification:
    SYMBOLS = frozenset({"fetch_users", "keep_active", "render", "publish"})

    def _payload(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "name": "fn",
            "statements": 4,
            "computation_weight": 0,
            "call_names": [],
        }
        base.update(overrides)
        return base

    def test_narrator(self) -> None:
        payload = self._payload(call_names=["fetch_users", "render"])
        assert classify(payload, self.SYMBOLS, frozenset()) == "narrator"

    def test_computer(self) -> None:
        payload = self._payload(computation_weight=6)
        assert classify(payload, self.SYMBOLS, frozenset()) == "computer"

    def test_mixed(self) -> None:
        payload = self._payload(call_names=["fetch_users"], computation_weight=4)
        assert classify(payload, self.SYMBOLS, frozenset()) == "mixed"

    def test_trivial(self) -> None:
        payload = self._payload(statements=2, call_names=["fetch_users"])
        assert classify(payload, self.SYMBOLS, frozenset()) == "trivial"

    def test_ambient_calls_do_not_make_a_narrator(self) -> None:
        payload = self._payload(call_names=["log"], computation_weight=2)
        assert classify(payload, self.SYMBOLS | {"log"}, frozenset({"log"})) == "computer"

    def test_mixing_tolerance_dial(self) -> None:
        # standard profile tolerates a couple of prose-grade operations.
        payload = self._payload(call_names=["fetch_users"], computation_weight=4)
        assert classify(payload, self.SYMBOLS, frozenset(), mixing_tolerance=0) == "mixed"
        assert classify(payload, self.SYMBOLS, frozenset(), mixing_tolerance=4) == "narrator"

    def test_self_recursion_is_not_narrative(self) -> None:
        payload = self._payload(name="walk", call_names=["walk"], computation_weight=2)
        assert classify(payload, self.SYMBOLS | {"walk"}, frozenset()) == "computer"


class TestModuleReports:
    def test_prose_module_is_clean(self, tmp_path: Path) -> None:
        reports = _derive(tmp_path, {"prose.py": PROSE_MODULE})

        rows = _rows(reports, "prose")
        assert rows["narrative_mixed_functions"] == 0.0
        assert rows["narrator_budget_exceeded"] == 0.0
        assert rows["computer_budget_exceeded"] == 0.0
        # publish calls three helpers all defined below it: perfect step-down.
        assert rows["step_down_ordering"] == 1.0

    def test_mixed_function_counted(self, tmp_path: Path) -> None:
        reports = _derive(tmp_path, {"half.py": MIXED_MODULE})

        rows = _rows(reports, "half")
        assert rows["narrative_mixed_functions"] == 1.0
        report = next(r for r in reports if r.subject == "half")
        mixed_row = next(
            m for m in report.metrics
            if m.metric_type.value == "narrative_mixed_functions"
        )
        assert (mixed_row.details or {})["functions"] == ["publish"]

    def test_run_on_narrator_flagged(self, tmp_path: Path) -> None:
        steps = "\n".join(
            f"    v{i} = step_{i}(v{i - 1})" for i in range(1, 13)
        )
        helpers = "\n\n".join(
            f"def step_{i}(x):\n    return x" for i in range(1, 13)
        )
        source = f"def run_on(v0):\n{steps}\n    return v12\n\n\n{helpers}\n"
        reports = _derive(tmp_path, {"long.py": source})

        rows = _rows(reports, "long")
        assert rows["narrator_budget_exceeded"] == 1.0

    def test_oversized_computer_flagged(self, tmp_path: Path) -> None:
        body = "\n".join(f"    x{i} = {i} * {i}" for i in range(12))
        source = f"def grind():\n{body}\n    return x11\n"
        reports = _derive(tmp_path, {"leaf.py": source})

        rows = _rows(reports, "leaf")
        assert rows["computer_budget_exceeded"] == 1.0

    def test_reversed_definition_order_lowers_step_down(self, tmp_path: Path) -> None:
        source = (
            "def helper(x):\n    return x\n\n\n"
            "def caller(v):\n    a = helper(v)\n    b = helper(a)\n    return b\n"
        )
        reports = _derive(tmp_path, {"upside.py": source})

        assert _rows(reports, "upside")["step_down_ordering"] == 0.0

    def test_violations_only_with_config(self, tmp_path: Path) -> None:
        informational = _derive(tmp_path, {"half.py": MIXED_MODULE})
        assert not any(r.has_violations for r in informational)

        gated = _derive(
            tmp_path,
            {"half.py": MIXED_MODULE},
            AntipastaConfig(narrative=NarrativeConfig()),
        )
        half = next(r for r in gated if r.subject == "half")
        assert half.has_violations


class TestAmbientDetection:
    def test_widely_called_name_is_ambient(self) -> None:
        payloads = [
            {"name": f"fn_{i}", "call_names": ["log"], "statements": 3}
            for i in range(10)
        ]
        ambient = _ambient_names({"m": payloads})

        assert "log" in ambient

    def test_rarely_called_name_is_not(self) -> None:
        payloads = [
            {"name": f"fn_{i}", "call_names": ["log"] if i < 2 else [], "statements": 3}
            for i in range(30)
        ]
        ambient = _ambient_names({"m": payloads})

        assert "log" not in ambient
