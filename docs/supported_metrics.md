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
`Any` means the metric is language-agnostic. The "Default" column is only about
configured comparison values; `None` does not mean the metric is unsupported.
Runtime inputs or producer context, such as git history, report snapshots,
configured layers, or coverage.py artifacts, are listed separately in
"Additional inputs / context."

For expanded descriptions of the project-defined metrics, see [`project_defined_metrics.md`](project_defined_metrics.md).

## Metric List

| Metric | Category | Scope | Value range | Default | Supported languages | Additional inputs / context | Source | What it measures |
|---|---|---:|---|---|---|---|---|---|
| `lines_of_code` | Lines of code | File | `>= 0` | None | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Physical line count. |
| `logical_lines_of_code` | Lines of code | File | `>= 0` | None | Python, JS/TS | None | Radon for Python; lexical JS/TS analyzer | Logical statement count. |
| `source_lines_of_code` | Lines of code | File | `>= 0` | None | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Non-blank, non-comment source line count. |
| `comment_lines` | Lines of code | File | `>= 0` | None | Python, JS/TS | None | Radon for Python; lexical JS/TS analyzer | Comment line count. |
| `blank_lines` | Lines of code | File | `>= 0` | None | Python, JS/TS | None | Radon for Python; lexical JS/TS analyzer | Blank line count. |
| `cyclomatic_complexity` | Complexity | Function and file | `>= 1` | `<= 10` | Python, JS/TS | None | Radon for Python; lizard for JS/TS | Independent control-flow paths through functions. |
| `halstead_volume` | Complexity | File and function | `>= 0` | `<= 1000` for file-level rows | Python | None | Radon | Halstead program volume derived from operator and operand vocabulary. |
| `halstead_difficulty` | Complexity | File and function | `>= 0` | `<= 10` for file-level rows | Python | None | Radon | Halstead estimate of how hard the code is to understand or write. |
| `halstead_effort` | Complexity | File and function | `>= 0` | `<= 10000` for file-level rows | Python | None | Radon | Halstead mental-effort estimate. |
| `halstead_time` | Complexity | File and function | `>= 0` seconds | None | Python | None | Radon | Halstead implementation-time estimate. |
| `halstead_bugs` | Complexity | File and function | `>= 0` | None | Python | None | Radon | Halstead estimated delivered defects. |
| `function_statements` | Complexity | Function | `>= 0` | None | Python, JS/TS | None | Custom | Count of statements owned by the function, excluding nested scopes. |
| `cognitive_complexity` | Complexity | Function and file | `>= 0` | `<= 15`; generated Python default metric row is disabled | Python | None | Complexipy | Human-comprehension complexity, especially nesting and flow disruption. |
| `message_chain_depth` | SOLID | Function | `>= 0` | None | Python, JS/TS | None | Custom | Deepest attribute/call chain in the function. |
| `function_arity` | Complexity | Function | `>= 0` | None | Python, JS/TS | None | Custom | Required positional parameters after excluding `self` or `cls`; defaulted, keyword-only, and variadic counts ride in details. |
| `boolean_flag_parameters` | SOLID | Function | `>= 0` | None | Python, JS/TS | None | Custom | Positional boolean parameters the function body branches on. |
| `global_state_reach` | SOLID | Function | `>= 0` | None | Python, JS/TS | None | Custom | Distinct module-level names a function touches that the module treats as mutable state. |
| `marker_density` | Maintainability | File | `>= 0` per 1000 lines | None | Python, JS/TS | None | Custom | TODO/FIXME/HACK/XXX marker density. |
| `comment_density` | Maintainability | File | `0..100` percent | None | Python, JS/TS | None | Custom | Percentage of physical lines that are comments. |
| `expression_flatness` | Experimental | Function | `0..1` | None | Python, JS/TS | None | Custom | Share of statements that stay within the one-idea operation budget. |
| `pipeline_linearity` | Experimental | Function | `0..1` | None | Python, JS/TS | None | Custom | Share of assigned local names written once and read once. |
| `narrative_mixed_functions` | Experimental | Module | `>= 0` | None unless `narrative` config exists; then `<= 0` offenders | Python, JS/TS | None | Custom | Count of functions that both narrate through project calls and compute raw details. |
| `narrator_budget_exceeded` | Experimental | Module | `>= 0` | None unless `narrative` config exists; computation uses narrator budget `9`, then `<= 0` offenders | Python, JS/TS | None | Custom | Count of narrator functions exceeding the step budget. |
| `computer_budget_exceeded` | Experimental | Module | `>= 0` | None unless `narrative` config exists; computation uses budgets `8` statements and nesting `1`, then `<= 0` offenders | Python, JS/TS | None | Custom | Count of leaf/computer functions exceeding statement or nesting budgets. |
| `step_down_ordering` | Experimental | Module | `0..1` | None | Python, JS/TS | None | Custom | Share of intra-module calls whose callee is defined below the caller. |
| `name_clarity` | Experimental | Module | `0..1` | None; if `narrative.name_clarity_floor` is set, `>=` that configured value | Python, JS/TS | None | Custom | Mean lexical clarity of callable names against the layered vocabulary. |
| `naming_antipatterns` | Maintainability | Module | `>= 0` | None unless `narrative` config exists; then `<= 0` offenders | Python, JS/TS | None | Custom | Count of naming/behavior contradictions such as lying predicates or two-job names. |
| `lack_of_cohesion` | SOLID | Class | `>= 0` | None | Python, JS/TS | None | Custom | Number of responsibility clusters among a class's concrete methods (methods linked by shared state, calls, properties, or shared inherited callees); no row for classes with no concrete methods. |
| `weighted_methods_per_class` | SOLID | Class | `>= 0` | None | Python | None | Custom, Radon-derived | Sum of member method cyclomatic complexity for a class. |
| `coupling_between_objects` | SOLID | Class | `>= 0` | None | Python, JS/TS | None | Custom | Distinct analyzed classes a class body references (Python: resolved through the class registry; JS/TS: imported names, lexical approximation). |
| `depth_of_inheritance_tree` | SOLID | Class | `>= 1` | None | Python, JS/TS | None | Custom | Inheritance depth after resolving known project bases. |
| `number_of_children` | SOLID | Class | `>= 0` | None | Python, JS/TS | None | Custom | Number of known immediate subclasses. |
| `directory_children` | SOLID | Directory | `>= 0` | None (never gated) | Python, JS/TS | None | Custom | Immediate module/subdirectory fan-out for analyzed directories. |
| `efferent_coupling` | SOLID | Module/package | `>= 0` | None | Python, JS/TS | None | Custom | Number of analyzed modules/packages this module/package imports. |
| `afferent_coupling` | SOLID | Module/package | `>= 0` | None | Python, JS/TS | None | Custom | Number of analyzed modules/packages importing this module/package. |
| `instability` | SOLID | Module | `0..1` | None | Python, JS/TS | None | Custom | Efferent coupling divided by total afferent plus efferent coupling. |
| `dependency_cycles` | SOLID | Cycle | `>= 2` | None unless `import_graph` config exists; then `forbid_cycles` defaults true and requires zero cycles | Python, JS/TS | None | Custom | Strongly connected import-cycle member count. |
| `stable_dependencies_violations` | SOLID | Module | `>= 0` | None unless `import_graph` config exists; then `<= 0` | Python, JS/TS | None | Custom | Imports pointing toward materially less stable modules. |
| `deferred_imports` | SOLID | Module | `>= 0` | None | Python, JS/TS | None | Custom | Analyzed modules imported only inside function bodies or `TYPE_CHECKING` blocks. |
| `abstractness` | SOLID | Module | `0..1` | None | Python, JS/TS | None | Custom | Ratio of abstract classes (abc, Protocol, abstractmethod, or stub-bodied methods) to behavioral classes in a module; data carriers such as exceptions and enums do not count. |
| `distance_from_main_sequence` | SOLID | Module | `0..1` | None | Python, JS/TS | None | Custom | Absolute distance from Martin's main sequence, `abs(A + I - 1)`. |
| `dependency_inversion` | SOLID | Module | `0..1` | None | Python, JS/TS | None | Custom | Mean abstractness of imported project targets. |
| `layering_violations` | SOLID | Module | `>= 0` | None because no layer order exists by default; if `tree_shape.layers` is configured, `<= 0` upward imports | Python, JS/TS | `tree_shape.layers` config | Custom | Imports from a configured lower layer back upward into an earlier layer. |
| `duplication_ratio` | Maintainability | File | `0..1` | None; if `duplication.max_ratio` is set, `<=` that configured value | Python | `duplication` config block | pydry plus custom | Per-file duplicated-line ratio from pydry clone groups. |
| `clone_occurrences` | Maintainability | Clone group | `>= 0` | None | Python | `duplication` config block | pydry plus custom | Number of occurrences in an exact structural clone group. |
| `assertions_per_test` | Test quality | Test function | `>= 0` | None | Python, JS/TS | Test-looking file path and test function name | Custom | Plain assertions plus mock-style assertion calls per test. |
| `mock_call_assertions` | Test quality | Test function | `>= 0` | None | Python, JS/TS | Test-looking file path and test function name | Custom | Mock call-count or call-argument assertion calls per test. |
| `big_literal_assertions` | Test quality | Test function | `>= 0` | None | Python, JS/TS | Test-looking file path and test function name | Custom | Assertions involving large inline literal structures. |
| `test_churn_ratio` | Test quality | Suite | `>= 0` | None | Any | Git history and test path conventions | git plus custom | Test lines changed divided by source lines changed. |
| `co_churn_multiplicity` | Test quality | Suite | `>= 0` | None | Any | Git history and test path conventions | git plus custom | Median number of test files touched in source-touching commits. |
| `suite_redundancy_index` | Test quality | Coverage artifact | `0..1` | None | Python coverage data | coverage.py dynamic-context artifact | coverage.py artifact plus custom | Share of tests that the greedy line-coverage cover can omit. |
| `blast_radius` | Test quality | Covered file | `>= 0` | None | Python coverage data | coverage.py dynamic-context artifact | coverage.py artifact plus custom | Number of distinct tests executing a file. |
| `code_churn` | VCS | File | `>= 0` | None | Any | Git history | git plus custom | Lines added plus deleted over the mined history window. |
| `change_coupling` | VCS | File pair | `>= 3` | None | Any | Git history | git plus custom | Number of commits in which a file pair changed together. |
| `maintainability_index` | Maintainability | File | `0..100` | `>= 50` in generated Python config | Python | None | Radon | Composite maintainability score from complexity, size, and Halstead data. |
| `single_responsibility_index` | SOLID | Class | `>= 0` | None | Python, JS/TS | None | Custom | Excess cohesion components (beyond one) weighted by method complexity and class size; zero for cohesive classes and interfaces. |
| `hotspot` | Maintainability | File | `>= 0` | None | Any | Git history and report snapshot with complexity for the file | git plus custom | Code churn multiplied by worst cyclomatic complexity from a snapshot. |

