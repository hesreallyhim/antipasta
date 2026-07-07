# Narrative Index — measuring code that reads like pseudo-code

Design sketch, 2026-07-03. Owner's brief: "I want a level of abstraction where
the code reads like pseudo-code — or rather I want a way to *measure* that type
of thing." Explicitly **not** cognitive complexity ("everyone does cognitive
complexity") — this is a different axis: cognitive complexity punishes what is
hard to follow; the Narrative Index rewards what reads well. A function can have
cognitive complexity 0 and still be an unreadable wall of subscripts and
arithmetic; a function can branch and still read like a story.

## The canonical example (the bar to measure against)

The owner's example, lightly translated:

```python
def should_accept_new_users():
    users = get_users_by_name()
    filtered_users = filter_users(users)
    if is_too_many_users(filtered_users):
        return False
    else:
        return True
```

What makes this pseudo-code-like is not one property but four independent ones:

1. Every statement advances the story by a **named step** — a call to a
   semantically named helper, never raw computation.
2. **One idea per line** — no nested calls, no `f(g(h(x)))`, no arithmetic
   smuggled into an argument.
3. The intermediates are **named and flow linearly** — `users` becomes
   `filtered_users` becomes the answer; each name is written once and read once,
   like pronouns in prose.
4. The **names themselves carry meaning** — `get_users_by_name` over
   `get_user_fn`, `should_accept_new_users` over `check2`. And meaning is
   *contextual*: `foo` is a bad word in general but a fine one inside a project
   named foo-measure.

Each of these is statically measurable. That is the design: four component
metrics plus the module-level ordering check, composed into one index.

## The five components

### 1. Narration ratio (per function)

The fraction of statements that are "narrative steps": an assignment whose
right-hand side is a single call to a named function with plain-name/constant
arguments; a return of a name, constant, call, or negated call; a conditional
whose test is a single predicate call. Everything else — arithmetic statements,
comprehensions, subscript chains, boolean algebra over multiple operands,
nested calls — is computation, which belongs one level down in a named helper.

This is the Single Level of Abstraction Principle made operational: a function
should either *orchestrate* (all narrative) or *compute* (it IS the extracted
helper — small, leaf-level, exempted by size), and the ratio detects the mixed
case that reads badly.

### 2. Expression flatness (per function)

One idea per line, measured directly: for each statement, count operation nodes
(calls count 1; arithmetic, comparisons, boolean operators, subscripts, and
comprehensions count double — raw computation is heavier than a named step;
negation is free because `not exceeds_capacity(x)` reads as prose). The score is
the fraction of statements at or under the one-idea budget. `f(g(h(x)))` fails;
three lines with named intermediates pass.

### 3. Pipeline linearity (per function)

The fraction of local names that are assigned exactly once and consumed exactly
once — the "explaining variable" pattern that makes bodies read as *then...
then... then*. Loop accumulators and reused temporaries lower it. (A refinement
worth testing on real code: also require definition and use to be adjacent-ish,
so a name introduced at the top and consumed twenty lines later doesn't count
as narrative flow.)

### 4. Name clarity (per identifier, aggregated per function)

The context-aware naming grade the owner asked for. Per identifier:

- **Split** into words (snake_case and camelCase splitting is a solved problem —
  the identifier-splitting literature calls this Samurai-style splitting;
  concatenated words are handled by the split, not fought).
- **Lexicon hit rate**: the fraction of word-parts found in a layered lexicon —
  see below. This is where `desc` in `get_users_by_name_desc` passes (common
  abbreviation list) and `fn` in `get_user_fn` fails.
- **Grammatical form**: callables should start with a verb; predicates
  (`is_`/`has_`/`should_`/`can_`) get checked against their return type where
  inferable. A name containing `and` (`fetch_and_save`) is two responsibilities
  wearing one name — flagged.
- **Junk penalties**: a curated stop-list (`fn`, `obj`, `tmp`, `mgr`, `util`,
  `impl`, `data2`, `stuff`, `proc`, numbered names like `check2`) that no
  lexicon should launder.

**The layered lexicon (the context-awareness mechanism):**

1. An embedded English wordlist (shipped with antipasta, offline, a few hundred
   kilobytes — same posture as the vendored d3).
2. A common programming-abbreviation list (`ctx`, `cfg`, `db`, `idx`, `desc`,
   `init`, `args`, `env`...), curated and versioned.
3. A **project lexicon harvested from anchor names only**: the package name,
   module names, class names, configuration keys, dependency names, README
   title words. This is how `foo` becomes a good word inside foo-measure —
   the project itself taught us its vocabulary. Anchors only, deliberately:
   harvesting from *all* identifiers would let junk self-whitelist (`fn` used
   40 times would become "vocabulary").
4. A user allowlist in `.antipasta.yaml` for domain terms the harvest misses.

