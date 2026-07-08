# Supported Metrics Reference

This reference is based on the current implementation for the upcoming v2
release. The authoritative code paths are:

- `src/antipasta/core/model/metrics.py` for the complete `MetricType` enum.
- `src/antipasta/runners/` for per-file runner output.
- `src/antipasta/core/derive/` for project-scope derived metrics.
- `src/antipasta/core/mining/` for VCS and coverage-artifact analytics.
- `src/antipasta/core/model/config.py` and `src/antipasta/schemas/metrics-config.schema.json` for defaults and schema coverage.

The table below treats "supported" as "the current library code has a producer
for this metric row." Producers include language runners, project-level
derivers, the VCS miner, the coverage-matrix loader, and snapshot-based joins.
Some producers need context beyond source files: duplication needs a
`duplication` config block, layering needs a configured layer order, VCS metrics
need git history, coverage metrics need a coverage.py dynamic-context artifact,
and hotspots need a prior report snapshot.

The "What it measures" column is the metric definition. The "Supported
languages" column is only about the languages the library can report on;
`Any` means the metric is language-agnostic. The "Default / threshold behavior"
column is only about
configuration thresholds; absence of a built-in threshold does not mean the
metric is unsupported. Runtime inputs or producer context, such as git history,
report snapshots, configured layers, or coverage.py artifacts, are listed
separately in "Additional inputs / context."

## Metric List

