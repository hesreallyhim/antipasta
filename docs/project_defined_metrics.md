# Project-Defined Metrics Explained

Antipasta reports some metrics with widely used definitions, such as
cyclomatic complexity, line counts, Halstead metrics, and package coupling.
It also reports metrics that operationalize design heuristics with local
formulas. This document explains those project-defined metrics: what they are
trying to reveal, how to interpret them, and what kind of code usually causes
them to rise.

These metrics are review signals, not verdicts. A high value means "inspect
this code"; it does not mean "this code is wrong." The most useful readings are
comparative: worst offenders in a module, trends over time, or places where a
metric disagrees with the team's intuition.

The complete metric list, supported languages, and threshold defaults live in
[`supported_metrics.md`](supported_metrics.md).

## Interpretation Rules

Use these rules when reading the project-defined metrics:

- Prefer outliers over absolutes. A value that is normal in one codebase may be
  suspicious in another.
- Treat generated code, framework glue, adapters, and performance-critical
  code as special cases.
- Look for repeated signals. A long function with poor flatness, high global
  reach, and mixed narrative/computation is more concerning than any one row.
- Use suppressions or thresholds sparingly. If many files need an exception,
  the rule or threshold probably needs adjustment.

For JavaScript and TypeScript, several design-style metrics are extracted with
a lightweight lexical analyzer. Rows that depend on source-shape recovery are
labeled approximate in `details`.

## Expression Flatness

`expression_flatness` measures how often a function's statements stay within a
small operation budget. It is meant to find statements that force the reader to
understand several ideas at once: selection, transformation, indexing,
branching, and collaborator calls.

Dense statements are not automatically bad. They are costly when the code has
no names for intermediate concepts and therefore gives the reader no place to
pause.

Dense:

```python
def active_names(users):
    return sorted(
        user["profile"]["name"].strip()
        for user in users
        if user["active"] and user["profile"]
    )
```

Flatter:

```python
def active_names(users):
    active_users = [user for user in users if user["active"] and user["profile"]]
    names = [user["profile"]["name"].strip() for user in active_users]
    return sorted(names)
```

The flatter version is longer, but it exposes two named steps: choosing active
users and extracting names.

## Pipeline Linearity

`pipeline_linearity` measures whether local names form a one-way pipeline:
assigned once, read once, then handed to the next step. High linearity often
corresponds to code that reads as "first this, then this, then this."

The metric rewards explaining variables. It tends to drop when a function
mutates scratch variables repeatedly or sends data through loops and branches
that obscure the path from input to output.

Less linear:

```python
def summarize(order):
    total = 0
    for item in order.items:
        total += item.price
    total = apply_discount(total, order.customer)
    total = add_tax(total, order.region)
    return total
```

More linear:

```python
def summarize(order):
    subtotal = sum(item.price for item in order.items)
    discounted = apply_discount(subtotal, order.customer)
    taxed = add_tax(discounted, order.region)
    return taxed
```

The second version leaves a short audit trail of the computation.

## Narrative Mixed Functions

`narrative_mixed_functions` counts functions that mix orchestration with local
computation. It is a measurable form of "one level of abstraction per
function." A narrative function advances the story by calling named project
steps. A computational function performs a local calculation. A mixed function
does both in the same body.

Mixed:

```python
def publish(directory):
    users = fetch_users(directory)
    active = [user for user in users if user.status == "active"]
    return render(active[:10])
```

Separated:

```python
def publish(directory):
    users = fetch_users(directory)
    active = keep_active(users)
    return render(active[:10])


def keep_active(users):
    return [user for user in users if user.status == "active"]
```

The separated version lets `publish()` stay at one abstraction level: fetch,
filter, render. The filtering rule has a name and can be tested independently.

## Narrator And Computer Budgets

`narrator_budget_exceeded` and `computer_budget_exceeded` apply size limits to
the roles used by the narrative classifier.

A narrator exceeds its budget when an orchestration function contains too many
steps. Even if each call is clear, a long sequence can become a run-on
procedure that should be split into named phases.

A computer exceeds its budget when a leaf calculation has too many statements
or too much nesting. That usually means the "leaf" is hiding multiple smaller
rules.

These rows are useful for finding functions that are readable statement by
statement but still too large at their current abstraction level.

## Step-Down Ordering

`step_down_ordering` measures whether functions in a module tend to call helpers
defined below them. This supports a top-down reading order: public or
high-level functions first, details later.

Less step-down:

```python
def normalize(user):
    return user.strip().lower()


def register(raw_user):
    user = normalize(raw_user)
    return save(user)
```

More step-down:

```python
def register(raw_user):
    user = normalize(raw_user)
    return save(user)


def normalize(user):
    return user.strip().lower()
```

This is a style signal. Alphabetic order, framework order, or lifecycle order
can be valid in some modules. The metric is most useful when a module is meant
to read as a top-down story but does not.

## Name Clarity