**What this is not:** semantic *accuracy* — verifying the name matches what the
body does — is not statically decidable in general. The closest honest static
approximation is the linguistic-antipattern family (Arnaoudova et al.): a
`get_*` that returns nothing, an `is_*` returning a list, a plural name
returning a scalar, a "setter" that reads. Those specific name-behavior
contradictions ARE checkable and worth adopting. Full semantic verification is
model-assisted territory — a possible future opt-in mode, never the static
core, and never silently blended into this score.

> **Addendum (2026-07-04):** that opt-in mode now has a design — the blind
> reading test (a model summarizes the function with all helpers hidden; an
> informed reading with callees visible is the ground truth; a judge compares).
> See `docs/design/llm-assisted-evaluation.md`.

### 5. Step-down ordering (per module)

Already adopted in the review's Round 2: the fraction of intra-module calls
whose callee is defined *below* the caller — Robert Martin's newspaper rule,
and literally the "reads top to bottom" property. It lives at module scope
while components 1–4 live at function scope; the report can show both.

## Probe results (implemented, not speculated)

A working probe of components 1–4 lives at
`tests/temp/narrative_index_probe.temp.py` (~230 lines, standard library only,
run with `venv/bin/python`). Four versions of the same behavior:

| Sample | Narration | Flatness | Pipeline | Names | Composite |
|---|:--:|:--:|:--:|:--:|:--:|
| Owner's example, as written | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| Tightened variant (`return not exceeds_capacity(...)`) | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| Inlined twin — identical behavior, zero extraction | 0.00 | 0.40 | 0.00 | 0.25 | **0.16** |
| Junk-named twin — prose *shape*, meaningless names | 1.00 | 1.00 | 1.00 | 0.00 | **0.75** |

Three findings:

1. **The metric discriminates.** Same behavior, 1.00 versus 0.16, purely on how
   it's written. That is exactly the axis the owner wants to measure, and no
   shipped metric captures it (the inlined twin's cyclomatic complexity is a
   modest 4 — conventional metrics shrug at it).
2. **The components are independent.** The junk-named twin proves structure and
   naming are separate axes — it aces one and zeroes the other.
3. **Design consequence: components must be separately thresholdable.** The
   junk-named twin's 0.75 composite shows equal-weight averaging lets good
   structure mask garbage names. Antipasta's existing per-metric threshold
   model is the fix, for free: ship `narration_ratio`, `expression_flatness`,
   `pipeline_linearity`, `name_clarity` (and module-level `step_down_ordering`)
   as first-class metrics, each with its own configurable floor, plus a
   composite `narrative_index` used for treemap coloring and trend lines. A
   function then *violates* on the failing component by name — which is also
   the actionable message ("names are the problem here"), not a mushy blended
   score.

## What is a leaf? Classification, not exemption (2026-07-04 revision)

