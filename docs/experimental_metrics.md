# Experimental Metrics

The metrics on this page are opt-in. They are not computed on a default run, no preset enables them, every row they produce carries `details.experimental: true`, and the HTML report keeps them out of the health score. They exist for projects that adopt a specific, deliberate style and want to measure adherence to it.

## Why these are held apart

The core metrics name defects most reviewers would flag: a function with too many required parameters, a class with two unrelated groups of methods, an import cycle, a copied block. The experimental metrics instead measure conformance to an opinionated model of readability, the Narrative Index, in which functions either narrate (a sequence of named steps) or compute (a small leaf), intermediate values are named once and used once, and modules read top to bottom.

That style is uncommon in practice. Benchmarked against the standard library and widely used packages (asyncio, email, unittest, click, pydantic, packaging, attrs, and others), 30 percent of non-trivial functions classify as mixed altitude, expression flatness fails on a single `is None` check, and the name-clarity ranking is led by lexicon gaps (`getchar`, `isatty`, `fileno`) rather than by unclear names. Rather than water the rules down to fit code that does not follow the style, the family is kept whole here and switched off by default. It will be revisited once the core of the library and the development process it belongs to have settled.

## Enabling

In configuration:

```yaml
experimental:
  narrative: {}          # defaults; or set budgets and gates, see below
```

For one run, without touching configuration:

```bash
antipasta report --experimental narrative --directory src/
```

The `narrative` block accepts `narrator_step_budget`, `computer_statement_budget`, `computer_nesting_budget`, `mixing_tolerance`, `allowlist`, and `name_clarity_floor`. Without gates the rows are informational; with them, counts above zero and clarity below the floor become violations.

## The Narrative Index

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
