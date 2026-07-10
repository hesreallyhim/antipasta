# Project-Defined Metrics Refactoring Demo

This demo is a set of static-analysis snapshots for the metrics described in `docs/project_defined_metrics.md`.

The source snapshots intentionally start with a module that has many local problems at once. Each later file is a copy of the previous idea with one metric family refactored toward a cleaner shape. It's worth noting that the final iteration is about twice the number of LoC as the first one - this points to an inherent tension that exists between certain classes of metrics. Understandably, code that is more readable frequently ends up being longer than code that optimizes for other things.

## Caveat

The final snapshot is intentionally best read as "passes this teaching config," not as "ideal code." In particular, some small helpers are thin wrappers that pydry's near-similarity model can identify as likely over-extraction. That tension is part of the point of this demo: metrics can reveal pressure, but they do not replace judgment about whether an abstraction earns its name.

## Source Snapshot Sequence

| Snapshot | Main refactoring focus |
|---|---|
| `source_snapshots/01_everything_tangled.py` | Baseline with dense expressions, mutable globals, mixed abstraction, poor names, deep chains, broad exceptions, large comment debt, and a many-purpose class. |
| `source_snapshots/02_flatten_expressions.py` | Names intermediate expression steps to improve `expression_flatness`. |
| `source_snapshots/03_linearize_pipeline.py` | Turns repeated scratch mutation into a clearer data pipeline for `pipeline_linearity`. |
| `source_snapshots/04_control_hidden_state_and_exceptions.py` | Passes state explicitly and handles narrow exceptions to reduce `global_state_reach` and `exception_discipline`. |
| `source_snapshots/05_separate_narrative_layers.py` | Separates orchestration from leaf computation for `narrative_mixed_functions`, narrator budget, and computer budget. |
| `source_snapshots/06_step_down_names_and_chains.py` | Reorders helpers below callers, improves names, fixes naming antipatterns, and replaces reach-through chains. |
| `source_snapshots/07_split_responsibilities.py` | Splits the many-purpose class to reduce `lack_of_cohesion`, `coupling_between_objects`, and `single_responsibility_index`. |
| `source_snapshots/08_clean_comments.py` | Removes marker/comment debt to improve `marker_density` and `comment_density`. |

## Test-Smell Companion

The three test-smell metrics are path-gated, so they live in `test_snapshots/`:

| Snapshot | Main refactoring focus |
|---|---|
| `test_snapshots/test_order_report_01_bad.py` | Many assertions, mock call assertions, and a large inline expected literal. |
| `test_snapshots/test_order_report_02_behavior_focused.py` | Fewer contract-level assertions and no mock implementation checks. |

## Running The Demo

Use the demo config when you want the custom metrics with clear pass/fail semantics to produce visible violations:

```bash
venv/bin/antipasta metrics \
  -c DEMOS/PROJECT_DEFINED_METRICS/project_defined_metrics_demo.yaml \
  -f DEMOS/PROJECT_DEFINED_METRICS/source_snapshots/01_everything_tangled.py
```

Compare the final source snapshot:

```bash
venv/bin/antipasta metrics \
  -c DEMOS/PROJECT_DEFINED_METRICS/project_defined_metrics_demo.yaml \
  -f DEMOS/PROJECT_DEFINED_METRICS/source_snapshots/08_clean_comments.py
```

For continuous or informational rows such as `expression_flatness`, `pipeline_linearity`, and `single_responsibility_index`, use JSON output:

```bash
venv/bin/antipasta metrics \
  -c DEMOS/PROJECT_DEFINED_METRICS/project_defined_metrics_demo.yaml \
  -f DEMOS/PROJECT_DEFINED_METRICS/source_snapshots/07_split_responsibilities.py \
  --format json
```

The default project configuration keeps several project-defined metrics informational. This demo config gates the rows with the clearest teaching thresholds while leaving continuous and derived rows visible in JSON.
