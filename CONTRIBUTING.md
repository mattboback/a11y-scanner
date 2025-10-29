# Contributing to a11y-scanner

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Enhancements](#suggesting-enhancements)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Docker or Podman
- Git

### Setting Up Your Development Environment

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/a11y-scanner.git
   cd a11y-scanner
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/a11y-scanner.git
   ```

4. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

5. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

6. **Verify setup**:
   ```bash
   pytest -q -k "not test_playwright_axe_service"
   python -m scanner.container.runner prepare
   ```

## Development Workflow

### 1. Create a Branch

Always work on a feature branch, not `main`:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or fixes

### 2. Make Your Changes

- Write clear, self-documenting code
- Add type hints to all functions
- Include docstrings for public APIs
- Update documentation as needed
- Add tests for new functionality

### 3. Run Tests Locally

**Quick tests** (skip browser-heavy tests):
```bash
pytest -q -k "not test_playwright_axe_service"
```

**Full test suite**:
```bash
pytest -q
```

**Integration tests** (requires Docker):
```bash
python -m scanner.container.integration
# or
make integration
```

**Reporting tests**:
```bash
pytest tests/test_reporting.py -v
# or
make test-reporting
```

### 4. Format and Lint

**Format code**:
```bash
black src tests
```

**Lint code**:
```bash
ruff check src tests
```

**Auto-fix linting issues**:
```bash
ruff check src tests --fix
```

### 5. Update Documentation

If you've made changes that affect usage:
- Update `README.md`
- Update relevant files in `docs/`
- Add entries to `CHANGELOG.md` under `[Unreleased]`

### 6. Commit Your Changes

See [Commit Guidelines](#commit-guidelines) below.

### 7. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Style

### Python Style

- **Formatting**: Use Black with line length 88
- **Linting**: Follow Ruff rules (E, F, W, I, B, UP)
- **Type hints**: Required for all function signatures
- **Docstrings**: Use for all public functions, classes, and modules
- **Imports**: Group and sort with `isort` (handled by Ruff)

### Code Organization

```python
# Good: Clear, typed, documented
from pathlib import Path

def scan_url(url: str, output_path: Path, source_file: str | None = None) -> list[dict]:
    """
    Scan a URL for accessibility violations.

    Args:
        url: The URL to scan
        output_path: Path where results will be written
        source_file: Optional source file name for tracking

    Returns:
        List of violation dictionaries

    Raises:
        RuntimeError: If the scan fails
    """
    # Implementation
    pass
```

### Avoid

- Magic numbers (use constants)
- Global state
- Overly complex functions (keep under 50 lines)
- Nested conditionals deeper than 3 levels

### Project-Specific Conventions

- **Service classes**: Should be instantiable and stateless where possible
- **Dependency injection**: Services receive dependencies via constructor
- **Path handling**: Use `pathlib.Path`, not string concatenation
- **Logging**: Use the `logging` module, not `print()`
- **Error handling**: Be specific with exceptions, don't catch bare `Exception`

## Testing Requirements

### Unit Tests

Required for:
- New service classes
- New functions in existing services
- Bug fixes (add regression test)
- Changes to core logic

Test file naming: `tests/test_<module_name>.py`

Example:
```python
import pytest
from pathlib import Path
from scanner.services.zip_service import ZipService

def test_zip_extraction(tmp_path: Path):
    """Test that ZipService extracts files correctly."""
    # Arrange
    service = ZipService(unzip_dir=tmp_path / "unzip", scan_dir=tmp_path / "scan")

    # Act
    service.run()

    # Assert
    assert (tmp_path / "scan" / "index.html").exists()
```

### Integration Tests

Required for:
- Pipeline changes
- Container changes
- Service interactions
- Report generation changes

Update golden files if output format changes:
```bash
# Run integration tests to generate new results
python -m scanner.container.integration

# Manually review and update golden files in:
# tests/assets/html_sets/*/golden_results/
```

### Test Coverage

- Aim for >80% coverage on new code
- Check coverage report: `htmlcov/index.html`
- Don't sacrifice clarity for coverage

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/).

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc. (no code change)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates

### Examples

```
feat(api): add URL validation for scan endpoint

Add validation to reject localhost and private IP addresses
in the /api/scan/url endpoint to prevent SSRF attacks.

Closes #123
```

```
fix(pipeline): ensure HTTP server stops on exception

The HTTP server was not being stopped when the pipeline
encountered an error. Moved stop() call to finally block.

Fixes #456
```

```
docs(readme): add comparison table with other tools

Added a table comparing a11y-scanner to axe DevTools,
Pa11y, and Lighthouse to help users choose the right tool.
```

### Scope Examples

- `api` - API server changes
- `pipeline` - Pipeline orchestration
- `services` - Service layer changes
- `reporting` - Report generation
- `container` - Docker/container management
- `ci` - CI/CD changes
- `deps` - Dependency updates

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] Code is formatted with Black
- [ ] No linting errors from Ruff
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated
- [ ] Commit messages follow conventions
- [ ] Branch is up to date with main

### PR Description Template

```markdown
## Description
Brief description of changes

## Motivation and Context
Why is this change needed? What problem does it solve?

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran and how to reproduce them.

## Screenshots (if applicable)
Add screenshots of report changes or UI updates

## Checklist
- [ ] My code follows the code style of this project
- [ ] I have updated the documentation accordingly
- [ ] I have added tests to cover my changes
- [ ] All new and existing tests passed
- [ ] I have updated CHANGELOG.md
```

### Review Process

1. A maintainer will review your PR within 5 business days
2. Address any feedback or requested changes
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

### After Your PR is Merged

1. Delete your feature branch
2. Update your fork:
   ```bash
   git checkout main
   git pull upstream main
   git push origin main
   ```

## Reporting Bugs

### Before Reporting

1. Check [existing issues](https://github.com/mattboback/a11y-scanner/issues)
2. Try the latest version of main
3. Review the [troubleshooting guide](README.md#troubleshooting)

### Bug Report Template

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) when creating an issue.

Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, Docker version)
- Relevant logs or error messages

## Suggesting Enhancements

### Before Suggesting

1. Check if the feature already exists
2. Check [existing feature requests](https://github.com/mattboback/a11y-scanner/issues?q=is%3Aissue+label%3Aenhancement)
3. Consider if it fits the project scope

### Enhancement Request Template

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md).

Include:
- Problem statement
- Proposed solution
- Alternatives considered
- Additional context (mockups, examples)

## Questions?

- Open a [GitHub Discussion](https://github.com/mattboback/a11y-scanner/discussions)
- Check the [documentation](docs/)
- Review [existing issues](https://github.com/mattboback/a11y-scanner/issues)

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in relevant documentation

Thank you for contributing to a11y-scanner! 🎉
