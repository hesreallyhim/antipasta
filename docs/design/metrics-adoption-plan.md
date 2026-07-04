# Metrics adoption plan — detailed implementation specs

Roadmap + detailed design, 2026-07-04 (detail pass same day; implementation
in subsequent passes). Scope: every ADOPT verdict in
`docs/solid_metrics_review.md` (rounds 1–2), the Narrative Index
(`narrative-index.md`), LLM-assisted evaluation (`llm-assisted-evaluation.md`),
and test-suite health (`test-suite-health.md`). The performance substrate
(in-process runners, process pool, content-addressed cache, extract/derive
split per `structural-metrics-caching.md`) landed 2026-07-04 and is assumed.

Everything below is design-current-best; an implementing session may deviate
with reasons recorded in the phase's closing commit.

## Ordering principles (unchanged)

1. Infrastructure-dependency order (per-function walk → class scope → import
   graph); 2. every phase ships visible violations; 3. project-scope
   reporting piloted on the smallest metric; 4. dogfood reckoning closes
   every phase; 5. tracks A–D are independent and interleave.

---

## Phase 0 — plumbing (M)

**Goal:** fact rows + project-scope reports + profiles + derivation hook.
No user-visible metrics; smallest possible diff that later phases ride.

**Schema.**
- `core/metrics.py`: new `FactRow` dataclass — `{kind: str, payload: dict[str,
  Any]}`, JSON-safe payload, strictly path-independent (rule from
  `structural-metrics-caching.md`). Collection payload becomes
  `(metrics, facts, errors)`; cache entry bumps to `v2` with a `facts` array
  (fingerprint change auto-invalidates v1 — no migration code).
- `core/violations.py`: `ProjectReport {subject: str /* "." or dir path */,
  metrics: list[MetricResult], violations: list[Violation]}`. `Violation`
  gains optional `subject` (defaults to file).
- Snapshot `schema_version: 2`: adds top-level `project` block
  `{reports: [...]}`; treemap directory nodes may reference project findings
  by subject path (report UI wiring lands with the first directory metric).

**Derivation hook.** `MetricAggregator.analyze_files` gains a post-collection
stage: `_derive(reports, facts_by_file, root) -> list[ProjectReport]` running
registered derivers — `Deriver = Callable[[DerivationInput], list[ProjectReport]]`
where `DerivationInput = {reports, facts_by_file, root: Path, config}`.
Derivers are pure and fast (never cached; see structural-metrics-caching.md).
CLI `metrics` prints a "Project findings" section; exit code folds project
violations in. `stats`/`report` consume project reports read-only.

**Profiles.** Config gains `profile: extreme | standard | relaxed` plus
per-metric overrides. Phase 0 only plumbs the enum + resolution precedence
(per-metric > profile default); consumers arrive in Phase 1.

**Tests.** Fact-row cache round-trip (v2), v1-entry treated as miss, a dummy
deriver end-to-end (facts in → project violation out → exit code), profile
resolution precedence.

**Acceptance.** All existing tests green; dogfood unchanged (no new metrics
fire); snapshot v2 accepted by report; `--baseline` across v1/v2 degrades
with a clear message rather than crashing.

**Open questions.** Whether `stats` should display project reports or ignore
them (lean: ignore in Phase 0).

---

## Phase 1 — single-walk house metrics + project-scope pilot (M)

**Goal:** one new runner (`runners/python/house_style.py`) doing a single
`ast` walk per file, emitting per-function/per-file rows + the import facts
Phase 2/3 will need; Module Tree Shape's tree half as the project-scope pilot.

**New MetricTypes** (thresholds via existing violation machinery; defaults
from the profile):
- `message_chain_depth` (per expression, reported as per-function max).
  Attribute/call chain depth: `foo.bar()` = 1, `foo.bar.baz.quix()` = 3.
  Default max 2 (extreme: 1). Allowlist config for fluent idioms +
  `self`/`cls` first hop free + stdlib chains (`path.parent.name`).
- `function_arity` (params excluding self/cls; default max 5, extreme 4;
  keyword-only params configurable to count half).
