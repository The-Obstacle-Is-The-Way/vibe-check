# SPEC-01: DevEx Foundation

**Status**: IMPLEMENTED (2026-01-02)
**Slice Type**: Infrastructure (Prerequisite for all other slices)
**Dependencies**: None
**Estimated Scope**: ~50 lines of config, ~20 lines of test code

---

## 1. Objective

Establish a production-grade Python development environment with 2026 best practices. This slice is **infrastructure-only** - no application logic, just tooling that all subsequent slices depend on.

### Success Criteria

```bash
# All of these must pass before this spec is complete:
make dev          # Installs deps + pre-commit hooks
make lint         # Zero errors
make typecheck    # Zero errors
make test         # Canary test passes
make ci           # Full CI pipeline passes locally
```

---

## 2. Deliverables

### 2.1 Project Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Single source of truth for deps, ruff, mypy, pytest, coverage |
| `.python-version` | Pin Python version (3.11) |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff + mypy) |
| `Makefile` | Developer convenience commands |
| `.github/workflows/ci.yml` | GitHub Actions CI |
| `.env.example` | Template for environment variables |
| `src/vibe_check/__init__.py` | Package marker |
| `tests/conftest.py` | Pytest configuration |
| `tests/unit/test_canary.py` | Smoke test proving toolchain works |
| `.gitignore` | Comprehensive Python + macOS gitignore (already exists, verify complete) |

### 2.2 Directory Structure (Minimal)

```
vibe-check/
├── pyproject.toml
├── .python-version
├── .pre-commit-config.yaml
├── Makefile
├── .env.example
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── vibe_check/
│       └── __init__.py
└── tests/
    ├── conftest.py
    └── unit/
        └── test_canary.py
```

---

## 3. Technical Specifications

### 3.1 pyproject.toml

**Build System**: hatchling (modern, fast, PEP 621 compliant)

**Core Dependencies** (minimal for this slice):
```toml
dependencies = [
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
]
```

**Dev Dependencies**:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.5",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=7.0.0",
    "ruff>=0.9.2",
    "mypy>=1.15.0",
    "pre-commit>=4.1.0",
]
```

**Ruff Configuration**:
- `line-length = 100`
- `target-version = "py311"`
- Select: E, W, F, I, B, C4, UP, ARG, SIM, TCH, PTH, RUF
- First-party: `vibe_check`

**Mypy Configuration**:
- `strict = true`
- `warn_unused_ignores = true`
- `show_error_codes = true`

**Pytest Configuration**:
- `testpaths = ["tests"]`
- `asyncio_mode = "auto"`
- Markers: unit, integration, e2e, slow
- Strict markers and config

**Coverage**:
- `source = ["src/vibe_check"]`
- `fail_under = 80`
- `branch = true`

### 3.2 .python-version

```
3.11
```

### 3.3 Pre-commit Hooks

1. **pre-commit-hooks**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, detect-private-key
2. **ruff-pre-commit**: lint with --fix, format check
3. **local mypy**: via `uv run mypy`

### 3.4 Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `dev` | `uv sync --locked --all-extras && uv run pre-commit install` | Full dev setup |
| `install` | `uv sync --locked` | Production install |
| `test` | `uv run pytest tests/ --cov=src/vibe_check --cov-report=term-missing --cov-fail-under=80` | Run tests with coverage |
| `test-unit` | `uv run pytest tests/unit/ -v` | Unit tests only |
| `lint` | `uv run ruff check .` | Lint check |
| `lint-fix` | `uv run ruff check . --fix` | Auto-fix lint issues |
| `format` | `uv run ruff format .` | Format code |
| `typecheck` | `uv run mypy src tests` | Type check (strict via `pyproject.toml`) |
| `ci` | `format-check lint typecheck test` | Full CI locally |
| `clean` | Remove `.pytest_cache`, `.mypy_cache`, `__pycache__`, etc. | Cleanup |

### 3.5 .gitignore Requirements

The `.gitignore` must include (already added to repo):

**macOS System Files** (critical for multi-platform teams):
```gitignore
.DS_Store
.AppleDouble
.LSOverride
._*
.Spotlight-V100
.Trashes
.fseventsd
Icon?
```

**Project-specific**:
```gitignore
# Checkpoints and outputs (large, regeneratable)
data/checkpoints/
data/outputs/

