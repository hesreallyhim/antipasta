## Expression Flatness

`expression_flatness` measures how often a function's statements stay within a small operation budget. It is meant to find statements that force the reader to understand several ideas at once: selection, transformation, indexing, branching, and collaborator calls.

The metric names statements that hide intermediate concepts instead of exposing them as local names.

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

The flatter version names two intermediate steps: choosing active users and extracting names.

## Pipeline Linearity

`pipeline_linearity` measures whether local names form a one-way pipeline: assigned once, read once, then handed to the next step. High linearity often corresponds to code that reads as "first this, then this, then this."

The metric drops when a function mutates scratch variables repeatedly or sends data through loops and branches that obscure the path from input to output.

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

The second version names each transition in the computation.

## Narrative Mixed Functions

`narrative_mixed_functions` counts functions that mix orchestration with local computation. It is a measurable form of "one level of abstraction per function." A narrative function advances the story by calling named project steps. A computational function performs a local calculation. A mixed function does both in the same body.

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

The separated version makes `publish()` call named project steps: fetch, filter, render. The filtering rule is represented by `keep_active()`.

## Narrator And Computer Budgets

`narrator_budget_exceeded` and `computer_budget_exceeded` apply size limits to the roles used by the narrative classifier.

A narrator exceeds its budget when an orchestration function contains too many steps. The named shape is a long procedural sequence without smaller named phases.

A computer exceeds its budget when a leaf calculation has too many statements or too much nesting. The named shape is a leaf function with multiple smaller rules embedded in its body.

These rows name functions whose role is identifiable but whose body exceeds the configured role budget.

## Step-Down Ordering

`step_down_ordering` measures whether functions in a module tend to call helpers defined below them. This supports a top-down reading order: public or high-level functions first, details later.

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

The metric names modules whose intra-module call order diverges from that top-down shape.

## Name Clarity

`name_clarity` scores callable names against a layered vocabulary: common English words, code vocabulary, project anchor words, and configured allowlist terms. It looks for names that are hard to pronounce, decode, search for, or distinguish from each other.

Low-scoring names often look like `chk`, `proc2`, `fn_hlpr`, or `do_stuff`. High-scoring names expose intent: `collect_active_users`, `render_invoice`, `normalize_token`, `load_project_snapshot`.

Allowlisted product names, protocol terms, abbreviations, and specialized nouns are treated as project vocabulary.

## Naming Antipatterns

`naming_antipatterns` counts names whose grammar conflicts with visible behavior. The checks are conservative: they fire when there is positive evidence, such as a predicate-looking name returning a non-boolean annotation, a getter/fetcher returning no value, or an `_and_` name advertising two jobs.

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

The metric treats names as contracts. A predicate-shaped name is treated as a yes/no contract. A fetcher-shaped name is treated as a returned-value contract. An `_and_` name is treated as a multi-responsibility contract.

## Message Chain Depth

`message_chain_depth` measures long reach-through chains such as `order.customer.account.owner.email`. Each attribute or call hop adds another level of object-boundary traversal.

Reach-through:

```python
email = order.customer.account.owner.email
```

Encapsulated:

```python
email = order.owner_email()
```

The metric names code that reaches through a sequence of collaborators instead of asking one object for the needed value.

## Global State Reach

`global_state_reach` counts mutable module-level names a function touches. It is a hidden-dependency signal: the function's behavior depends on state that is not visible in its parameters.

The named state includes caches, registries, feature flags, plugin tables, framework integration points, and other mutable names stored at module scope.

## Exception Discipline

`exception_discipline` counts bare, silent, or overly broad exception handlers that do not re-raise. It names handlers that discard failure information or hide error-handling intent.

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

The metric names handlers that catch an error and then erase it without a narrow exception type, a visible recovery action, or a reraised exception.

## Lack Of Cohesion

`lack_of_cohesion` counts disconnected groups of methods inside a class, using shared fields and local method calls as connecting evidence. A value above one means the class graph split into more than one method group.

For example, a class whose persistence methods share `self.connection` while its rendering methods share `self.template` forms two structural groups under one class name. The metric is approximate because field sharing is only a proxy for conceptual unity.

## Coupling Between Objects

`coupling_between_objects` approximates class-level coupling by counting distinct imported names referenced inside the class body. It asks how many external collaborators the class knows about.

The metric names classes whose bodies mention many imported collaborators.

## Single Responsibility Index

`single_responsibility_index` is a composite pressure score for classes. It combines:

- cohesion components: disconnected method groups
- weighted methods: accumulated method complexity
- class statements: method body volume

The formula is intentionally transparent:

```text
cohesion_components * (1 + weighted_methods / 30) * (1 + statements / 60)
```

The score rises when a class is structurally disconnected, method-heavy, and large.

## Test-Smell Metrics

`assertions_per_test`, `mock_call_assertions`, and `big_literal_assertions` identify three static test shapes.

`assertions_per_test` names tests with many assertion sites. `mock_call_assertions` names tests that assert call counts or call arguments on mocks. `big_literal_assertions` names tests that compare against large inline literal values.

These rows name tests whose static shape depends on broad assertion sets, implementation-level mock expectations, or large literal expected values.

## Marker And Comment Density

`marker_density` counts TODO/FIXME/HACK/XXX markers per thousand physical lines. It names the concentration of unresolved work markers in a file.

`comment_density` measures how much of a file is comment text. It names the proportion of physical lines devoted to comments rather than executable or declarative code.
