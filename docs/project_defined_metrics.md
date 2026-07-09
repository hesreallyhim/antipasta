# Project-Defined Metrics Explained

Antipasta includes familiar metrics such as cyclomatic complexity, line counts,
Halstead metrics, and the Martin package metrics. It also includes metrics that
are less standardized: they turn design advice about readability, abstraction,
names, tests, and class responsibility into concrete signals.

These are not meant to imply that the ideas are private inventions. Most of the
underlying principles are old and recognizable: small functions, one level of
abstraction, Law of Demeter, low coupling, high cohesion, intention-revealing
names, acyclic dependencies, and tests that specify behavior rather than
implementation trivia. The project-defined part is the decision to make those
principles measurable in this particular way.

Treat these rows as diagnostic instruments. A high value is a prompt to inspect
the code, not proof that the code is wrong. A low value is a reason to be less
worried, not proof that the design is good. They are most useful for ranking
refactoring candidates, finding surprising outliers, and making team preferences
explicit enough to discuss.

## How To Read The Examples

The examples below are intentionally small. Real code usually has more context:
performance constraints, framework idioms, generated code, tests with fixture
setup, or domain notation that is terse because the domain itself is terse. The
metric is useful when it points to a question worth asking.

## Expression Flatness

`expression_flatness` asks whether a function is written as a sequence of
readable steps or as dense statements that each do several jobs. The value is
the fraction of a function's own statements that stay under a small operation
budget. A low score often means a reader has to parse computation, branching,
indexing, and calls all at once.

The underlying idea is not that every line must be trivial. It is that a line
should usually communicate one move in the program. When a statement both
selects data, transforms it, applies conditionals, indexes deeply, and calls
out to collaborators, the function becomes harder to scan and harder to safely
change.

Dense:

```python
def active_names(users):
    return sorted(u["profile"]["name"].strip() for u in users if u["active"] and u["profile"])
```

Flatter:

```python
def active_names(users):
    active_users = [user for user in users if user["active"] and user["profile"]]
    names = [user["profile"]["name"].strip() for user in active_users]
    return sorted(names)
```

The second version is longer, but it gives the reader named intermediate
concepts. That is the tradeoff this metric tries to make visible.

## Pipeline Linearity

`pipeline_linearity` looks for the "then, then, then" shape: local names are
assigned once and read once as the function progresses. A high score often
means the function is using explaining variables well. A low score can indicate
mutation-heavy code, reused scratch variables, or a function where data flows
in circles.

This metric is not anti-variable. It is almost the opposite: it rewards local
names that explain a step and then hand the result to the next step.

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

The second version is easier to debug because each name records a particular
stage of the computation.

## Narrative Mixed Functions

`narrative_mixed_functions` counts functions that both orchestrate project-level
steps and perform raw computation in the same body. This is an operational
version of "one level of abstraction per function." A narrator function should
tell the story by calling named steps. A computer function should do the local
calculation. A mixed function does both, so the reader has to shift altitude.

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

The point is not that list comprehensions are bad. The point is that
`publish()` now reads at one altitude: fetch, filter, render. The filtering
details have a name and a home.

## Narrator And Computer Budgets

`narrator_budget_exceeded` and `computer_budget_exceeded` apply size limits to
the two function roles used by the narrative metric.

A narrator has a step budget because orchestration can become a run-on sentence:
fetch this, validate that, enrich the result, dispatch three side effects, log
four events, and return a DTO. Past a point, even individually clear steps stop
forming a clear story.

A computer has a statement and nesting budget because leaf calculations should
stay small. If a leaf function is long or deeply nested, it is often hiding
several smaller concepts that could be named.

The budgets are intentionally simple. They do not know whether a function is
business critical or performance sensitive. They mark functions that deserve
human attention.

## Step-Down Ordering

`step_down_ordering` measures whether a module reads top-down: callers appear
before the helpers they call. This is the "newspaper" or "table of contents"
style of source organization. The public or high-level function appears first,
then its supporting details appear below it.

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

This is deliberately stylistic. Some teams prefer alphabetic order, framework
order, or grouping by lifecycle hook. The metric exists because top-down
ordering is a real readability convention, not because it is the only valid
one.

## Name Clarity

`name_clarity` scores callable names against a layered vocabulary: common
English words, code vocabulary, project anchor words, and configured allowlist
terms. It is designed to catch names that are difficult to pronounce, decode,
or search for.

Low-scoring names tend to look like `chk`, `proc2`, `fn_hlpr`, or `do_stuff`.
High-scoring names tend to expose intent: `collect_active_users`,
`render_invoice`, `normalize_token`, `load_project_snapshot`.

This metric is necessarily approximate. A short domain word can be perfectly
clear inside a particular project, and a long English name can still be vague.
The allowlist exists because good names often include product names, protocol
terms, or domain-specific language that a general dictionary will not know.

