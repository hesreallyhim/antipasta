# Release Guide for Antipasta

This guide provides detailed instructions for releasing new versions of antipasta to PyPI.

## Quick Start

**Pre-flight check:**

```bash
make release-doctor  # Check system health and prerequisites
```

**Safe one-command releases (recommended):**

```bash
make release-patch-safe  # Bug fixes (0.0.X) with safety checks
make release-minor-safe  # New features (0.X.0) with safety checks
make release-major-safe  # Breaking changes (X.0.0) with safety checks
```

**Standard releases (without safety checks):**

```bash
make release-patch  # Bug fixes (0.0.X)
make release-minor  # New features (0.X.0)
make release-major  # Breaking changes (X.0.0)
```

These commands handle everything: version bump → commit → push → GitHub release → PyPI deployment.

**Testing before release:**

```bash
# Test what will happen (dry-run)
make release-dry-patch  # Simulate patch release
make release-dry-minor  # Simulate minor release
make release-dry-major  # Simulate major release
make gh-release-dry     # Simulate GitHub release creation

# Deploy to TestPyPI first
make gh-release-test    # Safe testing on TestPyPI
```

## Release Methods

Antipasta supports two release methods:

1. **GitHub Actions (Recommended)**: Automated deployment via GitHub Releases
2. **Manual Release**: Direct upload from your local machine

## Pre-Release Health Check

Before any release, run the release doctor to check your system:

```bash
make release-doctor
```

This comprehensive health check verifies:
- ✅ GitHub CLI installation and authentication
- ✅ Git repository state (uncommitted changes, branch)
- ✅ Version status and available tags
- ✅ Python environment and build tools
- ✅ GitHub repository and workflow configuration

## Testing Your Release (Dry-Run)

Before making an actual release, test what will happen:

```bash
# See what a patch release would do
make release-dry-patch

# Test GitHub release creation
make gh-release-dry

# Run pre-release safety checks
make release-safety-check
```

These commands simulate the entire release process without making any changes.

## Method 1: GitHub Actions (Recommended)

### Prerequisites

1. **GitHub Repository Access**: Push access to the antipasta repository
2. **Trusted Publishing**: Already configured in PyPI project settings (no tokens needed!)

### Quick Release Commands

The easiest and safest way to release is using the safe all-in-one commands:

```bash
# Safe releases with automatic safety checks (recommended)
make release-patch-safe  # Bug fixes (0.0.X)
make release-minor-safe  # New features (0.X.0)
make release-major-safe  # Breaking changes (X.0.0)

# Or standard releases without safety checks
make release-patch       # Bug fixes (0.0.X)
make release-minor       # New features (0.X.0)
make release-major       # Breaking changes (X.0.0)
```

These commands automatically:
1. Bump the version
2. Commit changes
3. Push to GitHub
4. Create a GitHub release
5. Trigger PyPI deployment

### Step-by-Step Workflow

For more control over the release process:

1. **Check System Health**:
   ```bash
   make release-doctor      # Comprehensive pre-flight check
   make release-safety-check  # Quick safety validation
   ```

2. **Test First (Optional but Recommended)**:
   ```bash
   make release-dry-patch   # Simulate the release
   make gh-release-dry      # Check if release would succeed
   ```

3. **Bump Version**:
   ```bash
   make version-bump-patch  # or minor/major
   ```

4. **Create GitHub Release**:
   ```bash
   # Safe release with checks (recommended)
   make gh-release-safe

   # Standard release
   make gh-release

   # Or create a draft to review first
   make gh-release-draft
   ```

5. **Monitor Deployment**:
   - The command outputs links to:
     - GitHub Actions progress
     - PyPI package page
   - Package appears on PyPI within minutes

### Alternative Methods

**GitHub UI**
- Navigate to your repo → Releases → "Draft a new release"
- Click "Choose a tag" → Create new tag: `v0.1.1` (match your version)
- Release title: `v0.1.1`
- Click "Generate release notes" for automatic changelog
- Click "Publish release"

**GitHub CLI (manual)**
```bash
gh release create v0.1.1 --generate-notes --title "v0.1.1"
```

### Testing with GitHub Actions

Before a production release, test on TestPyPI:

**Using Makefile (Recommended)**
```bash
make gh-release-test
```

This triggers the TestPyPI workflow and provides installation instructions.

**Using GitHub UI**
1. Go to Actions → "Publish to PyPI" workflow
2. Click "Run workflow"
3. Select `testpypi` as target
4. Run the workflow

**Test Installation**
```bash
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ antipasta
```

## Method 2: Manual Release

### Prerequisites

