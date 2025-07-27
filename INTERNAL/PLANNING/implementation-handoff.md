# Implementation Handoff Document

## Critical Context for New Implementation

### What You're Building

**code-cop** is a code quality enforcement tool that analyzes code complexity metrics. Currently, there's a working prototype in `main.py` that functions as a Claude Code hook. Your task is to refactor this into a modular Python package with a CLI interface.

### Current State vs Target State

**Current State:**
- `main.py` - Monolithic script (398 lines) that works as a Claude Code hook
- Analyzes Python files using Radon library
- Falls back to heuristic analysis for JS/TS files
- Uses JSON config file: `.code_cop.config.json`
- Has comprehensive unit tests in `test_main.py`

**Target State:**
- Modular Python package structure under `code_cop/` ✓ COMPLETED
- CLI tool: `code-cop` with subcommands ✓ COMPLETED
- YAML configuration: `.code_cop.yaml` ✓ COMPLETED
- Python-only for initial implementation ✓ COMPLETED
- Modern Python tooling (pyproject.toml, ruff, black, mypy) ✓ COMPLETED
- Additional features added: statistics command, multiple runners per language

### Implementation Priority (CRITICAL)

**Phase 1 - Project Setup** (Do this FIRST):
1. Create `pyproject.toml` with hatchling build backend
2. Set up development tools (ruff, black, mypy) with default configs
3. Create the `code_cop/` package structure
4. Set up GitHub Actions for CI

**Phase 2 - Core Implementation** (In this order):
1. T-01: Config schema with YAML and Pydantic validation ✓ COMPLETED
2. T-02: Language detector with pathspec for .gitignore ✓ COMPLETED
3. T-03: Python runner wrapping Radon ✓ COMPLETED
4. T-06: Aggregator and decision engine ✓ COMPLETED
5. T-04: Complexipy integration ✓ COMPLETED

**Deferred:** T-05 (JS/TS support), T-07 (pre-commit), T-08 (docs), T-09 (CI examples)

### Key Architecture Decisions (MUST FOLLOW)

1. **Configuration Format**: YAML only, no JSON support needed
   ```yaml
   defaults:
     max_cyclomatic_complexity: 10
     min_maintainability_index: 50

   languages:
     - name: python
       metrics:
         - type: cyclomatic_complexity
           threshold: 10
           comparison: "<="
   ```

2. **Package Structure**: Follow exactly as specified in `PLANNING/directory-structure.md`
   - `code_cop/core/` - Business logic (config, metrics, aggregator, detector, violations)
   - `code_cop/runners/` - Language-specific runners
   - `code_cop/cli/` - CLI commands
   - `code_cop/utils/` - Shared utilities

3. **CLI Design**: Single entry point with subcommands
   - `code-cop metrics --files src/*.py`
   - `code-cop validate-config .code_cop.yaml`
   - `code-cop stats --pattern "**/*.py"` (added feature)

4. **Dependencies**:
   - Production: `radon`, `complexipy`, `pydantic`, `pyyaml`, `pathspec`, `click` (chosen CLI framework)
   - Development: `pytest`, `ruff`, `black`, `mypy`, `pytest-cov`

### Critical Implementation Details

**Metric Definitions** (from existing code):
- **Cyclomatic Complexity**: Number of linearly independent paths
- **Halstead Metrics**: Volume, difficulty, effort based on tokens
- **Maintainability Index**: Combined score 0-100 (higher is better)
- **Cognitive Complexity**: (via Complexipy) How hard code is to understand

**Exit Codes**:
- 0 = Success, no violations
- 1 = Error (missing files, config errors, etc.)
- 2 = Violations found

**Runner Interface** (all runners must implement):
```python
class BaseRunner(ABC):
    @abstractmethod
    def analyze(self, file_path: Path, content: str) -> List[MetricResult]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
```

### What to Reuse from Existing Code

1. **Metric Calculation Logic**: The `radon_metrics()` and `heuristic_metrics()` functions in `main.py` are well-tested and should be adapted into the runners
2. **Test Cases**: `test_main.py` has comprehensive tests that should be migrated
3. **Metric Thresholds**: Current defaults are sensible, keep them

### Important Constraints

1. **Python-First**: Only implement Python support initially. Design for extensibility but don't implement JS/TS
2. **No Hooks Yet**: Focus on CLI only. Hooks come later
3. **Use Pathspec**: Must respect .gitignore using the pathspec library
4. **Modern Python**: Use type hints everywhere, Python 3.11 features (match statements, etc.)

### Testing Approach

1. **Unit Tests**: Each module should have corresponding tests
2. **Integration Tests**: Test CLI commands end-to-end
3. **Test Data**: Create fixtures under `tests/fixtures/`
4. **Coverage**: Aim for >90% coverage

### Common Pitfalls to Avoid

1. **Don't overthink the aggregator** - For Python-only, it's simpler
2. **Don't implement hooks** - CLI first, hooks are a thin wrapper later
3. **Don't add features** - Implement exactly what's in TICKET_LIST.md
4. **Don't skip pyproject.toml** - Set up modern tooling first

### Where to Start

1. Read these files in order:
   - `TICKET_LIST.md` - The requirements
   - `PLANNING/implementation-questions.md` - All decisions explained
   - `PLANNING/directory-structure.md` - Exact structure to create
   - `main.py` - Current implementation to understand the logic

2. Create the project structure:
   ```bash
   mkdir -p code_cop/{core,runners/python,cli,utils}
   touch code_cop/__init__.py
   # ... etc
   ```

3. Start with `pyproject.toml`:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [project]
   name = "code-cop"
   version = "0.1.0"
   # ... etc
   ```

### Configuration File Locations

- Example config: `.code_cop.yaml` in project root
- JSON Schema: `code_cop/schemas/metrics-config.schema.json`
- Pydantic models: `code_cop/core/config.py`

### Final Notes

- This is a greenfield project with no users - you can make breaking changes
- The existing `main.py` is just a reference - you're building fresh
- Keep it simple - this is a small, focused tool
- When in doubt, check the planning documents
- Use `git log --oneline` to see the planning history

### Questions You Might Have

**Q: Should I modify main.py?**
A: No, leave it as-is. It becomes `code_cop/hooks/claude.py` later.

**Q: What about the JavaScript heuristic analysis in main.py?**
A: Ignore it. Python-only for now.

**Q: Do I need to handle the JSON config format?**
A: No, YAML only.

**Q: Should I implement all tickets?**
A: No, focus on T-01, T-02, T-03, T-06 (and T-04 if time permits).

**Q: What Python version?**
A: Python 3.11 (see `.python-version` file).

Good luck! The planning is solid, now it just needs to be built.