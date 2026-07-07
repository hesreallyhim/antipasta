# Test-suite health — superfluous coverage and brittleness (track D)

Design note, 2026-07-04. Owner's observation, from living with agent-grown
codebases: coverage climbs monotonically because agents keep adding test
assertions and appeasing broken ones; the result is high coverage plus an
extremely brittle suite — one source change forces a hundred test edits.
Questions posed: does a "superfluous coverage / coverage redundancy" metric
exist, and if not, propose one.

## Prior art (the honest survey)

The ingredients exist in research; no standard practical score does:

- **Test-suite minimization/reduction** (Harrold et al. and a large literature):
  find a minimal subset of tests preserving coverage — greedy set-cover over
  the test×line matrix. Framed as a CI-time-saver, not a health metric.
- **Mutation subsumption** (PIT-adjacent research): tests that kill identical
  mutant sets are behaviorally redundant. Rigorous, expensive.
- **Fragile Test / Overspecified Software** (Meszaros, xUnit Test Patterns) and
  **change-detector tests** (Google Testing Blog): the smell vocabulary for
  tests that pin implementation instead of contract. Named, never metricized.

What is new here: composing these into a reportable suite-health score, and
the diagnosis that agentic coding makes it urgent — an agent's incentive
gradient (make tests pass, add tests when asked) produces exactly this
pathology unless something measures it.

## The two diseases (they need different instruments)

1. **Redundancy** — a test contributes nothing the rest of the suite doesn't
   already contribute. Harmless-looking, pure maintenance tax.
2. **Overspecification (brittleness)** — a test asserts incidental detail
   (exact strings, call counts, ordering, internal structure) rather than
   contract. This is what makes changes painful: the test *should not have
   needed to change*, but does.

High coverage multiplicity is the bridge: a function executed by 400 tests has
a 400-test blast radius for any behavior change, whether or not those tests
are individually reasonable.

## The metric family, by layer (cheapest first)

### D1 — static smells (per test file; rides the Phase 1 syntax-tree walk)

No execution, cacheable per file like every other metric:

- **Assertion count per test** (a 30-assert test is a change-detector)
- **Mock overspecification**: `assert_called_once_with` / call-count
  assertions per test; mock-to-assertion ratio
- **Exact-string assertions** on formatted/human-readable output
- **Deep-equality assertions** on large literal structures (dict/list over N
  entries — snapshot-testing by hand)
- **Near-duplicate tests**: pydry pointed at the test tree (agents copy-paste
  tests; structural Type-2 clones in tests are the purest superfluousness
  signal, and the engine already exists)

### D2 — coverage-matrix redundancy (artifact ingestion; no execution by antipasta)

coverage.py records **dynamic contexts** (which test covered which line —
pytest-cov's `--cov-context=test`). Antipasta ingests the resulting artifact
(same pattern as the discussed llvm-cov provider: antipasta stays a static
tool that reads coverage artifacts, never runs suites). From the test×line
matrix:

- **Unique-coverage ratio** per test: lines only this test covers ÷ lines it
  covers. Zero-unique tests are redundancy *candidates*.
- **Suite redundancy index**: 1 − (greedy set-cover size ÷ suite size) — "62%
  of tests add no coverage the rest doesn't provide."
- **Coverage multiplicity** per function: how many tests execute it — the
  blast-radius distribution, and the direct predictor of "a hundred tests
  break." Surfaces on the treemap as a hotspot overlay.
- Honesty label: line-coverage subsumption ≠ semantic redundancy (same lines,
  different properties asserted). These are candidates for review, not
  verdicts — the D4 upgrades harden them.

### D3 — churn coupling (rides track B's VCS miner)

The owner's lived experience, measured directly from history:

- **Test-churn ratio**: test lines changed per source line changed, windowed.
  Contract-grade suites keep it low on refactors; agent-grown suites trend ≥ 1.
- **Co-churn multiplicity**: median number of test files touched per
  source-touching commit — literally "how many tests must I edit per change."
- **Fix-vs-feature test churn**: test edits in commits that don't change
  public behavior (refactors) are the overspecification signal isolated from
  legitimate spec evolution.

### D4 — rigor upgrades (audit mode)

- **Mutation kill matrix** (mutmut/cosmic-ray artifact ingestion): identical
  kill vectors = behavioral redundancy, the rigorous form of D2.
- **LLM contract-vs-incidental classifier** (track C machinery): read the
  test plus the function's signature/docs; classify each assertion as
  contractual or incidental. Advisory, cached per content hash.
- **Disclosure-curve detection of change-detectors** (track C tier 4): if a
  test's assertion can only be reconstructed with the implementation visible
  (levels 3–4) and not from the contract (levels 0–2), the test pins
  internals *by measurement*. This unifies the two newest ideas: the same
  instrument grades code readability and test contract-fidelity.

## Composite

A per-suite **health panel**, not one number: redundancy index (D2),
blast-radius distribution (D2), churn ratio + co-churn multiplicity (D3),
smell counts (D1) — with per-metric thresholds like everything else in
antipasta. A single blended score would hide which disease you have; the
diseases have different cures (delete redundant tests vs. rewrite
overspecified ones against contracts).

## Sequencing

- D1 lands with Phase 1 (same walk, test files included by config).
- D2 is its own increment: artifact ingestion + matrix analytics (cheap,
  cache by artifact hash). Requires the project to produce a contexts-enabled
  coverage file; degrade gracefully when absent.
- D3 lands with track B (same git miner, keyed by commit range).
- D4 lands after track C exists.

Dogfood note: antipasta's own suite (357 tests, heavily agent-authored on
this branch) is the first patient. Expect real findings; that is the point.