| Metric | Category | Scope | Value range | Default / threshold behavior in current code | Supported languages | Additional inputs / context | Source | What it measures |
|---|---|---:|---|---|---|---|---|---|
| `cyclomatic_complexity` | Complexity | Function and file | `>= 1` when emitted | Default threshold `<= 10` | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Independent control-flow paths through functions. |
| `maintainability_index` | Mixed | File | `0..100` | Default threshold `>= 50` in generated Python config | Python | None | Radon | Composite maintainability score from complexity, size, and Halstead data. |
| `halstead_volume` | Complexity | File and function | `>= 0` | Default threshold `<= 1000` for file-level rows | Python | None | Radon | Halstead program volume derived from operator and operand vocabulary. |
| `halstead_difficulty` | Complexity | File and function | `>= 0` | Default threshold `<= 10` for file-level rows | Python | None | Radon | Halstead estimate of how hard the code is to understand or write. |
| `halstead_effort` | Complexity | File and function | `>= 0` | Default threshold `<= 10000` for file-level rows | Python | None | Radon | Halstead mental-effort estimate. |
| `halstead_time` | Complexity | File and function | `>= 0` seconds | No built-in default threshold | Python | None | Radon | Halstead implementation-time estimate. |
| `halstead_bugs` | Complexity | File and function | `>= 0` | No built-in default threshold | Python | None | Radon | Halstead estimated delivered defects. |
| `cognitive_complexity` | Readability | Function and file | `>= 0` | Threshold default `<= 15`; generated Python default metric row is disabled | Python | None | Complexipy | Human-comprehension complexity, especially nesting and flow disruption. |
| `lines_of_code` | Lines of code | File | `>= 0` | No built-in default threshold | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Physical line count. |
| `logical_lines_of_code` | Lines of code | File | `>= 0` | No built-in default threshold | Python | None | Radon | Logical statement count. |
| `source_lines_of_code` | Lines of code | File | `>= 0` | No built-in default threshold | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Non-blank, non-comment source line count. |
| `comment_lines` | Lines of code | File | `>= 0` | No built-in default threshold | Python | None | Radon | Comment line count. |
| `blank_lines` | Lines of code | File | `>= 0` | No built-in default threshold | Python | None | Radon | Blank line count. |
| `message_chain_depth` | Readability | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Deepest attribute/call chain in the function. |
| `function_arity` | Readability | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Number of function parameters after excluding `self` or `cls` for methods. |
| `boolean_flag_parameters` | Readability | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Positional parameters that look like boolean mode flags. |
| `exception_discipline` | Readability | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Bare, broad-without-reraise, or silent exception handlers. |
| `global_state_reach` | Readability | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Distinct mutable module-level names touched by a function. |
| `marker_density` | Readability | File | `>= 0` per 1000 lines | No built-in default threshold | Python | None | Custom | TODO/FIXME/HACK/XXX marker density. |
| `comment_density` | Readability | File | `0..100` percent | No built-in default threshold | Python | None | Custom | Percentage of physical lines that are comments. |
| `function_statements` | Complexity | Function | `>= 0` | No built-in default threshold | Python | None | Custom | Count of statements owned by the function, excluding nested scopes. |
| `expression_flatness` | Readability | Function | `0..1` | No built-in default threshold | Python | None | Custom | Share of statements that stay within the one-idea operation budget. |
| `pipeline_linearity` | Readability | Function | `0..1` | No built-in default threshold | Python | None | Custom | Share of assigned local names written once and read once. |
| `lack_of_cohesion` | SOLID | Class | `>= 0` | No built-in default threshold | Python | None | Custom | Number of disconnected method/field/call components in a class. |
| `weighted_methods_per_class` | SOLID | Class | `>= 0` | No built-in default threshold | Python | None | Custom, Radon-derived | Sum of member method cyclomatic complexity for a class. |
| `coupling_between_objects` | SOLID | Class | `>= 0` | No built-in default threshold | Python | None | Custom | Distinct imported names referenced from a class body. |
| `depth_of_inheritance_tree` | SOLID | Class | `>= 1` | No built-in default threshold | Python | None | Custom | Inheritance depth after resolving known project bases. |
| `number_of_children` | SOLID | Class | `>= 0` | No built-in default threshold | Python | None | Custom | Number of known immediate subclasses. |
| `single_responsibility_index` | Mixed | Class | `>= 1` | No built-in default threshold | Python | None | Custom | Composite responsibility pressure from cohesion, method weight, and class statement count. |
| `directory_children` | SOLID | Directory | `>= 0` | No default threshold unless `tree_shape` config exists; then defaults are non-root `>= 2` and all dirs `<= 7` | Python, JS/TS | None | Custom | Immediate module/subdirectory fan-out for analyzed directories. |
| `efferent_coupling` | SOLID | Module/package | `>= 0` | No built-in default threshold | Python | None | Custom | Number of analyzed modules/packages this module/package imports. |
| `afferent_coupling` | SOLID | Module/package | `>= 0` | No built-in default threshold | Python | None | Custom | Number of analyzed modules/packages importing this module/package. |
| `instability` | SOLID | Module | `0..1` | No built-in default threshold | Python | None | Custom | Efferent coupling divided by total afferent plus efferent coupling. |
| `dependency_cycles` | SOLID | Cycle | `>= 2` when emitted | No default threshold unless `import_graph` config exists; then `forbid_cycles` defaults true and requires zero cycles | Python | None | Custom | Strongly connected import-cycle member count. |
| `stable_dependencies_violations` | SOLID | Module | `>= 0` | No default threshold unless `import_graph` config exists; then default threshold is `<= 0` | Python | None | Custom | Imports pointing toward materially less stable modules. |
| `abstractness` | SOLID | Module | `0..1` | No built-in default threshold | Python | None | Custom | Ratio of abstract classes to total classes in a module. |
| `distance_from_main_sequence` | SOLID | Module | `0..1` | No built-in default threshold | Python | None | Custom | Absolute distance from Martin's main sequence, `abs(A + I - 1)`. |
| `dependency_inversion` | SOLID | Module | `0..1` when emitted | No built-in default threshold | Python | None | Custom | Mean abstractness of imported project targets. |
| `narrative_mixed_functions` | Readability | Module | `>= 0` | No default threshold unless `narrative` config exists; then threshold is `<= 0` offenders | Python | None | Custom | Count of functions that both narrate through project calls and compute raw details. |
| `narrator_budget_exceeded` | Readability | Module | `>= 0` | No default threshold unless `narrative` config exists; computation uses default narrator budget `9`, then threshold is `<= 0` offenders | Python | None | Custom | Count of narrator functions exceeding the step budget. |
| `computer_budget_exceeded` | Readability | Module | `>= 0` | No default threshold unless `narrative` config exists; computation uses default budgets `8` statements and nesting `1`, then threshold is `<= 0` offenders | Python | None | Custom | Count of leaf/computer functions exceeding statement or nesting budgets. |
| `step_down_ordering` | Readability | Module | `0..1` | No built-in default threshold | Python | None | Custom | Share of intra-module calls whose callee is defined below the caller. |
| `layering_violations` | SOLID | Module | `>= 0` | No default threshold because no layer order exists by default; if `tree_shape.layers` is configured, threshold is `<= 0` upward imports | Python | `tree_shape.layers` config | Custom | Imports from a configured lower layer back upward into an earlier layer. |
| `name_clarity` | Readability | Module | `0..1` | No default threshold; if `narrative.name_clarity_floor` is set, threshold is `>=` that configured value | Python | None | Custom | Mean lexical clarity of callable names against the layered vocabulary. |
| `naming_antipatterns` | Readability | Module | `>= 0` | No default threshold unless `narrative` config exists; then threshold is `<= 0` offenders | Python | None | Custom | Count of naming/behavior contradictions such as lying predicates or two-job names. |
| `duplication_ratio` | DRYness | File | `0..1` | No default threshold; if `duplication.max_ratio` is set, threshold is `<=` that configured value | Python | `duplication` config block | pydry plus custom | Per-file duplicated-line ratio from pydry clone groups. |
| `clone_occurrences` | DRYness | Clone group | `>= 0` | No built-in default threshold | Python | `duplication` config block | pydry plus custom | Number of occurrences in an exact structural clone group. |
| `assertions_per_test` | Test quality | Test function | `>= 0` | No built-in default threshold | Python | Test-looking file path and test function name | Custom | Plain assertions plus mock-style assertion calls per test. |
| `mock_call_assertions` | Test quality | Test function | `>= 0` | No built-in default threshold | Python | Test-looking file path and test function name | Custom | Mock call-count or call-argument assertion calls per test. |
| `big_literal_assertions` | Test quality | Test function | `>= 0` | No built-in default threshold | Python | Test-looking file path and test function name | Custom | Assertions involving large inline literal structures. |
| `code_churn` | VCS | File | `>= 0` | No built-in default threshold | Any | Git history | git plus custom | Lines added plus deleted over the mined history window. |
| `change_coupling` | VCS | File pair | `>= 3` when emitted | No built-in default threshold | Any | Git history | git plus custom | Number of commits in which a file pair changed together. |
| `hotspot` | Mixed | File | `>= 0` | No built-in default threshold | Any | Git history and report snapshot with complexity for the file | git plus custom | Code churn multiplied by worst cyclomatic complexity from a snapshot. |
| `test_churn_ratio` | Test quality | Suite | `>= 0` | No built-in default threshold | Any | Git history and test path conventions | git plus custom | Test lines changed divided by source lines changed. |
| `co_churn_multiplicity` | Test quality | Suite | `>= 0` | No built-in default threshold | Any | Git history and test path conventions | git plus custom | Median number of test files touched in source-touching commits. |
| `suite_redundancy_index` | Test quality | Coverage artifact | `0..1` | No built-in default threshold | Python coverage data | coverage.py dynamic-context artifact | coverage.py artifact plus custom | Share of tests that the greedy line-coverage cover can omit. |
| `blast_radius` | Test quality | Covered file | `>= 0` | No built-in default threshold | Python coverage data | coverage.py dynamic-context artifact | coverage.py artifact plus custom | Number of distinct tests executing a file. |