## Custom Metric Computation Notes

- JavaScript/TypeScript house-style rows come from a dependency-light lexical
  analyzer. Metrics that require source-shape recovery carry
  `details.approximate=true`; lizard remains the source for JS/TS cyclomatic
  complexity, LOC, and SLOC.
- `message_chain_depth`: walks each function representation and reports the deepest attribute/call chain, with the first local receiver hop (`self`, `cls`, `this`, or `super`) discounted.
- `function_arity`: counts required positional parameters, excluding leading `self` or `cls` on Python methods. Parameters with defaults, keyword-only parameters, and `*args`/`**kwargs` do not count toward the value (a keyword-only configuration surface is not a missing parameter object); their counts are recorded in `details` as `defaulted`, `keyword_only`, and `variadic`.
- `boolean_flag_parameters`: counts positional parameters annotated as boolean or defaulted to a boolean value that also appear in the test of an `if`, `while`, or conditional expression in the function's own body. A flag that is only stored or passed along is configuration, not a hidden second function. Python keyword-only booleans are exempt.
- `global_state_reach`: decides which module-level names are mutable state by evidence rather than spelling: a name counts when some function in the module writes to it (a `global` declaration plus assignment, an item or attribute store, or a mutating method call such as `append` or `update`), when it is rebound more than once at module level, or when it is bound to a mutable container literal or constructor. The value is how many distinct such names a function reads or declares global. Compiled regexes, type aliases, and sentinels that are assigned once and only read are constants whatever their case.
- `marker_density`: tokenizes comments, counts TODO/FIXME/HACK/XXX markers, and normalizes by physical lines per thousand.
- `comment_density`: tokenizes comments and reports comment lines divided by total physical lines as a percentage.
- `function_statements`: counts statements owned by a function while descending into control-flow blocks but excluding nested function/class scopes.
- `expression_flatness`: scores each owned statement by operation weight and reports the fraction at or below the one-idea budget.
- `pipeline_linearity`: counts local names assigned exactly once and loaded exactly once, divided by all assigned local names.
- `lack_of_cohesion`: builds connected components over a class's concrete methods and counts the responsibility clusters. Two methods connect when they touch the same field (through `self` or `cls`), when one calls the other or reads a property the other defines, or when both call the same inherited method. Dunder methods other than `__init__`, methods declared with `abstractmethod`, and stub bodies (`pass`, `...`, `raise NotImplementedError`, docstring only) are excluded. A component that is a single method touching no state is a stateless helper, not a cluster; it is counted in `details.stateless_methods` instead. A component consisting only of `__init__` is setup, not a responsibility. `details.clusters` lists the first members of each cluster, and a class with no concrete methods gets no row.
- `weighted_methods_per_class`: sums Radon per-method cyclomatic complexity rows by owning class.
- `coupling_between_objects`: for Python, counts the distinct analyzed classes named inside a class body, resolved through the same registry as inheritance (same-module names and imported names); the class itself and external names do not count, and `details.classes` lists the resolved targets. Rows are approximate because no type inference is performed. JS/TS rows keep the lexical imported-name approximation.
- `depth_of_inheritance_tree`: resolves project-local base classes from extracted class/import facts and reports maximum depth, treating unresolved external parents as one extra level.
- `number_of_children`: reverses the resolved inheritance edges and counts immediate project-local subclasses.
- `single_responsibility_index`: computes `(cohesion_components - 1) * (1 + weighted_methods / 30) * (1 + statements / 60)` and rounds to two decimals. A class with one component scores zero however large it is (size is a separate finding under weighted methods and statements); interfaces have zero components and score zero.
- `directory_children`: counts immediate analyzed module files plus immediate subdirectories for each analyzed directory, excluding plumbing files such as `__init__.py`.
- `efferent_coupling`: counts resolved outgoing import edges from a module or collapsed package.
- `afferent_coupling`: counts incoming resolved import edges to a module or collapsed package.
- `instability`: computes `Ce / (Ca + Ce)`, or `0` when both coupling counts are zero.
- Import edges: only imports that execute at import time count (top level, class bodies, conditional blocks). Imports inside function bodies or `if TYPE_CHECKING:` blocks are excluded from every graph metric and reported as `deferred_imports`, with the resolved targets in `details.targets`. When the analyzed root is a package, an absolute import resolves only through the package's own name, so `import json` inside a package that has a `json.py` stays external; a non-package root matches absolute imports as written.
- `dependency_cycles`: runs Tarjan strongly connected components over the resolved import graph and emits components with at least two modules.
- `stable_dependencies_violations`: counts outgoing edges where target instability exceeds source instability by more than the fixed `0.2` tolerance; the offending modules are listed in `details.targets`.
- `abstractness`: counts abstract classes divided by the module's behavioral classes. A class is abstract when it has an ABC/Protocol base, an ABCMeta metaclass, an `abstractmethod` decorator, any method whose body is only `raise NotImplementedError` or `...`, or when every method is a stub (an interface written with `pass` bodies). Data carriers, meaning classes with no concrete non-dunder method (exception hierarchies, enums, named tuples, dataclasses), are neither abstractions nor implementations and do not count; a module holding only data carriers has no abstractness or distance row.
- `distance_from_main_sequence`: computes `abs(abstractness + instability - 1)` for modules that have abstractness rows.
- `dependency_inversion`: averages the abstractness of imported target modules, treating classless targets as concrete.
- `narrative_mixed_functions`: classifies callable facts and counts functions with both project-level narrative calls and raw computation beyond the profile tolerance.
- `narrator_budget_exceeded`: counts narrator functions whose statement count exceeds the configured narrator step budget.
- `computer_budget_exceeded`: counts computer/leaf functions whose statement count or nesting exceeds configured budgets.
- `step_down_ordering`: counts intra-module calls and reports the fraction where the callee appears later in the same module.
- `layering_violations`: compares resolved import edges to configured layer order and counts imports from lower layers back into earlier layers.
- `name_clarity`: splits callable names into words, scores them against the built-in/project/user vocabulary, and averages non-dunder callable scores per module.
- `naming_antipatterns`: skips stub bodies (an abstract declaration has no behavior to contradict) and treats `TypeGuard` and `TypeIs` return annotations as boolean; otherwise counts callable names with positive-evidence contradictions such as `is_*` returning non-bool, `get_*` returning no value, or `_and_` two-job names.
- `duplication_ratio`: asks pydry for exact structural clone groups, sums duplicated spans per file, divides by that file's SLOC, and caps at `1.0`.
- `clone_occurrences`: reports pydry exact clone group occurrence counts.
- `assertions_per_test`: in test-looking files, counts `assert` statements and mock-style assertion calls per test function.
- `mock_call_assertions`: in test-looking files, counts mock assertion calls such as `assert_called*`, `assert_awaited*`, and `assert_has_calls`.
- `big_literal_assertions`: in test-looking files, counts assertions whose expression contains dict/list/set/tuple literals of at least eight entries.
- `code_churn`: mines `git log --numstat --no-merges` for the selected window and sums added plus deleted lines per file. Only files the configuration would analyze count (source extensions minus ignore patterns and gitignore), so documentation and generated artifacts do not dominate.
- `change_coupling`: counts co-commit pairs and reports pairs meeting the fixed support floor of three commits. Commits touching more than `--max-commit-files` source files (default 20) add to churn but not to coupling, since a bulk rename or reformat co-changes everything with everything.
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
  validation rejects negative values, and metric-specific ranges are not encoded
  there.
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
  meaningfully configured through `languages[].metrics`; project metrics use
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
- `docs/statistics_feature.md` lists only six "Available metrics"; the stats
  parser accepts any `MetricType` name and an `all` prefix, though project-scope
  metrics still only appear where the stats path consumes their rows.
- `DEMOS/README.md` uses a cognitive complexity default of `10`, while the code
  and main README use `15`.