# Local secrets
.secrets/
```

The existing Python `.gitignore` template already covers: `__pycache__`, `.venv`, `.env`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `htmlcov/`, `*.egg-info`, etc.

### 3.6 CI Workflow

**Triggers**: push to main/dev, PR to main

**Jobs**:
1. **lint**: ruff check + format check
2. **typecheck**: mypy (strict via `pyproject.toml`) + smoke import
3. **test**: pytest with coverage on Python 3.11 and 3.12

**Key Features**:
- Uses `actions/setup-python@v5` to pin the interpreter
- Uses `astral-sh/setup-uv@v7` for fast uv installs
- Caches dependencies via `uv.lock`
- Uploads coverage to Codecov
- Concurrency: cancel-in-progress for same ref
- Sets `PYTHONHASHSEED=0` for deterministic hashing
- Adds per-job timeouts to prevent hung runs

---

## 4. Test Specification

### 4.1 Canary Test (`tests/unit/test_canary.py`)

This test proves the toolchain works. It should:

1. Import from `vibe_check` package
2. Assert package has a `__version__` attribute
3. Pass type checking and linting

```python
"""Canary test to verify toolchain is working."""

from vibe_check import __version__


def test_version_exists() -> None:
    """Package version should be defined."""
    assert __version__ is not None
    assert isinstance(__version__, str)


def test_version_format() -> None:
    """Version should follow semver-like format."""
    parts = __version__.split(".")
    assert len(parts) >= 2  # At least major.minor
    assert all(part.isdigit() for part in parts[:2])
```

### 4.2 conftest.py

Minimal for now - just establish the pattern:

```python
"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def sample_file_id() -> str:
    """Sample file_id for testing."""
    return "active436"
```

---

## 5. Definition of Done

- [x] `uv init` creates project with hatchling backend
- [x] `uv sync --locked --all-extras` installs all dependencies
- [x] `uv run pre-commit install` installs hooks
- [x] `make lint` passes with zero errors
- [x] `make typecheck` passes with zero errors
- [x] `make test` passes with canary test
- [x] Coverage threshold (80%) is enforced
- [x] `make ci` runs full local CI successfully
- [x] Pre-commit hooks block commits with lint/type errors
- [x] GitHub Actions CI workflow is syntactically valid (manual check)
- [x] `.gitignore` includes macOS artifacts and project-specific exclusions

---

## 6. Non-Goals (Explicitly Deferred)

- Application code (deferred to SPEC-02+)
- LLM client setup (deferred to SPEC-04+)
- Database/checkpoint setup (deferred to later)
- Complex test fixtures (just the canary for now)

---

## 7. Testing Philosophy for This Spec

This spec has **one test**: the canary. It's not about testing behavior yet - it's about proving:

1. The toolchain compiles
2. Imports work
3. Type checking works
4. Test discovery works

No mocks. No stubs. Just "does the infrastructure function?"

---

## 8. Implementation Notes

### Implementation Deviations (SSOT)

- Hatchling src-layout requires an explicit wheel target: `[tool.hatch.build.targets.wheel] packages = ["src/vibe_check"]`.
- `make dev` uses `uv sync --locked --all-extras` (the `dev` extra is installed via extras; no separate `--dev` flag needed).

### Order of Operations

1. Create directory structure
2. Write `pyproject.toml` (complete config)
3. Write `.python-version`
4. Run `uv sync --all-extras` to generate `uv.lock`
5. Write `src/vibe_check/__init__.py` with `__version__`
6. Write `tests/conftest.py` and `tests/unit/test_canary.py`
7. Run `make test` to verify
8. Write `.pre-commit-config.yaml`
9. Run `uv run pre-commit install`
10. Write `Makefile`
11. Run `make ci` to verify full pipeline
12. Write `.github/workflows/ci.yml`
13. Write `.env.example`

### Why This Order?

- `pyproject.toml` first because `uv sync` needs it
- Tests before pre-commit because we need something to lint/check
- CI workflow last because it's validated by pushing

---

## Appendix A: Full pyproject.toml Template

See SPEC-vibe-check.md Section 10.1 for the complete template. This spec uses a **minimal subset** - only the infrastructure deps, not the full application deps.
