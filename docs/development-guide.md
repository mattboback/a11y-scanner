# Development Guide

This guide covers the day-to-day workflow for hacking on `a11y-scanner`.
It assumes you are working from a cloned repository and have Docker running locally.

## Local Environment

1. Create a virtual environment and install the editable package with dev extras:
   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. If you prefer `make`, the same setup is available via `make install` (which depends on `make venv`).

### Data directories

Runtime artifacts are written under `data/`:
- `data/unzip` — incoming zip archives and extracted files.
- `data/scan` — temporary working directory used by the pipeline.
- `data/results` — JSON artifacts and screenshots for each violation.
- `data/reports` — rendered HTML reports (`latest.html` is the consolidated view).

Use `make clean` to reset these directories without touching your source tree.

## Common Tasks

- **Build the Docker image** (installs Playwright browsers inside the container):
  ```bash
  python -m scanner.container.runner prepare
  # or
  make docker-prepare
  ```
- **Scan a sample site** end-to-end:
  ```bash
  ./scripts/create_test_site.sh
  python -m scanner.container.runner run
  # report: data/reports/latest.html
  ```
- **Serve the API** for manual uploads and live scans:
  ```bash
  python -m scanner.container.runner serve --port 8008
  # or
  make serve
  ```

## Testing

- **Unit tests (fast path):**
  ```bash
  pytest -k "not test_playwright_axe_service"
  ```
  The Playwright-heavy test is skipped here to avoid downloading browsers on the host.
- **Full test suite inside Docker:**
  ```bash
  python -m scanner.container.integration
  # or
  make integration
  ```
- **Reporting smoke test:**
  ```bash
  ./scripts/test_reporting.sh
  # or
  make test-reporting
  ```

Coverage reports are emitted to `htmlcov/` because of the `--cov-report=html` flag in `pyproject.toml`.

## Linting & Formatting

The project uses `black` and `ruff` (installed with the `dev` extras).

```bash
black src tests
ruff check src tests
```

To auto-fix lint issues:
```bash
ruff check src tests --fix
```

## Pull Request Checklist

Before opening a PR:
- Ensure unit tests pass locally.
- Run the Docker-based integration suite if you touched scanning/container code.
- Format with `black` and lint with `ruff`.
- Update documentation and CHANGELOG entries (if applicable).
- Provide sample output or screenshots when changing report templates.

## Troubleshooting

- **Playwright fails to launch:** ensure you ran `python -m scanner.container.runner prepare` after updating dependencies.
- **Missing report artifacts:** check the `data/results` directory. The pipeline skips files when no HTML pages are discovered.
- **Docker permissions issues:** confirm your user can access the Docker socket (`docker ps` should succeed outside the repo).

For more detail on how the system is wired together, see `docs/architecture-overview.md`.