- `boolean_flag_params` (count of positional bool-typed/bool-defaulted
  params; default max 0 warning-level).
- `exception_discipline` (count of bare `except:`, `except Exception` without
  re-raise, and silent `pass` handlers; default max 0).
- `global_state_reach` (module-level mutable names read/written per function;
  default max 0 extreme, 2 standard).
- `marker_density` (TODO/FIXME/HACK/XXX per 1000 lines, from comments —
  needs the raw comment text: extract in the same walk via tokenize).
- `comment_density` (comment_lines / lines_of_code — derived from existing
  radon rows in a tiny deriver; config-only otherwise).
- `function_statements` (statement count; feeds length-distribution
  reporting: file p50/p90 as informational rows).
- `expression_flatness`, `pipeline_linearity` (Narrative Index components
  that need no symbol table; algorithms seeded from
  `tests/temp/narrative_index_probe.temp.py`).

**Fact rows emitted in the same walk** (consumed later, cached now):
- `imports`: raw, unresolved — `[{module: ".x"|"pkg.mod", names: [...],
  level: int}]`.
- `callables`: `[{name, lineno, arity, is_method, class_name|None}]`.
- `classes`: `[{name, bases_raw: [...], methods: [{name, fields_read,
  fields_written, calls_local}]}]` (Phase 2 consumes; emitting now avoids a
  second walk later — one parse, all facts).

**Module Tree Shape, tree half** (`core/tree_shape.py`, a deriver):
`os.scandir` walk of the analyzed root. Config:
```yaml
tree_shape:
  fan_out: {min: 2, max: 7}     # 5–7 band; both directions violations
  leaf_max_sloc: 400             # from existing per-file rows
  exclude: [tests, docs]
```
Violations (subject = directory): `too_many_children` ("missing layer"),
`too_few_children` ("pointless layer", min 2, root exempt), `oversized_leaf`.
This pilots ProjectReport → CLI → snapshot → report hover (directory
aggregates gained hover in the report branch — findings attach there).

**Tests.** Per-metric fixture files (good/bad twins, probe style); tree-shape
fixture directory trees (missing layer, pointless layer); profile switching
changes thresholds; JS/TS files unaffected (Python-only runner).

**Dogfood risk (real).** `cli/` currently has >7 children in places;
antipasta's own `except Exception` uses in runners (deliberate — subprocess-era
semantics) will fire `exception_discipline`. Reckoning: allowlist-with-reason
config entries checked into `.antipasta.yaml`, or refactors. Budget a real
session-chunk for this; the gate has forced five refactors already.

**Acceptance.** Each metric fires on its bad-twin fixture and not its good
twin; dogfood green after reckoning; warm-run time still <0.5 s on antipasta.

---

## Phase 2 — class scope: cohesion cluster (M–L)

**Goal:** class-level metrics from the Phase 1 `classes` facts + a cross-file
class registry deriver.

**Metrics.**
- `lcom` (LCOM4: connected components over methods, edges = shared field
  access ∪ local method calls; value = component count, ideal 1; default max
  1 extreme / 2 standard). Per class, reported on the file with
  `function_name = class name`.
- `wmc` (sum of member cyclomatic complexity — join radon's per-method CC
  rows by classname in a deriver; no re-parse; default max 50, extreme 30).
- `cbo` (labeled approximation, `details: {approximate: true}`: distinct
  non-stdlib names a class body references via imports, annotations,
  instantiations; default max 10).
- `dit` / `noc` — registry deriver: resolve `bases_raw` using the `imports`
  facts (absolute + relative resolution against the module table; unresolved
  external bases count depth 1 and are flagged unresolved). DIT default max
  5; NOC informational at first (no default threshold).
- **Rider:** `srp_index` — informational composite (normalized LCOM4 ×
  WMC-band × SLOC-band), no default threshold until validated against real
  God-classes (validation task in-phase: run on 3 known-bad corpora, eyeball).