## Custom Metric Computation Notes

- `message_chain_depth`: walks each function AST and reports the deepest attribute/call chain, with the first `self`, `cls`, or `super` hop discounted.
- `function_arity`: counts positional, keyword-only, `*args`, and `**kwargs` parameters, excluding leading `self` or `cls` on methods.
- `boolean_flag_parameters`: counts positional parameters annotated as `bool` or defaulted to a boolean value; keyword-only booleans are exempt.
- `exception_discipline`: counts bare handlers, silent handlers, and broad `Exception`/`BaseException` handlers that do not reraise.
- `global_state_reach`: finds module-level mutable-style names and counts how many distinct such names a function reads or declares global.
- `marker_density`: tokenizes comments, counts TODO/FIXME/HACK/XXX markers, and normalizes by physical lines per thousand.
- `comment_density`: tokenizes comments and reports comment lines divided by total physical lines as a percentage.
- `function_statements`: counts statements owned by a function while descending into control-flow blocks but excluding nested function/class scopes.
- `expression_flatness`: scores each owned statement by operation weight and reports the fraction at or below the one-idea budget.
- `pipeline_linearity`: counts local names assigned exactly once and loaded exactly once, divided by all assigned local names.
- `lack_of_cohesion`: builds connected components over methods, connecting methods that share fields or call one another; the component count is the value.
- `weighted_methods_per_class`: sums Radon per-method cyclomatic complexity rows by owning class.
- `coupling_between_objects`: counts distinct imported names referenced inside a class body; rows are approximate.
- `depth_of_inheritance_tree`: resolves project-local base classes from extracted class/import facts and reports maximum depth, treating unresolved external parents as one extra level.
- `number_of_children`: reverses the resolved inheritance edges and counts immediate project-local subclasses.
- `single_responsibility_index`: computes `cohesion_components * (1 + weighted_methods / 30) * (1 + statements / 60)` and rounds to two decimals.
- `directory_children`: counts immediate analyzed module files plus immediate subdirectories for each analyzed directory, excluding plumbing files such as `__init__.py`.
- `efferent_coupling`: counts resolved outgoing import edges from a module or collapsed package.
- `afferent_coupling`: counts incoming resolved import edges to a module or collapsed package.
- `instability`: computes `Ce / (Ca + Ce)`, or `0` when both coupling counts are zero.
- `dependency_cycles`: runs Tarjan strongly connected components over the resolved import graph and emits components with at least two modules.
- `stable_dependencies_violations`: counts outgoing edges where target instability exceeds source instability by more than the fixed `0.2` tolerance.
- `abstractness`: counts abstract classes detected from ABC/Protocol bases, ABCMeta metaclasses, or abstractmethod decorators divided by total classes in the module.
- `distance_from_main_sequence`: computes `abs(abstractness + instability - 1)` for modules that have abstractness rows.
- `dependency_inversion`: averages the abstractness of imported target modules, treating classless targets as concrete.
- `narrative_mixed_functions`: classifies callable facts and counts functions with both project-level narrative calls and raw computation beyond the profile tolerance.
- `narrator_budget_exceeded`: counts narrator functions whose statement count exceeds the configured narrator step budget.
- `computer_budget_exceeded`: counts computer/leaf functions whose statement count or nesting exceeds configured budgets.
- `step_down_ordering`: counts intra-module calls and reports the fraction where the callee appears later in the same module.
- `layering_violations`: compares resolved import edges to configured layer order and counts imports from lower layers back into earlier layers.
- `name_clarity`: splits callable names into words, scores them against the built-in/project/user vocabulary, and averages non-dunder callable scores per module.
- `naming_antipatterns`: counts callable names with positive-evidence contradictions such as `is_*` returning non-bool, `get_*` returning no value, or `_and_` two-job names.
- `duplication_ratio`: asks pydry for exact structural clone groups, sums duplicated spans per file, divides by that file's SLOC, and caps at `1.0`.
- `clone_occurrences`: reports pydry exact clone group occurrence counts.
- `assertions_per_test`: in test-looking files, counts `assert` statements and mock-style assertion calls per test function.
- `mock_call_assertions`: in test-looking files, counts mock assertion calls such as `assert_called*`, `assert_awaited*`, and `assert_has_calls`.
- `big_literal_assertions`: in test-looking files, counts assertions whose expression contains dict/list/set/tuple literals of at least eight entries.
- `code_churn`: mines `git log --numstat --no-merges` for the selected window and sums added plus deleted lines per file.
- `change_coupling`: counts co-commit pairs and reports pairs meeting the fixed support floor of three commits.
- `hotspot`: joins mined churn to worst per-file cyclomatic complexity from a saved report snapshot and multiplies them.
- `test_churn_ratio`: divides mined test-file churn by mined source-file churn for the selected history window.
- `co_churn_multiplicity`: records test files touched in each source-touching commit and reports their median.
- `suite_redundancy_index`: loads coverage.py dynamic contexts, greedily selects tests covering all observed lines, and computes `1 - cover_size / test_count`.
- `blast_radius`: loads coverage.py dynamic contexts and counts distinct tests that cover any line in each file.