`name_clarity` scores callable names against a layered vocabulary: common
English words, code vocabulary, project anchor words, and configured allowlist
terms. It looks for names that are hard to pronounce, decode, search for, or
distinguish from each other.

Low-scoring names often look like `chk`, `proc2`, `fn_hlpr`, or `do_stuff`.
High-scoring names expose intent: `collect_active_users`, `render_invoice`,
`normalize_token`, `load_project_snapshot`.

Domain vocabulary matters. Product names, protocol terms, abbreviations, and
specialized nouns may need to be added to the allowlist so the metric learns
the project's language.

## Naming Antipatterns

`naming_antipatterns` counts names whose grammar conflicts with visible
behavior. The checks are conservative: they fire when there is positive
evidence, such as a predicate-looking name returning a non-boolean annotation,
a getter/fetcher returning no value, or an `_and_` name advertising two jobs.

Examples:

```python
def is_ready(user) -> list[str]:
    return user.missing_fields


def fetch_user(id):
    logger.info("fetching %s", id)


def fetch_and_save_user(id):
    user = fetch_user(id)
    return save_user(user)
```

The metric treats names as contracts. A predicate should answer a yes/no
question. A fetcher should return what it fetched. A function name should not
usually announce multiple responsibilities.

## Message Chain Depth

`message_chain_depth` measures long reach-through chains such as
`order.customer.account.owner.email`. It is a Law of Demeter style signal: the
current function may know too much about another object's internal structure.

Reach-through:

```python
email = order.customer.account.owner.email
```

Encapsulated:

```python
email = order.owner_email()
```

Long chains are common in fluent APIs, query builders, and test assertions.
They are most suspicious in business logic, where repeated chains often point
to missing methods on the object that owns the data.

## Global State Reach

`global_state_reach` counts mutable module-level names a function touches. It
is a hidden-dependency signal: the function's behavior depends on state that is
not visible in its parameters.

Global state can be deliberate: caches, registries, feature flags, plugin
tables, or framework integration points. The metric identifies the functions
coupled to that state so tests, concurrency changes, and refactors can inspect
those dependencies deliberately.

## Exception Discipline

`exception_discipline` counts bare, silent, or overly broad exception handlers
that do not re-raise. The goal is to preserve failure information and make
error-handling intent visible.

Risky:

```python
try:
    publish(event)
except Exception:
    pass
```

Clearer:

```python
try:
    publish(event)
except PublishError as error:
    logger.warning("publish failed", exc_info=error)
    raise
```

Best-effort cleanup, optional telemetry, and compatibility shims can justify
swallowing an exception. Those cases should be narrow and explicit.

## Lack Of Cohesion

`lack_of_cohesion` counts disconnected groups of methods inside a class, using
shared fields and local method calls as connecting evidence. A value above one
suggests that the class may contain multiple responsibilities.

For example, a class whose persistence methods share `self.connection` while
its rendering methods share `self.template` may be two concepts under one class
name. The metric is approximate because field sharing is only a proxy for
conceptual unity, but unrelated responsibilities often leave this structural
trace.

## Coupling Between Objects

`coupling_between_objects` approximates class-level coupling by counting
distinct imported names referenced inside the class body. It asks how many
external collaborators the class knows about.

High coupling is normal at integration boundaries. It is more concerning inside
domain logic, where a class that imports many collaborators may be coordinating
too much of the system itself.

## Single Responsibility Index

`single_responsibility_index` is a composite pressure score for classes. It
combines:

- cohesion components: disconnected method groups
- weighted methods: accumulated method complexity
- class statements: method body volume

The formula is intentionally transparent:

```text
cohesion_components * (1 + weighted_methods / 30) * (1 + statements / 60)
```

The score is a sorting heuristic, not a formal proof of Single Responsibility
Principle compliance. Classes that are disconnected, complex, and large should
rise toward the top of a refactoring review list.

## Test-Smell Metrics

`assertions_per_test`, `mock_call_assertions`, and `big_literal_assertions`
identify static signs of brittle tests.

Many assertions in one test can mean the test is checking a broad scenario
diff rather than one behavior. Mock call assertions can pin implementation
details instead of externally visible outcomes. Large inline literals can
become hand-written snapshots without snapshot tooling or review workflow.

These rows should be interpreted in context. A protocol adapter may need exact
mock-call checks. An integration test may need many assertions. The useful
question is whether the brittleness is intentional.

## Marker And Comment Density

`marker_density` counts TODO/FIXME/HACK/XXX markers per thousand physical
lines. It is a debt inventory signal. It is especially useful as a trend: is
the project accumulating unresolved markers faster than it resolves them?

`comment_density` measures how much of a file is comment text. Very low comment
density can be fine in self-explanatory code. Very high comment density can be
fine in protocol, security, or numerical code where the "why" matters. Outliers
are worth inspecting because comments often reveal either careful explanation
or code that is too confusing to stand on its own.
