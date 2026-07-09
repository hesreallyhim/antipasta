# Configuration Presets

Presets give users a coarse starting point when the full metric configuration is too large to author by hand.

Use `preset` to choose the philosophy and `profile` to choose strictness:

```yaml
preset: readable
profile: standard
```

You can also materialize a preset into a full editable YAML file:

```bash
antipasta config generate --preset readable --non-interactive
```

Explicit config wins over preset values. If a language metric is already configured, the preset leaves that threshold alone and only fills missing metrics for that same language. If project blocks such as `narrative` or `duplication` already contain values, the preset fills only missing fields.

## Presets

| Preset | Focus | Typical gates |
|---|---|---|
| `balanced` | Default-ish adoption path | Cyclomatic complexity, cognitive complexity, maintainability index, file-level Halstead metrics |
| `readable` | Compose-method and local readability | Cognitive complexity, function statements, message chains, boolean flags, exception discipline, global state reach, narrative budgets, name clarity |
| `compact` | Counterweight against ceremony and repetition | Source/logical lines of code, duplication ratio with normalized local names and constants |
| `architecture` | Package and import structure | Directory fan-out, dependency cycles, stable-dependencies violations |
| `testing` | Test-suite maintainability | Assertions per test, mock call assertions, big literal assertions |

## Profiles

| Profile | Meaning |
|---|---|
| `relaxed` | Easier adoption thresholds; useful while introducing a preset to an existing project |
| `standard` | The default thresholds for the preset |
| `extreme` | Stricter thresholds for teams that already agree with that preset's tradeoffs |

Presets intentionally do not enable every metric. Some metrics are advisory, some require extra context such as layer order or coverage artifacts, and some are in tension with each other.