## Schema Comparison

- `metrics-config.schema.json` currently matches the code enum exactly: 57 metric
  values, no missing values, no extras, and the same order as `MetricType`.
- The committed schema also matches `AntipastaConfig.model_json_schema()` as
  generated by `src/antipasta/cli/config/schema_generator.py`.
- The schema exposes all 57 metric values through `MetricConfig.type`, but
  `MetricConfig.threshold` is only a generic number in the schema; runtime
  validation rejects negative thresholds, and metric-specific ranges are not
  encoded there.
- Only six global default fields carry schema ranges/defaults:
  `max_cyclomatic_complexity` (`1..50`, default `10`),
  `max_cognitive_complexity` (`1..100`, default `15`),
  `min_maintainability_index` (`0..100`, default `50`),
  `max_halstead_volume` (`0..100000`, default `1000`),
  `max_halstead_difficulty` (`0..100`, default `10`), and
  `max_halstead_effort` (`0..1000000`, default `10000`).
- The schema allows any metric enum value inside any language config, but the
  runners do not emit every metric for every language; for example, JS/TS emit
  cyclomatic complexity, LOC, and SLOC only.
- Several supported metrics are project-, VCS-, or artifact-scoped and are not
  meaningfully thresholded through `languages[].metrics`; project metrics use
  optional config blocks such as `tree_shape`, `import_graph`, `narrative`, and
  `duplication`, while VCS and coverage metrics depend on provider inputs rather
  than language config.
