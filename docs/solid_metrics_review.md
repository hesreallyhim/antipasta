# SOLID metrics review — evaluation of `solid_code_metrics_table.csv`

Reviewed 2026-07-03 against antipasta as it stands on `feat/report-command`
(radon + complexipy + lizard runners; file- and function-scoped metric model;
snapshot schema v1; offline HTML report). Each metric is scored on:

- **Importance (1–5):** how much it enables *deep SOLID analysis* — cohesion,
  coupling, dependency direction, responsibility — not generic code quality.
- **Complexity (XS/SM/M/L/XL):** implementation cost *in antipasta*, counting
  shared infrastructure honestly (the first metric on a new analysis scope pays
  for the scope; followers are cheap).
- **Verdict:** ADOPT / TABLE / ABANDON, with reasoning.

(Metric acronyms are spelled out in full throughout, on purpose.)

## The strategic picture first

The single most important observation: antipasta today sees **files and
functions**. SOLID lives at two scopes antipasta cannot yet see:

1. **Class scope** — cohesion and responsibility (Lack of Cohesion of Methods,
   Weighted Methods per Class, Depth of Inheritance Tree, Number of Children,
   Coupling Between Objects). Requires one new analyzer: a Python syntax-tree
   pass that maps classes to methods to attribute and name usage. One platform,
   five metrics fall out.
2. **Module / import-graph scope** — coupling and dependency direction (Afferent
   Coupling, Efferent Coupling, Instability, Abstractness, Distance from the Main
   Sequence, dependency cycles, Stable Dependencies Principle, package coupling,
   Dependency Inversion Principle). Requires one new analyzer: an import graph
   (pure Python parsing, or a library such as grimp). One platform, eight metrics
   fall out.
3. **Version-control scope** (bonus, non-static) — evolutionary coupling (code
   churn, change coupling). One `git log --numstat` miner, two metrics fall out.
   This also subsumes the already-deferred git-churn hotspot scatter report idea.

So the thirty-row table collapses into **three infrastructure investments plus a
handful of derivations**. That is the plan's shape: build scopes, not metrics.

**Alignment with priorities (i) latency and (ii) caching:** the class-scope and
import-graph analyzers should be built *content-hash cached from day one* (hash a
file to its analysis JSON; the import graph re-derives only for changed files).
Static SOLID metrics are pure functions of file content — they are the ideal
cache citizens, and the graph assembly is cheap once the per-file facts are
cached. Do not bolt caching on later; make the new analyzers the first cached
ones.

**Honesty rule** (existing antipasta ethos, keep it): Python's dynamism makes
several of these *approximations* — Coupling Between Objects, Response For Class,
Dependency Inversion Principle. Approximate metrics are fine; mislabeled ones are
not. Every adopted approximation gets a `details: {"analyzer": ...,
"approximate": true}` provenance flag and a documented definition, the same way
the report already labels JavaScript/TypeScript metric coverage.

---

## Verdict table

