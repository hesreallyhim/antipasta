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

The metric treats names as contracts. A predicate-shaped name is treated as a yes/no contract, and narrowing annotations such as `TypeGuard` satisfy it. A fetcher-shaped name is treated as a returned-value contract. An `_and_` name is treated as a multi-responsibility contract. Stub bodies (`pass`, `...`, `raise NotImplementedError`) are declarations rather than behavior and are never flagged.

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

A module-level name is mutable state by evidence, not by spelling: some function in the module writes to it, it is rebound more than once at module level, or it is bound to a mutable container waiting to be filled. Caches, registries, feature flags, and plugin tables qualify. A compiled regex, a type alias, or a sentinel assigned once and only read is a constant even when written in lowercase.

## Lack Of Cohesion

`lack_of_cohesion` counts the responsibility clusters inside a class. Methods join a cluster when they touch the same field (through `self` or `cls`), when one calls the other or reads a property the other defines, or when both call the same inherited method. A value above one means the class holds more than one group of methods that share nothing with each other.

Three kinds of method are deliberately left out of the count. Stub methods such as abstract declarations and no-op hooks touch no state, so an interface with fifty declared methods is not fifty responsibilities. A stateless helper that touches no field and shares nothing with a sibling is a method parked on the class, not a reason for the class to change; these are counted separately in the row's details. And a group consisting only of `__init__` is setup, not a responsibility. A class with no concrete methods gets no row rather than a misleading count.

These rules were calibrated against twelve libraries. Before them, 187 of 1,022 classes had more than one component, most of them interfaces and classes with a few stateless helpers; after, 37 do, and they are the splits a maintainer would recognize, such as `unittest.TestCase` dividing into instance lifecycle and class-level cleanup, or pydantic's `BaseModel` into construction, dumping, and schema groups.

For example, a class whose persistence methods share `self.connection` while its rendering methods share `self.template` forms two structural groups under one class name. The metric is approximate because field sharing is only a proxy for conceptual unity.

## Coupling Between Objects

`coupling_between_objects` counts the distinct classes in the analyzed project that a class body names, whether defined in the same module or imported from another analyzed module. It asks how many other classes this class knows about.

The metric names classes whose bodies mention many project collaborators. It is approximate because no type inference is performed: a collaborator reached only through an attribute chain or a return value is not seen.

## Single Responsibility Index

`single_responsibility_index` scores a class by how many extra reasons to change it carries. The direct evidence for a responsibility split is the number of disconnected method groups, so that is the primary term; method complexity and class size only scale it, so that a split between two heavy halves outranks a split between two accessors.

The formula is intentionally transparent:

```text
(cohesion_components - 1) * (1 + weighted_methods / 30) * (1 + statements / 60)
```

A class with a single method group scores zero however large it is. A very large cohesive class is a size finding, reported separately by weighted methods and statement counts, not a responsibility finding. Interfaces have no concrete methods and score zero as well.

## Test-Smell Metrics

`assertions_per_test`, `mock_call_assertions`, and `big_literal_assertions` identify three static test shapes.

`assertions_per_test` names tests with many assertion sites. `mock_call_assertions` names tests that assert call counts or call arguments on mocks. `big_literal_assertions` names tests that compare against large inline literal values.

These rows name tests whose static shape depends on broad assertion sets, implementation-level mock expectations, or large literal expected values.

## Marker And Comment Density

`marker_density` counts TODO/FIXME/HACK/XXX markers per thousand physical lines. It names the concentration of unresolved work markers in a file.

`comment_density` measures how much of a file is comment text. It names the proportion of physical lines devoted to comments rather than executable or declarative code.