- `LanguageConfig.name` is a free string in the schema, while the current
  detector only recognizes Python, JavaScript, and TypeScript extensions.
- The schema does not set `additionalProperties: false`; unknown object fields
  may therefore be schema-valid even when runtime Pydantic models would ignore
  or reject them depending on model behavior.

## Visible Documentation Drift To Fix Later

This section ignores `INTERNAL/` planning notes and only calls out visible docs
or config-generation artifacts.

- `README.md` states Halstead prompt ranges as volume `1..100000`, difficulty
  `0.1..100`, and effort `1..1000000`, while the schema/code default fields
  allow `0` for all three.
- `README.md`'s example config shows cognitive complexity as an enabled metric
  row, while `AntipastaConfig.generate_default()` creates the Python cognitive
  metric with `enabled=false`.
- `src/antipasta/cli/config/config_generate/language_config.py` still prints
  JavaScript/TypeScript as "coming soon" in the interactive flow, although the
  current runner path supports lightweight JS/TS analysis through lizard.
- The same config-generation helper's dormant `create_javascript_config()` lists
  cognitive complexity for JS/TS, but the lizard runner emits only cyclomatic
  complexity, LOC, and SLOC.
- `docs/statistics_feature.md` lists only six "Available metrics"; the stats
  parser accepts any `MetricType` name and an `all` prefix, though project-scope
  metrics still only appear where the stats path consumes their rows.
- `DEMOS/README.md` uses a cognitive complexity default of `10`, while the code
  and main README use `15`.
