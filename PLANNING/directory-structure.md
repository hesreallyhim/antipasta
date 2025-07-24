# Directory Structure Design

## Overview

The project will be structured as a Python package with clear separation between core functionality, language-specific implementations, and interface layers.

```
cc-code-cop/
├── pyproject.toml              # Modern Python packaging
├── setup.py                    # Backwards compatibility
├── README.md
├── LICENSE
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── package.json               # Node dependencies for JS/TS analysis
├── .ccguard.metrics.yaml      # Example configuration
├── .gitignore
├── .pre-commit-config.yaml    # Pre-commit framework config
│
├── ccguard/                   # Main package
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
│   │   │   ├── radon.py       # Radon integration
│   │   │   └── complexipy.py  # Complexipy integration
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
│   │   └── metrics.py         # Metrics analysis command
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
- `ccguard.core`: Language-agnostic metric models and business logic
- `ccguard.runners`: Pluggable language-specific implementations
- `ccguard.cli`: Command-line interface
- `ccguard.hooks`: Adapters for various hook systems

### 2. **API Layers**

```python
# Low-level API (direct Python usage)
from ccguard.core import analyze_file
from ccguard.core.config import load_config

config = load_config(".ccguard.metrics.yaml")
metrics = analyze_file("myfile.py", config)

# CLI API
$ ccguard-metrics --files src/*.py
$ ccguard-validate-config .ccguard.metrics.yaml

# Hook API (via adapters)
# Pre-commit: calls CLI with specific arguments
# Claude Code: adapts stdin/stdout JSON format
```

### 3. **Entry Points**

Defined in `pyproject.toml`:
```toml
[project.scripts]
ccguard-metrics = "ccguard.cli.main:metrics_command"
ccguard-validate-config = "ccguard.cli.main:validate_command"

# For backwards compatibility with existing main.py
ccguard-claude-hook = "ccguard.hooks.claude:main"
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

- JSON Schema: `ccguard/schemas/metrics-config.schema.json`
- Pydantic models: `ccguard/core/config.py`

This structure provides:
- Clear separation of concerns
- Easy testing at each layer
- Multiple ways to consume the functionality
- Room for extension without breaking changes