**Files.** `core/class_registry.py` (deriver), LCOM/CBO computed in the
Phase 1 runner walk (facts already carry field access). No new runner.

**Tests.** LCOM4 textbook cases (1-component cohesive class, 3-component
God-class, property/dunder handling policy: dunders excluded, properties
count as field reads); diamond inheritance DIT; unresolved-base labeling;
WMC join correctness against radon rows.

**Dogfood risk.** FleetViewModel-scale classes don't exist here; low. `cli`
command classes may trip CBO.

---

## Phase 3 — import graph: dependency cluster (L)

**Goal:** the module graph and Martin's suite; cycles first.

**Resolution algorithm** (`core/import_graph.py`): module table from analyzed
files (src-layout aware: strip configured roots, default auto-detect `src/`);
relative imports resolved by dot-level against the importing module's package;
targets resolved longest-prefix-first (probe-verified approach); imports that
resolve outside the analyzed set become external nodes (counted for Ce,
excluded from cycles).

**Metrics** (subject = module file, or package dir for rollups):
- `dependency_cycles` — Tarjan SCC (probe code is the seed; iterative
  implementation, no recursion limit). Violation per SCC (subject = the
  cycle, listed members), default max 0. **Ships first within the phase.**
- `efferent_coupling`, `afferent_coupling`, `instability` (informational by
  default; thresholds optional).
- `sdp_violations` — per edge where source instability < target instability
  by more than an epsilon (default 0.2); informational at first.
- `package_coupling` (PCA/PCE rollup, informational).
- **Module Tree Shape, layering half**: with config
  `layers: [cli, report, runners, core]` (order = downward), violations for
  upward or layer-skipping imports; without config, only sibling-cycle
  checks (no invented order).

**Report.** Directory hover gains cycles/coupling findings; snapshot carries
the graph summary (nodes, edges, cycle count) for trend lines; Main-Sequence
scatter deferred to Phase 4 (needs Abstractness for the second axis).

**Tests.** Resolution table-driven cases (relative dots, src-layout,
namespace packages, unresolvable); synthetic cycle fixtures (2-cycle,
3-cycle, self-import excluded); SDP direction cases; layering fixtures with
config permutations.

**Dogfood.** Probe says antipasta has 0 cycles — should stay green; layering
config for antipasta itself gets written as part of reckoning (cli → report →
runners → core is the de facto order).

---

## Phase 4 — composites + full Narrative Index (L)

**Abstractness** (`abstractness`): per module, abstract types (ABC bases,
`Protocol`, `@abstractmethod` presence — facts extended in the Phase 1/2
walk) ÷ total classes. → `distance_main_sequence` = |A + I − 1|
(informational + the scatter view in the report: modules plotted A×I, zone
shading, hover = module). → `dip_compliance` (labeled approximation): per
module, imported project targets classified abstract/concrete by the
registry; ratio + violation on all-concrete-heavy modules (threshold
configurable, standard 0.x TBD during validation).

**Narrative Index, complete** (`core/narrative.py` + `core/lexicon.py`):
- Symbol table: project-defined callables from Phase 1 facts + import graph
  (resolves cross-module calls); ambient vocabulary = configured list ∪
  call-graph fan-in above percentile (default p95).
- Classification (narrator/computer/MIXED/trivial) + per-class budgets
  (narrator steps ≤ 9 extreme; computer statements ≤ 8, nesting ≤ 1) — the
  probe's `classify_function`/`check_budget` are the seeds.