The first cut of this document punted on leaves ("exempt by size or by being at
the bottom of the call graph"). The owner pushed: how do you *capture* a leaf,
and is the strict policy — "only leaves may perform computation" — the right
one? Working it through changed the design.

**Capture leaves by content, not by call-graph position.** A function is a
**computer** (a leaf) if its body makes zero *narrative calls* — calls to
project-defined callables — after three exclusions: self-recursion (a recursive
kernel is still a leaf), ambient vocabulary (logging, metrics, assertions — a
configured list, eventually auto-detected as "called from everywhere" via
call-graph fan-in), and builtins/third-party calls (using `len` or a library is
vocabulary, not orchestration of *your* code). Position-based leafness ("nothing
below me in the call graph") is the same idea stated globally — but it requires
whole-program call resolution, which breaks per-file caching and fights the
latency priority. Content-based leafness is local, cacheable per file-hash, and
causally prior anyway: you are a leaf *because* you call nothing project-level,
not because of where you happen to sit.

**The policy, reframed.** "Only leaves may compute" is right as an invariant but
wrong as the enforcement rule — enforced directly it punishes leaves for
existing and gives mushy diagnostics. Enforce it as two local rules that jointly
imply it:

1. **No function may both narrate and compute** (the MIXED class below is the
   violation — two abstraction altitudes in one body).
2. **Leaves must be small** (leaf budgets: statement cap, nesting cap ≤ 1,
   relaxed flatness; the narration and name-verb floors do not apply).

So every function classifies into one of four:

| Class | Definition | Judged by |
|---|---|---|
| **narrator** | project calls, no raw computation | narration floor, name clarity, step-down, **step budget** |
| **computer** (leaf) | raw computation, no project calls | leaf budgets: statement cap, nesting cap, cognitive complexity, name clarity |
| **MIXED** | both in one body | the violation itself — "split altitudes" |
| trivial | under 3 statements | nothing — too small to classify |

**Budgets at every altitude (owner refinement, 2026-07-04).** A narrator built
from 25 semantically perfect helper calls in a row still fails — prose has
paragraphs, and 25 sequential steps at one level means missing intermediate
chunks (the refactor: group the steps into named phases). So narrators carry a
**step budget** (extreme profile: about 9 narrative steps; the 7±2 band),
symmetric with the computers' statement/nesting budget. Note that *no other
metric can see this defect*: a 25-step run-on narrator has cognitive complexity
0 and cyclomatic complexity 1, and if a generic line cap catches it that's
coincidence, because the unit that matters is narrative steps, not lines. This
is also the function-scale instance of a principle that now unifies several of
the owner's metrics: **bounded fan-out at every altitude** — 5–7 children per
package (Module Tree Shape), 5–9 steps per narrator, method-count bounds per
class (Weighted Methods per Class), 4–5 parameters per function (arity). One
aesthetic, four scales.

**Probe results with classification and budgets** (the probe implements both):

| Sample | Class | Steps | Budget | Composite |
|---|---|:--:|:--:|:--:|
| Owner's example | narrator | 5 | ok | 1.00 |
| Tightened variant | narrator | 3 | ok | 1.00 |
| Inlined twin | **computer** | 5 | **over** (nesting 2) | 0.16 |
| Junk-named twin | narrator | 3 | ok | 0.75 |
| Half-refactored (`fetch_users` then a comprehension + arithmetic on the result) | **MIXED** | 3 | — | 0.50 |
| The extracted leaf itself (`exceeds_capacity`, three tidy statements) | computer | 3 | ok | 0.60 |
| Run-on narrator — 12 perfect, well-named steps in a row | narrator | 12 | **over** | 1.00 |

The last row is the punchline for budgets: **a perfect composite and a
violation at the same time.** Every defect in the table routes through its own
named check — junk names fail the name-clarity floor, the half-refactored
function fails by class (MIXED), the inlined twin fails the leaf nesting
budget, the run-on narrator fails the step budget — and each check's name *is*
the refactoring instruction.

Two findings worth naming:

- **The inlined twin classifies as a computer — correctly.** By content it calls
  no project code; its sin is not altitude-mixing but being an *oversized,
  nested leaf* (six statements, nesting depth 2). It gets flagged by leaf
  budgets, and the diagnostic that falls out is the right one: "extract and
  name this computation," not "you mixed abstraction levels." Meanwhile the
  half-refactored sample — the most common real-world shape, where someone
  extracted one step and stopped — is what MIXED catches.
- **The extracted leaf's low narration/flatness scores are irrelevant — by
  design.** Its class exempts it from those floors; it is three clean
  statements well inside any leaf budget. This is why classification must
  precede scoring: the same numbers mean different things at different
  altitudes, and a composite that averages across classes (the 0.54) is
  meaningless. Per-class thresholds, always.

**The strictness dial still applies inside "computation."** Is
`if count > limit:` computation or prose? Most would read it as prose; extreme
Compose Method extracts `is_too_many(count)`. The classifier's notion of "raw
computation" is therefore profile-scoped — `extreme` counts any operator,
`standard` grants prose-grade status to single comparisons between named
values, emptiness tests, and one-deep attribute access, `relaxed` adds single
arithmetic operations and f-strings. The same dial governs both the narrator
floor and the MIXED trigger, so a project picks one altitude discipline and
every component honors it.

## Honesty section (what this metric is and is not)

- It measures **conformance to a style**, not comprehension truth. The
  readability literature's own caution applies (models of how code *looks*
  correlate weakly with measured understanding). But unlike generic readability
  models, this one encodes the owner's explicit, chosen house style — Compose
  Method, one level of abstraction, step-down ordering — where conformance is
  the point.
- It is **gameable** (name a garbage function `fetch_users` and narration
  passes). The linguistic-antipattern checks catch the crude cases; review and
  tests catch the rest. Label it a style metric, not a quality guarantee.
- **Leaf handling is classification, not exemption** — *someone* has to do the
  arithmetic, and the metric must not punish the leaves for existing. See "What
  is a leaf?" above: content-based trimodal classification (narrator / computer
  / MIXED), leaf budgets instead of narration floors for computers.
- **Python-first.** Components 1–3 and 5 are one syntax-tree walk (they ride
  the class-scope analyzer pass from the review's capability B). Name clarity
  needs the lexicon build — a cheap whole-program pass, cached per commit like
  the import graph. JavaScript/TypeScript later via a tree-sitter-style parse
  if demand appears; lizard's function-level view is not enough for this.

## Naming

Working title **Narrative Index** (per-function composite; components exposed
individually). Alternatives considered: prose score (too cute), newspaper score
(better reserved for the module-level step-down component), pseudo-code index
(reads as pejorative). Owner has final say.

## Relationship to the SOLID review

This deepens Round 2's "readability profile": abstraction purity and step-down
ordering from that table become components 1 and 5 here; expression flatness,
pipeline linearity, and name clarity are new. Infrastructure cost is unchanged —
everything rides the capability-B syntax-tree pass plus one cached lexicon
build. Complexity: **M** for components 1–3 and 5 together, **M** for name
clarity with its lexicon machinery. Importance to the owner's stated ideal: 5.