## Naming Antipatterns

`naming_antipatterns` counts cases where a function name makes a behavioral
promise that the implementation contradicts. The current checks are deliberately
conservative: they fire only on positive evidence, such as a predicate-looking
name returning a non-boolean annotation, a getter/fetcher returning nothing, or
a name with `_and_` that advertises two jobs.

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

The issue is not grammatical purity. Names are contracts. When a name says
"predicate," "query," or "one job," callers build expectations around that
contract.

## Message Chain Depth

`message_chain_depth` measures long reach-through chains such as
`order.customer.account.owner.email`. This is a Law of Demeter style signal:
the current function may know too much about the shape of other objects.

Long chains are not always wrong. Fluent APIs, builders, query objects, and
test assertions often use chains intentionally. The smell is strongest in
business logic where a function repeatedly reaches through several layers of
another object's internals.

Reach-through:

```python
email = order.customer.account.owner.email
```

Encapsulated:

```python
email = order.owner_email()
```

The second version moves knowledge about the object's internal path closer to
the object that owns it.

## Global State Reach

`global_state_reach` counts mutable module-level names a function touches. It
is a hidden-dependency signal: the function's behavior depends on state that is
not visible in its parameters.

Sometimes global state is a deliberate cache, registry, feature flag store, or
framework integration point. The metric does not forbid that. It tells you
which functions are coupled to those shared names so that tests, refactors, and
concurrency changes can be more careful.

## Exception Discipline

`exception_discipline` counts bare, silent, or overly broad exception handlers
that do not re-raise. The principle is that failure handling should preserve
information and make intent explicit.

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

There are legitimate boundary cases: best-effort cleanup, optional telemetry,
or compatibility shims. Those cases should usually be local and obvious.

## Lack Of Cohesion

`lack_of_cohesion` counts disconnected groups of methods inside a class, using
shared fields and local method calls as the connecting evidence. A value above
one suggests the class may contain multiple responsibilities that do not
communicate with each other.

For example, a class with `load_user()` and `save_user()` methods using
`self.connection`, plus `render_invoice()` and `format_currency()` methods
using `self.template`, may be two objects wearing one class name. Cohesion is
about whether the methods form one concept, not whether the class is large.

The metric is approximate because static field access is only a proxy for
conceptual unity. It is still useful because unrelated responsibilities often
leave exactly this structural trace.

## Coupling Between Objects

`coupling_between_objects` approximates class-level coupling by counting
distinct imported names referenced inside the class body. It is a local version
of the larger coupling question: how many external collaborators must this class
know about?

A class with many imported collaborators can still be correct, especially at an
integration boundary. But high coupling raises the cost of change: more imports
mean more reasons the class might break when other modules move, rename, or
change behavior.

## Single Responsibility Index

`single_responsibility_index` is a composite pressure score. It combines three
signals:

- cohesion components: how many disconnected method groups the class appears to
  contain
- weighted methods: how much method complexity is attached to the class
- class statements: how much method body volume the class owns

The formula is intentionally transparent:

```text
cohesion_components * (1 + weighted_methods / 30) * (1 + statements / 60)
```

The score is not a formal proof of SRP compliance. It is a sorting heuristic:
classes that are disconnected, complex, and large should float toward the top
of a refactoring list.

## Test-Smell Metrics

`assertions_per_test`, `mock_call_assertions`, and `big_literal_assertions` are
static signals for brittle tests.

Many assertions in one test can mean the test is checking a whole scenario
diff rather than one behavior. Mock call assertions can over-specify
implementation details instead of externally visible outcomes. Large inline
literals can become hand-written snapshots without snapshot tooling, update
workflow, or review discipline.

None of these is categorically wrong. A high-value integration test may
legitimately assert many facts. A protocol adapter may need to prove that it
calls a dependency with exact wire-format arguments. The metric's job is to
find tests where that brittleness may be accidental.

## Marker And Comment Density

`marker_density` counts TODO/FIXME/HACK/XXX markers per thousand physical
lines. It is a debt inventory signal. The best interpretation is trend-based:
is the project accumulating unresolved markers faster than it resolves them?

`comment_density` measures how much of a file is comment text. Extremely low
comment density can be fine in self-explanatory code. Extremely high comment
density can be fine in protocol, security, or numerical code where the "why"
matters. Outliers are worth inspecting because comments often reveal either
careful explanation or code that is too confusing to stand on its own.

## Why These Are Still Metrics

The fact that a metric encodes judgment does not make it useless. Cyclomatic
complexity also encodes a judgment: that branch count is a useful proxy for
test and comprehension burden. The difference is that cyclomatic complexity has
a longer history and a more standardized definition.

Project-defined metrics are useful when they are:

- named honestly
- documented clearly
- cheap to compute
- stable enough to compare over time
- treated as prompts for review rather than automatic moral verdicts

That is the intended role of these metrics in antipasta.
