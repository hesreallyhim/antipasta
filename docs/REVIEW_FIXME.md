**Status Verdict**

Core implementation looks surprisingly solid, but I would not publish this branch yet. The metrics engine, CLI entrypoints, tests, type checks, package build, VCS mode, and report generation are working. The release blockers are around CI formatting, versioning/API compatibility, stale public docs/schema, and a couple of artifact/UX issues.

**Findings**

---

FIXME: USE RUFF ONLY:
venv/bin/ruff format src/antipasta tests
venv/bin/ruff check --fix src/antipasta tests
Then update CI/Makefile so the canonical checks are:
ruff format --check src/antipasta tests
ruff check src/antipasta tests
And remove black from pyproject.toml dev dependencies plus the [tool.black] section.

- [x] P0 - CI will fail Black formatting.
`venv/bin/black --check src/antipasta tests` wants to reformat 31 files. CI runs Black in [.github/workflows/ci.yml](/Users/hesreallyhim/coding/projects/antipasta/.github/workflows/ci.yml:41), but `make check-all` does not, so local checks can pass while CI fails.

---

TODO (not yet): WE'LL BUMP TO 2.0 WHEN THIS IS RELEASED

- [ ] P1 - This branch breaks published import paths while still reporting `1.1.2`.
Old imports now fail: `antipasta.core.config`, `antipasta.core.metrics`, `antipasta.core.violations`, `antipasta.core.aggregator`, etc. The adoption doc explicitly notes this as breaking in [docs/design/metrics-adoption-plan.md](/Users/hesreallyhim/coding/projects/antipasta/docs/design/metrics-adoption-plan.md:42), but version remains `1.1.2` in [pyproject.toml](/Users/hesreallyhim/coding/projects/antipasta/pyproject.toml:7) and [src/antipasta/__version__.py](/Users/hesreallyhim/coding/projects/antipasta/src/antipasta/__version__.py:3). Either add compatibility shims or treat this as a major/deprecation release.

---

FIXME: UPDATE DOCS

- [x] P1 - Public docs and schema are behind the feature surface.
README omits `vcs` and `test-health` from the command table at [README.md](/Users/hesreallyhim/coding/projects/antipasta/README.md:110), still says Python-only / JS+TS coming soon at [README.md](/Users/hesreallyhim/coding/projects/antipasta/README.md:9), and still lists HTML reports as future work at [README.md](/Users/hesreallyhim/coding/projects/antipasta/README.md:599). The committed JSON schema has 13 metric enum values while the live model has 57, and it is missing `profile`, `tree_shape`, `import_graph`, `narrative`, `duplication`, and `use_gitignore`; see [src/antipasta/schemas/metrics-config.schema.json](/Users/hesreallyhim/coding/projects/antipasta/src/antipasta/schemas/metrics-config.schema.json:111).

---

FIXME

- [x] P1 - `test-health` works, but its default path fails in this repo’s coverage layout.
After `pytest --cov --cov-context=test`, coverage data landed at `.coverage/.coverage`; `antipasta test-health` defaulted to `.coverage` and rejected it because that is a directory. Explicitly running `antipasta test-health --coverage-file .coverage/.coverage` worked and reported 458 contexts, redundancy index `0.7445`, greedy cover `117/458`.

---

TODO (not yet): IGNORE AND/OR AUTO-CLEANUP AFTER ANTIPASTA PASSES ITS OWN METRICS - (Context: there was a decision to track in git the project's own coverage as these changes were made)

- [ ] P1/P2 - `tmp.html` is tracked and included in the sdist.
`tmp.html` is a 432K generated report artifact, shows up in `antipasta vcs` churn as 982 added lines, and is included in `/tmp/antipasta-dist/antipasta-1.1.2.tar.gz`. The wheel is clean, but the source release is polluted.

---

FIXME: Update deps(?)

- [x] P2 - Test suite is green but noisy.
`491 passed`, but pytest emits `15,766` deprecation warnings from `pathspec` using `gitwildmatch`. Not broken today, but it is enough noise to hide real warnings.

---

FIXME: USE FULL-SHA-PINNING TO LATEST MAJOR VERSION 

- [x] P2 - GitHub Actions are not SHA-pinned.
Workflows use tags such as `actions/checkout@v5`, `actions/setup-python@v6`, and `pypa/gh-action-pypi-publish@release/v1`. That violates your stated workflow policy, though it appears pre-existing rather than caused by this branch.

**Validation Run**

Passed: `ruff`, `mypy`, `pytest --no-cov`, `make check-all`, `antipasta metrics -d src/antipasta -q`, `antipasta report`, `antipasta stats`, `antipasta vcs`, build, and `twine check`.

Failed: `black --check`.

Could not run: `check-wheel-contents`; it is not installed in the project venv.

**Branch Status**

`feat/golden-set-core-split` is 40 commits ahead of `main` and 0 behind. The stack is active and coherent: report command, JS/TS lizard runner, phases 0-4, pydry duplication, VCS, static test smells, coverage-matrix health, then the core split. I’d call the implementation direction healthy, but release readiness is not there until formatting, version/API compatibility, docs/schema, and artifact cleanup are handled.
