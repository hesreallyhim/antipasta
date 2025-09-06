# Implementation Questions and Unknowns

This document outlines key unknowns and unresolved questions that need to be addressed before implementing the features described in TICKET_LIST.md.

## 1. Dual Configuration System

**Unknown**: Should we support both JSON (existing) and YAML (tickets) configs simultaneously?

**Questions**:

- Migration path for existing users?
- Which takes precedence if both exist?
- Should we auto-convert between formats?

**Decision**: **YAML only** - Since this is a greenfield prototype with no existing users, we'll use YAML exclusively as specified in the tickets. The YAML format provides better structure for language-specific configurations and is more readable.

---

## 2. Tool Integration Architecture

**Unknown**: Current code is a hook script, but tickets describe CLI tools

**Questions**:

- How do these coexist? Is main.py being replaced or wrapped?
- Should the hook call the CLI tools or embed the logic?
- Directory structure for the modular architecture?

**Decision**: **Modular API-first design** - The tool will be structured as a Python package with:

- Core library providing language-agnostic APIs
- CLI commands as the primary interface
- Hook adapters that wrap the core functionality
- The existing main.py becomes a thin adapter in `antipasta/hooks/claude.py`
- See `PLANNING/directory-structure.md` for full details

---

## 3. TypeScript/JavaScript Tooling

**Unknown**: `ts-complex` npm package details and availability

**Questions**:

- Is ts-complex actually published on npm? (need to verify)
- Fallback strategy if not available?
- How to handle Node.js dependency in Python project?
- Should we bundle node_modules or expect users to npm install?

**Decision**: **Deferred** - Initial prototype will focus on Python only. Design will maintain extensibility for future language support through the runner plugin architecture.

---

## 4. Complexipy Integration

**Unknown**: Package availability and Python version compatibility

**Questions**:

- Is it on PyPI? What's the exact package name?
- Does it output JSON or need parsing?
- How does cognitive complexity differ from cyclomatic?

**Decision**: **Use complexipy from PyPI** - Package is available on PyPI as `complexipy`. Repository at https://github.com/rohaquinlop/complexipy. Will integrate as a second Python runner alongside Radon.

---

## 5. Pathspec/.gitignore Integration

**Unknown**: Exact behavior expected

**Questions**:

- Should we respect .gitignore by default or make it configurable?
- What about other ignore files (.dockerignore, .npmignore)?
- How deep should the integration go?

**Decision**: **Mirror .gitignore** - First pass will respect .gitignore by default using the `pathspec` library. No configuration needed initially.

---

## 6. Pre-commit Framework Integration

**Unknown**: How this relates to the existing Claude Code hook

**Questions**:

- Are we supporting both pre-commit framework AND Claude Code hooks?
- Different entry points for each?
- How to handle the different input formats?

**Decision**: **CLI-first approach** - Focus on building a working CLI library first. Hooks can be added later as thin wrappers around the CLI. This provides maximum flexibility for integration.

---

## 7. Metric Aggregation Strategy

**Unknown**: How to aggregate metrics across mixed languages

**Questions**:

- Should Python and JS files have different thresholds?
- How to handle partial file analysis in MultiEdit?
- Should we analyze whole files or just changed portions?

**Decision**: **Deferred** - First pass supports Python only. Will design aggregator with language-specific thresholds in mind for future extensibility.

---

## 8. Exit Codes and Error Handling

**Unknown**: Specific exit code semantics

**Questions**:

- What's the difference between exit code 2 (block) vs 1 (error)?
- How to handle missing dependencies gracefully?
- Should we fail open or closed when tools are unavailable?

**Decision**: **Not relevant for POC** - Exit codes pertain to hooks. CLI will use standard conventions: 0 for success, 1 for errors, 2 for violations found.

---

## 9. Performance Considerations

**Unknown**: Performance impact of running multiple tools

**Questions**:

- Should we parallelize language analysis?
- Cache strategy for unchanged files?
- Timeout handling for large files?

**Decision**: **Build first, optimize later** - Create a "steel thread" implementation for Python metrics. Test against various file sizes and optimize only if needed. Focus on correctness over performance initially.

---

## 10. Package Distribution

**Unknown**: How to package and distribute

**Questions**:

- Use setup.py, pyproject.toml, or both?
- How to handle the Node.js dependencies?
- Should we create a separate package or extend current?

**Decision**: **Modern Python tooling** - Use pyproject.toml with hatchling build backend, venv for virtual environments, and standard tools (ruff, black, mypy) with default settings. No Node.js dependencies in initial version.

---

## 11. Backwards Compatibility

**Unknown**: Impact on existing users of main.py

**Questions**:

- Can we break the existing hook interface?
- How to communicate changes to users?
- Version numbering strategy?

**Decision**: **Not an issue** - This is the first implementation with no existing users. Start at version 0.1.0 following semantic versioning.

---

## Notes

This document will be updated with decisions as they are made. Each decision should include:

- The chosen approach
- Rationale for the decision
- Any implications or trade-offs
