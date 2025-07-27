# Directory Structure Design

## Overview

The project will be structured as a Python package with clear separation between core functionality, language-specific implementations, and interface layers.

```
cc-code-cop/
├── pyproject.toml              # Modern Python packaging
# (setup.py removed - using pyproject.toml only)
├── README.md
├── LICENSE
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── package.json               # Node dependencies for JS/TS analysis
├── .code_cop.yaml      # Example configuration
├── .gitignore
├── .pre-commit-config.yaml    # Pre-commit framework config
│
├── code_cop/                   # Main package
│   ├── __init__.py
│   ├── __version__.py         # Single source of version
│   │
│   ├── core/                  # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration loading/validation
│   │   ├── metrics.py         # Metric data models (Pydantic)
│   │   ├── aggregator.py      # Metric aggregation logic
│   │   ├── detector.py        # Language detection
│   │   └── violations.py      # Violation detection engine
│   │
│   ├── runners/               # Language-specific metric runners
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract base runner
│   │   ├── python/
│   │   │   ├── __init__.py
│   │   │   ├── radon_runner.py       # Radon integration
│   │   │   └── complexipy_runner.py  # Complexipy integration
│   │   ├── javascript/
│   │   │   ├── __init__.py
│   │   │   └── tscomplex.py   # ts-complex integration
│   │   └── typescript/
│   │       ├── __init__.py
│   │       └── tscomplex.py   # Reuses JS runner
│   │
│   ├── cli/                   # CLI commands
│   │   ├── __init__.py
│   │   ├── main.py            # Main CLI entry point
│   │   ├── validate.py        # Config validation command
│   │   ├── metrics.py         # Metrics analysis command
│   │   └── stats.py           # Statistics collection command
│   │
│   ├── hooks/                 # Hook integrations
│   │   ├── __init__.py
│   │   ├── precommit.py       # Pre-commit framework
│   │   └── claude.py          # Claude Code hook adapter
│   │
│   └── utils/                 # Shared utilities
│       ├── __init__.py
│       ├── subprocess.py      # Subprocess helpers
│       ├── cache.py           # Caching functionality
│       └── pathspec.py        # .gitignore handling
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_metrics.py
│   │   ├── test_aggregator.py
│   │   └── runners/
│   │       ├── test_python.py
│   │       └── test_javascript.py
│   ├── integration/
│   │   ├── test_cli.py
│   │   └── test_hooks.py
│   └── fixtures/             # Test data
│       ├── python/
│       ├── javascript/
│       └── configs/
│
├── examples/                 # Example usage
│   ├── simple_project/
│   ├── multi_language/
│   └── custom_config/
│
├── scripts/                  # Development scripts
│   ├── install-dev.sh
│   └── run-tests.sh
│
└── docs/                    # Documentation
    ├── api.md
    ├── configuration.md
    └── metrics.md
```

## Key Design Principles

### 1. **Core Package Structure**

- `code_cop.core`: Language-agnostic metric models and business logic
- `code_cop.runners`: Pluggable language-specific implementations
- `code_cop.cli`: Command-line interface
- `code_cop.hooks`: Adapters for various hook systems

### 2. **API Layers**

```python
# Low-level API (direct Python usage)
from code_cop.core import analyze_file
from code_cop.core.config import load_config

config = load_config(".code_cop.yaml")
metrics = analyze_file("myfile.py", config)

# CLI API
$ code-cop metrics --files src/*.py
$ code-cop validate-config .code_cop.yaml

# Hook API (via adapters)
# Pre-commit: calls CLI with specific arguments
# Claude Code: adapts stdin/stdout JSON format
```

### 3. **Entry Points**

Defined in `pyproject.toml`:

```toml
[project.scripts]
code-cop = "code_cop.cli.main:main"

# For backwards compatibility with existing main.py
code-cop-claude-hook = "code_cop.hooks.claude:main"
```

### 4. **Runner Plugin Architecture**

Each language runner implements a common interface:

```python
class BaseRunner(ABC):
    @abstractmethod
    def analyze(self, file_path: Path, content: str) -> List[MetricResult]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
```

### 5. **Configuration Schema Location**

- JSON Schema: `code_cop/schemas/metrics-config.schema.json`
- Pydantic models: `code_cop/core/config.py`

This structure provides:

- Clear separation of concerns
- Easy testing at each layer
- Multiple ways to consume the functionality
- Room for extension without breaking changes