1. **PyPI Account**: Create an account at [pypi.org](https://pypi.org)
2. **TestPyPI Account** (optional): Create an account at [test.pypi.org](https://test.pypi.org)
3. **API Tokens**: Generate API tokens for both PyPI and TestPyPI
4. **Configure Authentication**: Set up your `~/.pypirc` file:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-TOKEN-HERE

[testpypi]
username = __token__
password = pypi-YOUR-TEST-TOKEN-HERE
repository = https://test.pypi.org/legacy/
```

5. **Clean Git State**: Ensure your working directory is clean and you're on the main branch

## Release Workflow

### Step 1: Pre-release Checks

Run the release checklist to ensure everything is ready:

```bash
make release-check
```

This displays a checklist of items to verify before releasing:
- All tests passing
- Code formatted properly
- Type checks passing
- Version bumped appropriately
- CHANGELOG updated (if applicable)
- Git working directory clean
- On the correct branch

### Step 2: Run Quality Checks

Ensure all quality checks pass:

```bash
make check
```

This runs:
- Linting (`ruff`)
- Type checking (`mypy`)
- Tests (`pytest`)

### Step 3: Update Version

Choose the appropriate version bump based on your changes:

#### Patch Release (Bug Fixes)
For backward-compatible bug fixes (0.0.X):
```bash
make version-bump-patch
```

#### Minor Release (New Features)
For backward-compatible new features (0.X.0):
```bash
make version-bump-minor
```

#### Major Release (Breaking Changes)
For incompatible API changes (X.0.0):
```bash
make version-bump-major
```

The version will be updated in both `antipasta/__version__.py` and `pyproject.toml`.

### Step 4: Build and Verify

Build the distribution packages and verify they're correct:

```bash
make build-check
```

This will:
1. Clean any previous build artifacts
2. Build both source distribution (.tar.gz) and wheel (.whl)
3. Run `twine check` to validate the packages

You can also do a dry run to see what will be uploaded:

```bash
make release-dry-run
```

### Step 5: Test Release (Optional but Recommended)

Test your release on TestPyPI first:

```bash
make release-test
```

Then install and test from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ antipasta
```

### Step 6: Production Release

Once you're confident everything works, release to PyPI:

```bash
make release
```

This uploads your packages to the official PyPI repository.

### Step 7: Git Tag and Push

After a successful release, create a git tag:

```bash
# Commit the version changes
git add -A
git commit -m "chore: release v$(make version-show 2>&1 | grep "Current version" | cut -d: -f2 | xargs)"

# Create and push tag
git tag -a v$(make version-show 2>&1 | grep "Current version" | cut -d: -f2 | xargs) -m "Release v$(make version-show 2>&1 | grep "Current version" | cut -d: -f2 | xargs)"
git push origin main --tags
```

### Step 8: Verify Installation

Test that the new version can be installed from PyPI:

```bash
pip install --upgrade antipasta
antipasta --version
```

## Troubleshooting

### Authentication Errors

If you get authentication errors:
1. Verify your `.pypirc` file has the correct API tokens
2. Ensure tokens start with `pypi-`
3. Check that tokens have upload permissions

### Package Validation Errors

If `twine check` fails:
1. Run `make clean` to remove old artifacts
2. Ensure `README.md` is valid markdown
3. Check that all required fields are in `pyproject.toml`

### Version Already Exists

If PyPI reports the version already exists:
1. You cannot overwrite an existing version on PyPI
2. Bump the version again (even for a patch)
3. Delete local build artifacts: `make clean`

### TestPyPI Issues

TestPyPI may have missing dependencies. When testing installation:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ antipasta
```

The `--extra-index-url` ensures dependencies are pulled from production PyPI.

## Version Numbering Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Incompatible API changes
  - Removing features
  - Changing function signatures
  - Major behavior changes

- **MINOR** (0.X.0): Backward-compatible functionality
  - New features
  - New configuration options
  - Deprecations (but not removals)

- **PATCH** (0.0.X): Backward-compatible bug fixes
  - Bug fixes
  - Performance improvements
  - Documentation updates

## Release Checklist

Use the built-in checklist command:

```bash
make release-check
```

This displays the current version and a checklist of items to verify:
- [ ] All tests passing (`make test`)
- [ ] Code formatted (`make format`)
- [ ] Type checks passing (`make type-check`)
- [ ] Version bumped appropriately
- [ ] CHANGELOG.md updated (if exists)
- [ ] Git working directory clean
- [ ] On correct branch (main/master)

For a complete quality check before release:

```bash
make check  # Runs lint, type-check, and tests
```

## Automating Releases

For frequent releases, consider:

1. **GitHub Actions**: Automate releases on tag push
2. **Semantic Release**: Automatic version management based on commit messages
3. **Pre-commit Hooks**: Ensure quality checks before commits

## Emergency Rollback

If a critical issue is found after release:

1. **Do NOT delete the release from PyPI** (it's not allowed)
2. **Yank the release** (marks it as broken):
   ```bash
   pip install twine
   twine yank antipasta==X.Y.Z
   ```
3. **Fix the issue** and release a new patch version
4. **Communicate** with users about the issue

## Additional Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)