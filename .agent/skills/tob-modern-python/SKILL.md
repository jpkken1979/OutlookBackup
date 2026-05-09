---
name: tob-modern-python
type: feature
description: >
---
  Modern Python development with uv, ruff, ty, pytest, and PEP 723. Covers
  migration from legacy tools (pip, black, isort, flake8, mypy), pyproject.toml
  configuration, and dependency groups. Use for Python project modernization.
source: Trail of Bits
---

# Modern Python Tooling

Modernize Python projects with the latest high-performance toolchain.

## Core Toolchain

| Tool | Replaces | Purpose |
|------|----------|---------|
| **uv** | pip, pip-tools, virtualenv, pyenv | Package/project manager |
| **ruff** | flake8, isort, black, pyflakes, pylint | Linter + formatter |
| **ty** | mypy, pyright | Type checker (experimental) |
| **pytest** | unittest | Test runner |

## uv — Package & Project Manager

### Project Init
```bash
# New project
uv init my-project
cd my-project

# Or init in existing dir
uv init

# With specific Python version
uv init --python 3.12
```

### Dependency Management
```bash
# Add dependencies
uv add requests pydantic

# Add dev/group dependencies
uv add --group dev pytest ruff
uv add --group lint ruff mypy
uv add --group test pytest pytest-asyncio

# Remove
uv remove requests

# Sync (install all from lockfile)
uv sync

# Sync with specific groups
uv sync --group dev --group test
```

### Running
```bash
# Run a command in the venv
uv run python main.py
uv run pytest tests/
uv run ruff check .

# Run a script with inline deps (PEP 723)
uv run script.py
```

### pyproject.toml with uv
```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0",
    "httpx>=0.27",
]

[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.9", "mypy>=1.13"]
test = ["pytest>=8.0", "pytest-asyncio>=0.24"]
lint = ["ruff>=0.9"]
```

## ruff — Linter & Formatter

### Configuration
```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "ARG",  # flake8-unused-arguments
    "SIM",  # flake8-simplify
    "S",    # flake8-bandit (security)
    "N",    # pep8-naming
    "RUF",  # ruff-specific rules
]

[tool.ruff.lint.isort]
known-first-party = ["my_project"]
```

### Usage
```bash
# Lint
ruff check .
ruff check --fix .          # Auto-fix
ruff check --diff .         # Show diff

# Format (replaces black)
ruff format .
ruff format --check .       # Check only
ruff format --diff .        # Show diff
```

### Migration from Legacy Tools
```bash
# From flake8
# Delete .flake8 / setup.cfg [flake8] section
# ruff check replaces flake8

# From black
# Delete black config
# ruff format replaces black

# From isort
# Delete .isort.cfg
# ruff check --select I replaces isort

# All at once
ruff check --fix . && ruff format .
```

## ty — Type Checker (Experimental)

```bash
# Install
uv add --group dev ty

# Run
uv run ty check
uv run ty check src/

# Strict mode
uv run ty check --strict
```

## pytest — Test Runner

### Configuration
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_functions = ["test_*"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow",
    "integration: integration tests",
    "unit: unit tests",
]
addopts = "-v --tb=short"
```

### Usage
```bash
uv run pytest                    # All tests
uv run pytest tests/test_api.py  # Single file
uv run pytest -k "test_create"   # By name pattern
uv run pytest -m "not slow"      # By marker
uv run pytest -x                 # Stop on first failure
uv run pytest --cov=src          # With coverage
```

## PEP 723 — Inline Script Metadata

Single-file scripts with inline dependency declarations:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27",
#     "rich>=13.0",
# ]
# ///
"""Fetch and display data from an API."""

import httpx
from rich import print

response = httpx.get("https://api.example.com/data")
print(response.json())
```

```bash
# Run directly — uv installs deps automatically
uv run script.py
```

## Migration Checklist

- [ ] Replace `pip` / `pip-tools` with `uv`
- [ ] Replace `virtualenv` / `venv` with `uv venv` (or let uv manage it)
- [ ] Replace `black` with `ruff format`
- [ ] Replace `isort` with `ruff check --select I`
- [ ] Replace `flake8` with `ruff check`
- [ ] Move all config to `pyproject.toml`
- [ ] Remove `setup.py`, `setup.cfg`, `MANIFEST.in` (if using pyproject.toml build)
- [ ] Delete `.flake8`, `.isort.cfg`, `.black.toml` config files
- [ ] Update CI to use `uv run` commands
- [ ] Add `uv.lock` to version control