- `narration_ratio` (with the profile's prose-grade expression dial),
  `step_down_ordering` (per module: fraction of intra-module calls whose
  callee is defined below the caller; default min 0.8 extreme, informational
  standard).
- Name clarity: embedded wordlist asset (`data/wordlist.txt`, ~50k words,
  SCOWL-derived, license-checked); abbreviation list; anchor-harvested
  project lexicon (package/module/class names, config keys, README title
  words — anchors only, per the self-whitelisting hazard); user allowlist;
  junk stop-list; linguistic-antipattern checks (`get_*` returning None,
  `is_*` non-bool, `*_and_*` names).
- Violations fire per component (never on the composite); composite
  `narrative_index` is informational for treemap coloring + trends.

**Tests.** Probe samples become the fixture suite (all seven, with class +
budget + component expectations pinned); lexicon layering (foo passes in
foo-measure, `fn` never passes); antipattern cases; ambient exclusion.

**Dogfood risk (highest of the plan).** Step-down ordering and narration on
antipasta's own core will fire; the reckoning either tunes standard-profile
defaults or refactors — findings recorded either way. This phase is the
plan's thesis test: the owner's house style, enforced on real code.

---

## Track A — pydry duplication runner (M; any time after Phase 0)

Optional dependency (`antipasta[dry]`) importing the pydry engine (owner's
package) — subprocess JSON envelope as fallback. Per-file
`duplication_ratio` (duplicated lines ÷ SLOC) and `clone_pair_count`;
project-level worst-offenders ProjectReport. The pairwise near-match stage is
the one derivation that earns Merkle-tree-hash memoization (see
structural-metrics-caching.md); exact-clone stage is cheap. Also pointed at
the test tree for track D1's near-duplicate-test signal.

## Track B — version-control mode (M–L; opt-in `--vcs`)

`core/vcs.py`: `git log --numstat` miner, keyed (HEAD, window). `code_churn`
per file (windowed adds+deletes), `hotspot` = churn × max CC (treemap
overlay), `change_coupling` pairs (association support/confidence, min
support 5 co-commits). Never on the default path; cached per commit range.
Also computes track D3's test-churn ratio and co-churn multiplicity.

## Track C — LLM-assisted evaluation (M; opt-in, advisory)

Per `llm-assisted-evaluation.md`. Increment 1: provider abstraction
(anthropic + local endpoint), versioned prompts as assets, tier-1 classifier
+ tier-2 blind/informed agreement on narrators only; advisory rows
(`advisory: true`, model + prompt_version in details and fingerprint).
Increment 2: leaf naming test; calibration report (static score ×
blind-reading outcome matrix). Increment 3 (audit): tier-4 disclosure curves
(assertion reconstruction; execution-free; equivalence-graded).

## Track D — test-suite health (per `test-suite-health.md`)

D1 static smells ride the Phase 1 walk (test files opted in by config);
D2 coverage-matrix redundancy = artifact ingestion (`coverage.py` dynamic
contexts; degrade gracefully when absent) → unique-coverage ratio, suite
redundancy index, blast-radius distribution on the treemap;
D3 churn coupling rides track B; D4 rigor (mutation-matrix ingestion, LLM
contract-vs-incidental, disclosure-curve change-detector detection) rides
track C. First patient: antipasta's own 357-test suite.

---

## Cross-cutting engineering rules

- Every new analyzer returns rows/facts through `_collect_file_metrics` —
  cache + pool inheritance is by construction, and a phase that bypasses the
  substrate is wrong by definition.
- Facts are path-independent and judgment-free; config never touches
  extraction; derivations are pure and uncached (Merkle memoization only
  where measured-expensive).
- Approximations always labeled (`approximate: true`), advisory LLM rows
  always labeled; composites never gate — components do.
- Snapshot schema bumps at most once per phase; report UI lands in the same
  phase as the metric it displays; README metric table per phase.
- Per-phase closing: pytest + ruff + mypy + dogfood reckoning (pass or tune
  with reasons committed) + a `docs/design/` addendum recording deviations.

## Coverage check (nothing dropped)

R1 adopts → P2 (LCOM, WMC, CBO, DIT, NOC), P3 (cycles/ADP, SDP, Ce/Ca/I,
package coupling), P4 (Abstractness, Distance, DIP), P1 (comment density),
track B (churn, change coupling). R2 adopts → P1 (Demeter, arity, flags,
exceptions, globals, markers; tree-shape tree half), P3 (layering half),
track A (pydry). Narrative Index → P1 (flatness, pipeline, lengths), P4
(full). LLM → track C. Test-suite health → track D. Shipped: cyclomatic,
Halstead, MI, cognitive.
