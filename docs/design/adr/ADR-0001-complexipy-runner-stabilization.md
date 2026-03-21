# ADR-0001: Complexipy Runner Stabilization for Day-to-Day Reliability

- Status: Proposed
- Date: 2026-03-21
- Owner: antipasta maintainers
- Scope: Current Python CLI (`metrics`, `stats`) on `main`

## Context

`antipasta` currently depends on `ComplexipyRunner` for cognitive complexity metrics.
In real local usage, cognitive metrics can silently disappear because runner availability is determined by invoking a bare `complexipy` command on `PATH`.

In environments where the active runtime is `venv/bin/python` but shell `PATH` resolves `complexipy` to a missing or mismatched shim (for example pyenv shims), the runner is marked unavailable even though `venv/bin/complexipy` exists.

There is also operational noise from `complexipy.json` output files being created in the working directory.

## Problem Statement

We need a reliable, low-risk fix for daily use that:

1. Uses the same environment as the active Python interpreter.
2. Prevents workspace artifact noise from Complexipy output.
3. Preserves current behavior for other metrics and CLI workflows.
4. Minimizes implementation risk before broader language-agnostic/Rust refactor work.

## Decision Drivers

- Fast path to stable developer experience.
- Avoid correctness risk of re-implementing cognitive complexity now.
- Keep scope aligned to a patch-level improvement on current architecture.
- Keep future migration path open for language-agnostic engine work.

## Options Considered

### Option A: Bundle/Vendor Complexipy now (MIT)

Pros:
- Maximum control over runtime behavior and packaging.
- Can patch behavior directly if needed.

Cons:
- Introduces ownership burden (upstream tracking, local patch maintenance).
- Larger immediate change surface than needed for this fix.

### Option B: Implement in-house cognitive complexity analyzer now

Pros:
- Full control; no subprocess artifact model.
- Better long-term strategic alignment with language-agnostic core.

Cons:
- Highest risk and longest timeline.
- Requires substantial validation and parity testing.

### Option C: Stabilize current integration (chosen)

Pros:
- Smallest safe change with immediate impact.
- Preserves known analyzer semantics.
- Addresses both reliability and artifact-noise issues.

Cons:
- Keeps external-tool dependency in the short term.

## Decision

Adopt **Option C** for the current release cycle.

We will keep using Complexipy as the cognitive analyzer, but harden invocation and output handling.

## Proposal: Implementation Plan

### 1) Deterministic executable resolution

Update `ComplexipyRunner` to resolve `complexipy` in this order:

1. Sibling executable next to active interpreter:
   - Unix/macOS: `Path(sys.executable).with_name("complexipy")`
   - Windows: `Path(sys.executable).with_name("complexipy.exe")` (with fallback to `.with_name("complexipy")`)
2. Fallback: `shutil.which("complexipy")`.

If no executable is found or health check fails, mark runner unavailable.

### 2) Isolate Complexipy output artifacts

Run complexipy subprocess with:

- `cwd` set to a temporary directory (`tempfile.TemporaryDirectory()`),
- absolute target file path argument,
- parse `complexipy.json` from temp directory only.

Result: no `complexipy.json` file in repository/workspace.

### 3) Availability and failure signaling

- Keep default runtime behavior as **warn-and-continue** for local ergonomics.
- Add clear warning messaging when cognitive complexity is configured/requested but unavailable.
- Avoid silent omission of cognitive metrics in command output summary.

### 4) Regression tests

Add tests that verify:

- cognitive metrics are available when `venv` has complexipy, even if shell `PATH` is not globally aligned,
- running `metrics`/`stats` does not leave `complexipy.json` in project root,
- existing cognitive-focused tests remain green under hardened invocation.

### 5) Validation gates

Run and require:

- `make lint`
- `make type-check`
- `make test`
- one smoke command: `venv/bin/antipasta stats -p "src/**/*.py" --by-directory -m cog`

## Consequences

### Positive

- Reliable cognitive metrics in typical `venv` workflows.
- No noisy output artifacts in repo roots.
- Small, patch-suitable change for near-term productivity.

### Negative / Tradeoffs

- Continues dependency on external CLI behavior.
- Does not advance full language-agnostic analyzer architecture directly.

## Out of Scope

- Vendoring/forking Complexipy code in this iteration.
- Implementing an in-house cognitive complexity analyzer.
- Rust refactor and universal analyzer redesign.

## Follow-up Trigger

Revisit vendoring or in-house analyzer if any of the following recur after this patch:

- recurring runtime incompatibilities across environments,
- persistent subprocess/output instability,
- performance constraints that require direct library/API integration.

