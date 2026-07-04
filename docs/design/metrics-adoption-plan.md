# Metrics adoption plan — implementation order for every ADOPT verdict

Roadmap, 2026-07-04. Scope: everything marked ADOPT in
`docs/solid_metrics_review.md` (rounds 1 and 2) plus the Narrative Index
(`docs/design/narrative-index.md`), sequenced for implementation. The
performance substrate (in-process runners, process pool, content-addressed
cache, extract/derive split) landed 2026-07-04 and is assumed throughout.

## Ordering principles

1. **Infrastructure dependency order** — a metric lands in the first phase
   where its scope exists (per-function walk → class scope → import graph).
2. **Each phase ships user-visible violations** — no phase is pure plumbing
   except Phase 0, which is deliberately minimal.
3. **Pilot the risky architecture on the smallest metric** — project-level
   reporting (a new concept: violations with no single file) is pioneered by
   the tree-shape half of Module Tree Shape, which needs no per-file facts at
   all, before the import graph depends on it.
4. **Dogfood reckoning closes every phase** — antipasta must pass its own new
   metrics (or the defaults must be defended). Expect real findings: the gate
   has already forced five refactors on the report branch.
5. **Two tracks are independent** (pydry, VCS) and can interleave anywhere.

## Phase 0 — plumbing (M)

The only infrastructure-first phase; everything after rides it.

- **Fact rows**: extend the collection payload so runners can emit
  non-thresholded, path-independent facts (raw import statements, class/base
  declarations, callable definitions) alongside metric rows. Cache entry
  format bumps to v2 (the fingerprint change invalidates old entries
  automatically — no migration).
- **Project-scope reports**: a report row whose subject is a directory or the
  project, not a file — model, CLI output, snapshot schema bump, exit-code
  semantics. This is the one genuinely new architectural concept.
- **Profiles**: the strictness dial (`extreme` / `standard` / `relaxed`) in
  config, consumed by later phases (prose-grade expressions, budgets).
- **Derivation hook**: `analyze_files` gains a post-collection derivation
  stage that receives all reports + facts + the live directory tree.

## Phase 1 — single-walk house metrics + the project-scope pilot (M)

All per-function/per-file, one shared Python syntax-tree runner, every one
individually thresholdable; several are probe-seeded already.

- Law of Demeter chain depth (with fluent-interface allowlist)
- Function arity · boolean-flag parameters · exception discipline
  (bare/broad except) · global-state reach · marker density (TODO/FIXME)
- Comment density (radon already emits the inputs — config only)
- Function length distribution · expression flatness · pipeline linearity
  (Narrative Index components that need no project symbol table)
- Cognitive-complexity ceiling profile (config only, zero code)
- **Module Tree Shape, tree half** (fan-out 5–7 band, leaf size caps): pure
  `os.scandir` derivation — the pilot for project-scope reporting.

## Phase 2 — class scope: the cohesion cluster (M–L)

One class-registry pass (classes → methods → field access), emitting facts
for the registry derivation.

- Lack of Cohesion of Methods (LCOM4 / connected components)
- Weighted Methods per Class
- Coupling Between Objects (labeled approximation)
- Depth of Inheritance Tree + Number of Children (registry derivation —
  base-name resolution is cross-file, so it's a derivation over class facts)
- Rider: the Single-Responsibility index (composition of the above + LOC) —
  tabled in review but lands nearly free here; validate against real
  God-classes before trusting.

## Phase 3 — import graph: the dependency cluster (L)

Fact rows: raw unresolved imports (path-independence rule per
`structural-metrics-caching.md`). Derivation: resolution → module graph.

- **Dependency cycles / Acyclic Dependencies Principle first** — highest
  actionable value in the entire table; SCC already probe-verified at 0.3 ms.
- Efferent + afferent coupling → Instability
- Stable Dependencies Principle (edge direction vs instability)
- Package coupling (graph rolled up to packages)
- **Module Tree Shape, layering half** (sibling imports acyclic + downward)
- Report: directory hover aggregates gain structural findings; groundwork
  for the Main-Sequence scatter (completed in Phase 4).

## Phase 4 — composites + the full Narrative Index (L)

Needs Phases 2 + 3.

- Abstractness (definitional work: abstract base classes, Protocols,
  abstract methods) → Distance from the Main Sequence (+ scatter view)
- Dependency Inversion compliance (labeled approximation)
- **Narrative Index, complete**: narration ratio + narrator/computer/MIXED
  classification + per-class budgets (project symbol table from the import
  graph; ambient-vocabulary detection via call fan-in), step-down ordering,
  name clarity (embedded wordlist asset + anchor-harvested project lexicon +
  linguistic-antipattern checks).

## Independent track A — pydry duplication runner (M)

Any time after Phase 0. Invoke the pydry engine (owner's own code) as a
runner: `duplication_ratio`, `clone_pair_count` per file + project
worst-offenders list. The one derivation that earns the Merkle-tree-hash
memoization (pairwise similarity is quadratic); incremental form compares
only changed files' fingerprints.

## Independent track B — version-control mode (M–L, opt-in)

Last, behind `--vcs`, cached per commit range: code churn (× complexity =
the hotspot map, pairs with the treemap) and change coupling.

## Per-phase closing checklist

- `pytest` green · `ruff` · `mypy` · **dogfood reckoning** (antipasta passes
  its own new metrics, or defaults are tuned with reasons recorded)
- Snapshot schema + report UI updated in the same phase as the metric
- README metric table updated
- New metrics inherit cache + pool by construction (fact rows through
  `_collect_file_metrics`) — a phase that bypasses the substrate is wrong.

## Coverage check (nothing dropped)

Round 1 adopts: cycles/ADP (P3), SDP (P3), Ce/Ca/Instability (P3), package
coupling (P3), Abstractness/Distance (P4), DIP (P4), LCOM (P2), WMC (P2),
CBO (P2), DIT/NOC (P2), comment density (P1), churn + change coupling
(track B). Round 2 adopts: Module Tree Shape (P1 + P3), pydry (track A),
Demeter/arity/flags/exceptions/globals/markers (P1). Narrative Index:
components without symbol-table needs (P1), full (P4). Shipped already:
cyclomatic, Halstead, maintainability index, cognitive complexity.