| # | Metric | Category | Importance | Complexity | Verdict |
|---|--------|----------|:---:|:---:|---------|
| 1 | Lack of Cohesion of Methods | Cohesion & Coupling | 5 | M | **ADOPT** |
| 2 | Coupling Between Objects | Cohesion & Coupling | 5 | M | **ADOPT** (approx.) |
| 3 | Afferent Coupling | Cohesion & Coupling | 4 | SM† | **ADOPT** |
| 4 | Efferent Coupling | Cohesion & Coupling | 4 | SM† | **ADOPT** |
| 5 | Instability | Cohesion & Coupling | 4 | XS† | **ADOPT** |
| 6 | Abstractness | Cohesion & Coupling | 4 | SM | **ADOPT** |
| 7 | Distance from the Main Sequence | Cohesion & Coupling | 4 | XS† | **ADOPT** |
| 8 | Cyclomatic Complexity | Complexity | 3 | — | **ADOPT** (shipped) |
| 9 | Halstead metrics | Complexity | 2 | — | **ADOPT** (shipped) |
| 10 | Weighted Methods per Class | Complexity | 4 | SM‡ | **ADOPT** |
| 11 | Response For Class | Complexity | 3 | L | **TABLE** |
| 12 | Depth of Inheritance Tree | Inheritance | 3 | SM‡ | **ADOPT** |
| 13 | Number of Children | Inheritance | 3 | SM‡ | **ADOPT** |
| 14 | Polymorphism Factor | Inheritance | 2 | M | **ABANDON** |
| 15 | Modularity Index | Architecture | 2 | L | **ABANDON** |
| 16 | Package Cohesion | Architecture | 3 | M | **TABLE** |
| 17 | Package Coupling | Architecture | 3 | SM† | **ADOPT** |
| 18 | Dependency Cycles | Architecture | 5 | M† | **ADOPT** |
| 19 | Acyclic Dependencies Principle | Architecture | 5 | XS† | **ADOPT** (merged into #18) |
| 20 | Stable Dependencies Principle | Architecture | 4 | XS† | **ADOPT** |
| 21 | Maintainability Index | Maintainability | 2 | — | **ADOPT** (shipped) |
| 22 | Comment Density | Maintainability | 2 | XS | **ADOPT** |
| 23 | Code Churn | Evolutionary | 3 | M | **ADOPT** (version-control phase) |
| 24 | Change Coupling | Evolutionary | 4 | M | **ADOPT** (version-control phase) |
| 25 | Temporal Cohesion | Evolutionary | 2 | XL | **ABANDON** |
| 26 | Commit Frequency | Evolutionary | 1 | XS | **TABLE** (churn sub-stat) |
| 27 | Single Responsibility violation index | Design Principles | 3 | SM‡ | **TABLE** (compose later) |
| 28 | Interface Segregation violation ratio | Design Principles | 3 | XL | **TABLE** (Protocol-scoped variant only) |
| 29 | Dependency Inversion compliance | Design Principles | 5 | M | **ADOPT** (approx.) |
| 30 | Open/Closed flexibility index | Design Principles | 2 | XL | **ABANDON** |

† cost shown assumes the **import-graph analyzer** exists (itself M, amortized
across eight metrics). ‡ assumes the **class-scope analyzer** exists (itself M,
amortized across five-plus metrics).

**Tally: 19 ADOPT (3 already shipped) · 5 TABLE · 4 ABANDON · 2 merged/absorbed.**

---

## Per-metric reasoning

### Class scope (the Single-Responsibility end of SOLID)

**1. Lack of Cohesion of Methods — Importance 5, M, ADOPT.** The canonical
cohesion metric and the single best automated single-responsibility signal: a
class whose methods partition into groups that do not share attributes is really
N classes wearing one name. Use the connected-components formulation (sometimes
called LCOM4) rather than the original subtraction formula — its "number of
responsibilities" reading is directly actionable ("this class splits into 3").
Implement it in our own syntax-tree pass rather than a small third-party cohesion
package: we need per-class rows in our own schema, and the algorithm is about a
page. The class-scope analyzer this requires is the M; this metric on top is
small.

**2. Coupling Between Objects — Importance 5, M, ADOPT (approximate).** Counts the
distinct classes a class references. Full precision needs type resolution Python
cannot give statically (attribute types, call-target classes), so antipasta's
version is a documented approximation: distinct imported names, annotated types,
and instantiated names used inside a class body, flagged `approximate: true`.
Still the best available "this class touches too much of the world" signal, and
the class-scope companion to the import-graph coupling metrics. (Contested call:
a stricter reviewer would TABLE this until real name resolution exists; the
verdict here is ADOPT-as-labeled-approximation, consistent with the report's
existing coverage honesty.)

**10. Weighted Methods per Class — Importance 4, SM, ADOPT.** The sum of method
complexities in a class. radon already yields class to methods to per-method
cyclomatic complexity (verified), so this is a near-free aggregation once the
class-scope pass exists. A strong "this class does too much" signal and a direct
input to the single-responsibility composite (#27).

**11. Response For Class — Importance 3, L, TABLE.** The set of methods invocable
in response to a message equals own methods plus the methods they call, which
needs intra- and cross-class call resolution. High cost, modest marginal signal
over Weighted Methods per Class and Coupling Between Objects. Table until
call-graph infrastructure exists (it shares that cost with #28).

### Inheritance scope

**12. Depth of Inheritance Tree — Importance 3, SM, ADOPT.** Needs a cross-file
class registry (base-class resolution) that the class-scope pass builds anyway.
Deep hierarchies are a Liskov-substitution and open/closed smell. A cheap
follower.

**13. Number of Children — Importance 3, SM, ADOPT.** The reverse of the
inheritance edges Depth of Inheritance Tree already computes. Free once the
registry exists; flags fragile base classes.

**14. Polymorphism Factor — Importance 2, M, ABANDON.** A MOOD-suite metric with
weak real-world correlation to design quality, definitional ambiguity in
duck-typed Python, and cost beyond Depth of Inheritance Tree and Number of
Children. Not worth it.

### Import-graph scope (the Dependency end of SOLID — Martin's suite)

One import-graph analyzer (pure Python parsing, or a library such as grimp) is a
single M investment that lights up this entire cluster; the per-metric costs
below are the followers.

**3. Afferent Coupling / 4. Efferent Coupling — Importance 4, SM, ADOPT.**
Afferent (who depends on me) and Efferent (who I depend on) coupling are the
reverse and forward degree of each module node — the raw edges everything else
here is built from.

**5. Instability — Importance 4, XS, ADOPT.** Efferent coupling divided by the sum
of afferent and efferent coupling. A pure derivation and the single most useful
directional-coupling number.

**6. Abstractness — Importance 4, SM, ADOPT.** The ratio of abstract types
(abstract base classes, `Protocol`s, classes bearing an abstract method) to total
classes per module. Needs a documented definition (hence SM), and it is the
second Main-Sequence axis plus a dependency-inversion input.

**7. Distance from the Main Sequence — Importance 4, XS, ADOPT.** The absolute
value of abstractness plus instability minus one. Once abstractness and
instability exist, this is arithmetic — and it yields the most communicative
architecture picture antipasta could ship: the Main-Sequence scatter, a natural
new report view.

**17. Package Coupling — Importance 3, SM, ADOPT.** Roll the module graph up to
package nodes; incoming and outgoing package edges. A free aggregation.

**16. Package Cohesion — Importance 3, M, TABLE.** Package-level cohesion derived
from member Lack of Cohesion of Methods and Coupling Between Objects; wait until
those class-scope metrics exist to roll them up.

**18. Dependency Cycles — Importance 5, M, ADOPT.** Strongly-connected-component
detection on the import graph. The most *actionable* single output in the whole
table: "these N modules form an import cycle" is a concrete, fixable defect. If
antipasta adopts one thing from this list, it is this.

**19. Acyclic Dependencies Principle — Importance 5, XS, ADOPT (merged into #18).**
This principle is violated exactly when a cycle exists; report cycles *as*
violations of it. Same computation, principle-framed.

**20. Stable Dependencies Principle — Importance 4, XS, ADOPT.** Each edge should
point toward equal-or-greater stability (lower instability). A per-edge
directional check, cheap once instability exists.

**15. Modularity Index — Importance 2, L, ABANDON.** A non-standard research
composite of size, complexity, cohesion, and coupling with no agreed formula.
Every ingredient is already reported individually and more legibly; a synthetic
single number would obscure rather than clarify.

### Complexity and maintainability (mostly shipped)

**8. Cyclomatic Complexity — 3, shipped.** · **9. Halstead metrics — 2, shipped.**
· **21. Maintainability Index — 2, shipped.** The existing baseline; the SOLID
composites build on them.

**22. Comment Density — Importance 2, XS, ADOPT.** Comment lines divided by code
lines; lizard and radon already expose comment counts. Nearly free — a weak but
real documentation signal, droppable in anytime, independent of any new scope.

### Version-control scope (evolutionary coupling — one `git log --numstat` miner)

Opt-in by design (a `--vcs` mode), cached per commit range, never on the default
hot path — this respects priority (i) latency. This phase also subsumes the
previously-deferred git-churn hotspot scatter.

**23. Code Churn — Importance 3, M, ADOPT (version-control phase).** Lines added
and removed per file over a window. Mild alone; multiplied by complexity it is the
canonical hotspot map ("complex and volatile equals fix this first"), which pairs
directly with the treemap.

**24. Change Coupling — Importance 4, M, ADOPT (version-control phase).** Files
that change together across commits. Empirically the *strongest* coupling signal
that exists, and it sees couplings static analysis structurally cannot (a config
file and its consumer, for instance). The highest-value version-control metric;
adopt it alongside churn.

**26. Commit Frequency — Importance 1, XS, TABLE (churn sub-stat).** A byproduct of
the churn miner; keep it as a hotspot sub-statistic, not a headline metric.

**25. Temporal Cohesion — Importance 2, XL, ABANDON.** "Components modified
together serve the same purpose" fuses co-change (measurable) with intent (not).
Change Coupling already captures the measurable half honestly; the rest is
unmeasurable.

### Design-principle composites (the SOLID payoff — only as good as their inputs)

**27. Single Responsibility violation index — Importance 3, SM, TABLE (compose
later).** The most on-brand output: high Lack of Cohesion of Methods, high
Weighted Methods per Class, and high line count together mean a class doing too
much. Marked TABLE only in the *sequencing* sense — it is a pure composition of
#1, #10, and line count, so it lands the moment those do, and it is arguably the
flagship to demo first. (Reviewer's note: importance is defensibly a 5; scored 3
because a derived index inherits — and can amplify — its inputs' noise, so
validate it against real over-large classes before trusting the number.)

**29. Dependency Inversion compliance — Importance 5, M, ADOPT (approximate).** Do
imports target abstractions (an abstract base class or `Protocol`) or concretes?
Classify each import edge's target using the abstractness machinery (#6).
Approximate in Python (an imported name's abstractness is not always resolvable),
so label it — but even approximate, "this module depends on 12 concretes and 0
abstractions" is a strong, actionable signal.

**28. Interface Segregation violation ratio — Importance 3, XL, TABLE
(Protocol-scoped variant only).** The full version (unused interface methods per
client) needs whole-program usage tracking that duck typing defeats. A tractable
narrow variant exists: for explicit `Protocol` and abstract-base-class
definitions, measure how much of the interface each implementer or consumer
actually uses. Table until there is appetite for that scoped version; do not ship
a general score.

**30. Open/Closed flexibility index — Importance 2, XL, ABANDON.** "Extensions
versus modifications for new behavior" requires knowing intended extension points
and the modification history of adding features — a design judgment, not a static
property. Any number here would be fabricated confidence; the tool is trusted
*more* for the honest omission.

---

## Recommendation (sequencing, aligned to your priorities)

1. **Caching and parallelism first (priorities ii, i).** Content-hash each file to
   its metric JSON; parallelize the per-file passes (radon and lizard are
   embarrassingly parallel; antipasta is almost certainly single-threaded today).
   This is the substrate that makes "a lot more metrics" affordable — build the new
   analyzers as the *first* cached citizens, not a retrofit.
2. **Class-scope analyzer and the single-responsibility slice.** Lack of Cohesion
   of Methods (#1) and Weighted Methods per Class (#10) feeding the
   single-responsibility violation index (#27). Small, Python-first, immediately
   demonstrable — the fastest path to a visible SOLID payoff ("here are your
   over-large classes").
3. **Import-graph analyzer and the dependency cluster.** Efferent and afferent
   coupling, instability, abstractness, distance, package coupling, and above all
   **dependency cycles** (#18/#19) and the stable-dependencies check (#20), with
   the Main-Sequence scatter as a new report view. The largest and most
   SOLID-defining investment; about eight metrics from one graph.
4. **Second wave, cheap followers.** Depth of Inheritance Tree and Number of
   Children (#12/#13), dependency-inversion compliance (#29), comment density
   (#22).
5. **Version-control mode, opt-in.** Code churn (#23) and change coupling (#24)
   behind `--vcs`, cached per commit range.
6. **Never:** Polymorphism Factor (#14), Modularity Index (#15), Temporal Cohesion
   (#25), Open/Closed flexibility index (#30) — documented here so they are not
   re-proposed.

**If only two things ever ship from this table: dependency cycles and the
single-responsibility violation index.** They are the highest signal-per-effort
metrics antipasta could add, one per scope (import-graph and class), and both sit
squarely in the well-factored, loosely-coupled spirit you are aiming at.
