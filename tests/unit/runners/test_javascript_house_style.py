"""Unit tests for JavaScript/TypeScript house-style metrics."""

from __future__ import annotations

from pathlib import Path

from antipasta.core.model.metrics import MetricResult, MetricType
from antipasta.runners.javascript.house_style import HouseStyleRunner

TS_SOURCE = """\
import { Helper } from "./helper";
let cache = [];
// TODO: tighten this later
const normalize = () => {
  return cache.length;
};

abstract class Account extends Base {
  constructor(name, active = true) {
    this.name = name;
  }

  save(flag: boolean = false, items = []) {
    if (flag) {
      this.writer.persist(this.name);
    }
    cache.push(items.length);
    return items.map(item => item + 1);
  }
}
"""

TEST_SOURCE = """\
test("renders", () => {
  expect(result).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  expect(save).toHaveBeenCalledWith(1);
});
"""


class TestJavaScriptHouseStyleRunner:
    def test_supported_metrics_include_ported_rows(self) -> None:
        runner = HouseStyleRunner()

        assert MetricType.FUNCTION_ARITY.value in runner.supported_metrics
        assert MetricType.COMMENT_LINES.value in runner.supported_metrics
        assert MetricType.LACK_OF_COHESION.value in runner.supported_metrics

    def test_typescript_functions_classes_and_facts(self) -> None:
        result = HouseStyleRunner().analyze(Path("account.ts"), content=TS_SOURCE)

        assert result.error is None
        assert result.language == "typescript"

        rows = _rows_by_type(result.metrics)
        assert rows[MetricType.COMMENT_LINES][0].value == 1
        assert rows[MetricType.MARKER_DENSITY][0].value > 0

        save_arity = _row_for(rows[MetricType.FUNCTION_ARITY], "save")
        assert save_arity.value == 2
        save_flags = _row_for(rows[MetricType.BOOLEAN_FLAG_PARAMETERS], "save")
        assert save_flags.value == 1
        save_global_reach = _row_for(rows[MetricType.GLOBAL_STATE_REACH], "save")
        assert save_global_reach.value == 1
        save_chain = _row_for(rows[MetricType.MESSAGE_CHAIN_DEPTH], "save")
        assert save_chain.value >= 1

        cohesion = _row_for(rows[MetricType.LACK_OF_COHESION], "Account")
        assert cohesion.value >= 1
        coupling = _row_for(rows[MetricType.COUPLING_BETWEEN_OBJECTS], "Account")
        assert coupling.details == {"approximate": True, "analyzer": "javascript-house-style"}

        import_fact = next(fact for fact in result.facts if fact.kind == "import")
        assert import_fact.payload == {"module": "helper", "names": ["Helper"], "level": 1}

        class_fact = next(fact for fact in result.facts if fact.kind == "class")
        assert class_fact.payload["name"] == "Account"
        assert class_fact.payload["bases"] == ["Base"]
        assert class_fact.payload["decorators"] == ["abstract"]

        callables = [fact.payload for fact in result.facts if fact.kind == "callable"]
        assert any(payload["name"] == "normalize" for payload in callables)
        assert any(
            payload["name"] == "save" and payload["class_name"] == "Account"
            for payload in callables
        )
        assert any(
            payload["name"] == "(anonymous)" and payload["class_name"] is None
            for payload in callables
        )

    def test_javascript_test_smell_rows(self) -> None:
        result = HouseStyleRunner().analyze(Path("widget.test.js"), content=TEST_SOURCE)

        rows = _rows_by_type(result.metrics)
        assert _row_for(rows[MetricType.ASSERTIONS_PER_TEST], "test").value == 2
        assert _row_for(rows[MetricType.MOCK_CALL_ASSERTIONS], "test").value == 1
        assert _row_for(rows[MetricType.BIG_LITERAL_ASSERTIONS], "test").value == 1


def _rows_by_type(metrics: list[MetricResult]) -> dict[MetricType, list[MetricResult]]:
    rows: dict[MetricType, list[MetricResult]] = {}
    for metric in metrics:
        rows.setdefault(metric.metric_type, []).append(metric)
    return rows


def _row_for(metrics: list[MetricResult], function_name: str) -> MetricResult:
    return next(metric for metric in metrics if metric.function_name == function_name)
