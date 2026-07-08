# Contributing

This project welcomes contributions. You may open an issue to request a new feature or report a bug.

If you plan to make a more substantial PR, it is recommended that you open an issue first to discuss the proposed change.

For all contributors, please be sure that you have read the Code of Conduct.

## Local Setup

antipasta is a Python project. The local default Python version is recorded in `.python-version`; use Python 3.11 unless you are intentionally testing another supported version.

Create the project virtual environment and install development dependencies:

```sh
make install-dev
```

The Makefile creates and uses a local `venv/` directory. You do not need to activate it for the documented Make targets.

To install the repository's pre-commit hooks:

```sh
make install-hooks
```

## Common Commands

Show available Make targets:

```sh
make help
```

Format code:

```sh
make format
```

Run linting, type checking, and tests in the local virtual environment:

```sh
make check
```

Run the test suite only:

```sh
make test
```

Run CI-parity checks through tox, including Python 3.11, Python 3.12, linting, type checking, and package validation:

```sh
make check-ci
```

## Before Opening a Pull Request

Before opening a pull request, run:

```sh
make format
make check-ci
```

If you are iterating quickly, `make test-fast` can run the tests most likely to be affected by your recent changes. If its cache appears stale after switching branches, run `make test-fast-clean`.

Keep pull requests focused. If a change affects behavior, include or update tests that demonstrate the expected behavior.

## Maintainers - Release Process

antipasta uses Release Please for normal releases. Contributors do not need to bump versions, edit release notes, create tags, or publish packages manually.

Use conventional commit-style PR titles because the squash commit message is what Release Please uses to decide the next version:

- `fix: ...` for patch releases
- `feat: ...` for minor releases
- `feat!: ...` or a `BREAKING CHANGE:` footer for major releases
- `docs: ...`, `test: ...`, `refactor: ...`, `ci: ...`, and `chore: ...` for changes that usually should not create a release by themselves

After changes are merged to `main`, the Release Please workflow opens or updates a release PR. That PR owns the version bump, `CHANGELOG.md`, and release metadata. When the release PR is merged, Release Please creates the GitHub release, and the PyPI publishing workflow publishes the package using trusted publishing.

For maintainers, the usual release checklist is:

```sh
make check-ci
```

Then review the Release Please PR, confirm the version and changelog are correct, merge it, and monitor the `Publish to PyPI` workflow. For a packaging smoke test before a production release, use the manual `Publish to PyPI` workflow with the `testpypi` target.

The older local upload flow is not the preferred path. Avoid publishing directly from a workstation unless the automated release pipeline is unavailable and the reason is documented in the release notes or follow-up issue.
