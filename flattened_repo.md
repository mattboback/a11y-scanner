# Repository: a11y_scanner_v1

## File: a11y_scanner_v1/README.md

<!-- This is the main README file. It's shown at the top for context. -->

````markdown
# a11y-scanner (Docker-only)

> Static-site Accessibility Scanner
>
> Powered by Python 3.10+, Playwright, Docker, and axe-core.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![axe-core](https://img.shields.io/badge/axe--core-Playwright-green)](https://github.com/dequelabs/axe-core)

---

## 📚 Documentation

- [Development Guide](docs/development-guide.md) — local setup, testing, linting, and troubleshooting.
- [Architecture Overview](docs/architecture-overview.md) — how the container runner, pipeline, and reporting layers fit together.
- [Contributors](CONTRIBUTORS.md) — expectations for new pull requests and ways to get involved.

---

## 🚦 Important: Docker-Only Execution

This project is intentionally containerized. The CLI guards will exit if you attempt to run them directly on your host machine.

- ✅ Run via the Docker SDK runner provided in this repo.
- ❌ Do not run `python -m scanner.main` on bare metal.

Why? Consistent Playwright dependencies, reproducible results, and a clean developer experience.

---

## 1 · Overview

This project provides an open-source, self-hostable system to run automated accessibility audits on static websites. It is designed to be integrated into CI/CD and executed uniformly in a Docker container.

The container is prepared programmatically via the Docker SDK (no docker-compose required).

---

## 2 · How It Works

1. Place a `site.zip` archive under `data/unzip` or upload it via the API.
2. The scanner extracts the site to a temp directory.
3. It starts a local HTTP server serving the extracted files.
4. It visits each `.html` page with Playwright + axe-core and audits a11y.
5. It writes full JSON reports (and screenshots) to `data/results`.
6. It renders a consolidated HTML report under `data/reports/latest.html`.

---

## 3 · Quick Start (Docker Runner)

Prereqs:

- Docker Engine running
- Python 3.10+ (host, for the thin wrapper that orchestrates Docker)

```bash
# 0) (first time) create a venv and install the local package
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

# 1) Build the cached Docker image with deps pre-installed (first run may take a bit)
python -m scanner.container.runner prepare

# 2) Create a simple sample site (zipped to data/unzip/site.zip)
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path("data/unzip"); root.mkdir(parents=True, exist_ok=True)
site = root/"site_tmp"; site.mkdir(parents=True, exist_ok=True)
(site/"index.html").write_text("""<!doctype html>
<html lang=en><head><meta charset=utf-8><title>Sample</title></head>
<body><h1>Sample Page</h1><img src="logo.png"><p class="low-contrast-text">Low contrast text</p></body>
</html>""", encoding="utf-8")
with ZipFile(root/"site.zip", "w", ZIP_DEFLATED) as z:
    for p in site.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(site))
print("Wrote", (root/"site.zip").resolve())
PY

# 3) Run the scan
python -m scanner.container.runner run

# 4) Inspect results
ls -la data/results
# macOS
open data/reports/latest.html
# Linux
# xdg-open data/reports/latest.html
```

### B · Long-running API Server (Demo Ready)

Start the FastAPI server in a Docker container and expose port 8008 on the host:

```bash
python -m scanner.container.runner serve --port 8008
# or
make serve
```

Upload a zip and view the report:

```bash
# Reuse the sample site from above (data/unzip/site.zip)
curl -F "file=@data/unzip/site.zip" http://127.0.0.1:8008/api/scan/zip
# Open report
open http://127.0.0.1:8008/reports/latest.html   # macOS
# xdg-open http://127.0.0.1:8008/reports/latest.html  # Linux
```

You can also scan live URLs directly:

```bash
curl -X POST http://127.0.0.1:8008/api/scan/url \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://example.com/"]}'
```

---

## 4 · Project Layout

```
.
├── data/                 # Runtime artifacts (zip inputs, results, reports)
├── docker/               # Dockerfile assets for the runner image
├── scripts/              # Helper scripts for sample sites, reporting, tests
├── src/scanner/          # Application code (pipeline, services, web server)
├── tests/                # Unit and integration tests
├── Makefile              # Developer shortcuts (install, integration, serve)
└── pyproject.toml        # Packaging metadata, dependencies, tooling config
```

Key docs: `docs/development-guide.md` and `docs/architecture-overview.md` expand on this structure.

---

## 5 · Reporting

- Consolidated report template: `scanner/templates/a11y_report.html.j2` (Jinja2).
- The reporting system aggregates JSON artifacts in `data/results` and writes a single HTML report to `data/reports/latest.html`.
- Each rule group shows: rule id/impact, description, link to docs, occurrences (URL/source, selector, HTML snippet, screenshot).
- Raw artifacts (JSON/PNG) are linked.

Local reporting smoke test (no Docker):

```bash
python - <<'PY'
from pathlib import Path
from scanner.reporting.jinja_report import build_report
out = Path("test_data/reports/test_report.html")
out.parent.mkdir(parents=True, exist_ok=True)
build_report(Path("test_data/results"), out, title="Test Accessibility Report")
print(out.resolve())
PY
```

Note on template loading:

- At runtime, templates are loaded from installed package resources.
- During development (editable installs), it falls back to the source tree for velocity.

---

## 6 · Makefile Shortcuts

```bash
make docker-prepare   # Build/rebuild the cached image
make serve            # Launch the API server in Docker on port 8008
make integration      # Run Docker-based integration suite
make clean            # Reset data dirs
make test-reporting   # Test the reporting system locally
```

---

## 7 · Tests

Unit tests can be run locally. The Playwright-heavy test may require browsers installed.

```bash
# Run fast tests (skip the real-browser test)
pytest -q -k 'not test_playwright_axe_service'

# Or run the full Docker-backed integration suite
python -m scanner.container.integration
```

Notes

    Results are written below data/.

    The container runner marks the environment with A11Y_SCANNER_IN_CONTAINER=1.

    The app checks this and exits if not set.

    Playwright browsers and dependencies are managed inside the container image.

    The API server serves:

        Raw JSON/screenshot artifacts at /results

        Consolidated HTML report at /reports/latest.html

---

## 8 · Validation Checklist

1. Local reporting smoke test (no Docker)
   - Generate: see “Reporting” snippet above.
   - Validate: file exists (>1KB), contains “Test Accessibility Report”, “Pages Scanned”, “Total Violations”, and sample rule ids (e.g., image-alt, color-contrast).
2. Unit tests (host)
   - Run: `pytest -q -k 'not test_playwright_axe_service'`
   - Expect: reporting/services/pipeline/settings tests pass locally. The Playwright test requires installed browsers.
3. End-to-end scan (Docker)
   - Prepare: `python -m scanner.container.runner prepare`
   - Run: `python -m scanner.container.runner run`
   - Validate: `data/results/*.json` and screenshots exist; `data/reports/latest.html` renders consolidated report.
4. API mode (Docker)
   - Start: `python -m scanner.container.runner serve --port 8008`
   - Upload: `curl -F "file=@data/unzip/site.zip" http://127.0.0.1:8008/api/scan/zip`
   - View: open `http://127.0.0.1:8008/reports/latest.html`

---

## 9 · Breadcrumbs: Next Potential Steps

- Add helper scripts
  - `scripts/create_test_site.sh` to generate and zip a sample site to `data/unzip/site.zip`.
  - `scripts/test_reporting.sh` to build a local HTML report from `test_data/results`.
- Reuse a single Playwright browser
  - Keep one browser/context per run and one page per scan to reduce overhead; optionally add concurrency.
- Harden ZipService
  - Prevent Zip Slip path traversal by validating archive members before extraction in `src/scanner/services/zip_service.py`.
- Persist source file in JSON artifacts
  - Thread the relative source path into the saved JSON (alongside `scanned_url`) to enrich reporting.
- CLI and config options
  - Include/exclude patterns, concurrency level, headless toggle, timeouts, viewport, and screenshot behavior.
- CI integration
  - Optional JUnit/SARIF export, severity thresholds to set exit code, and a GitHub Action example.
- API hardening
  - Upload size limits, basic auth or tokens, rate limiting, and clearer error responses.
- Report UX
  - Filters (by impact/rule), grouping by page, CSV/JSON export of summary, and pagination for large sites.
- Testing ergonomics
  - Add a pytest marker to skip the Playwright test by default unless `RUN_E2E=1` is set; document Playwright browser install steps.

---

## 🤝 Contributing

Before filing a PR, read the [Contributors guide](CONTRIBUTORS.md) and the
[Development Guide](docs/development-guide.md). These cover the expected workflow
(virtualenv, linting, tests) and how to run the Docker-backed integration suite.

````

---

## Quick Stats

- Files included: 52
- Estimated text size: 117.5KB
- Primary languages: python (25), txt (10), markdown (4), bash (4), yaml (2)
- Key directories: src/ (27), tests/ (7), scripts/ (4), data/ (2), docs/ (2)

---

## File Structure

```
├── .dockerignore
├── .github
│   └── workflows
│       └── ci.yml
├── CONTRIBUTORS.md
├── LICENSE
├── Makefile
├── README.md
├── data
│   ├── scan
│   │   └── index.html
│   └── unzip
│       └── site_tmp
│           └── index.html
├── docker
│   └── Dockerfile
├── docker-compose.yml
├── docs
│   ├── architecture-overview.md
│   └── development-guide.md
├── pyproject.toml
├── scan_live_site.py
├── scripts
│   ├── create_test_site.sh
│   ├── run_integration_tests.sh
│   ├── test_reporting.sh
│   └── update_golden_files.sh
├── src
│   ├── a11y_scanner.egg-info
│   │   ├── SOURCES.txt
│   │   ├── dependency_links.txt
│   │   ├── entry_points.txt
│   │   ├── requires.txt
│   │   └── top_level.txt
│   ├── python_scanner.egg-info
│   │   ├── SOURCES.txt
│   │   ├── dependency_links.txt
│   │   ├── entry_points.txt
│   │   ├── requires.txt
│   │   └── top_level.txt
│   └── scanner
│       ├── __init__.py
│       ├── container
│       │   ├── __init__.py
│       │   ├── integration.py
│       │   ├── manager.py
│       │   └── runner.py
│       ├── core
│       │   ├── logging_setup.py
│       │   └── settings.py
│       ├── main.py
│       ├── pipeline.py
│       ├── reporting
│       │   ├── __init__.py
│       │   └── jinja_report.py
│       ├── services
│       │   ├── html_discovery_service.py
│       │   ├── http_service.py
│       │   ├── playwright_axe_service.py
│       │   └── zip_service.py
│       ├── templates
│       │   └── __init__.py
│       └── web
│           └── server.py
└── tests
    ├── services
    │   └── test_playwright_axe_service.py
    ├── test_html_discovery_service.py
    ├── test_http_service.py
    ├── test_pipeline.py
    ├── test_reporting.py
    ├── test_settings.py
    └── test_zip_service.py
```

---

## File Contents

### File: a11y_scanner_v1/.dockerignore

<!-- Auto-extracted from leading comments/docstrings -->
> Git --- Exclude the entire Git directory and related files

<!-- This is the file '.dockerignore', a text file. -->

```
# --- Git ---
# Exclude the entire Git directory and related files
.git/
.gitignore
.gitattributes

# --- Docker ---
# Exclude Docker related files themselves from the context
.dockerignore
Dockerfile*
docker-compose*.yml

# --- Python Virtual Environments ---
# Exclude local virtual environments
env/
venv/
.venv/
ENV/

# --- Python Cache / Build Artifacts ---
# Exclude bytecode, build directories, distributions etc.
# These will be generated *inside* the container if needed.
__pycache__/
*.py[cod]
build/
dist/
*.egg-info/
wheels/
.installed.cfg
*.egg

# --- Test artifacts / cache ---
# Exclude test results, coverage data, and caches from the context
.pytest_cache/
.coverage
.coverage.*
htmlcov/
nosetests.xml
coverage.xml

# --- Tests Directory ---
# Exclude the tests themselves unless you plan to run tests
# *inside* the final built Docker image (less common for simple scripts).
# Including tests increases the build context size.
tests/

# --- Project Specific ---

# Local environment configuration - Use Docker env vars or config files instead
# These should NOT be copied into the image.
.env*
!.env.example

# Data directory - Mount via volume at runtime, NEVER include in build context
data/

# Log files
*.log
logs/

# --- IDE / Editor / OS ---
# Exclude configuration and temporary files specific to local development setups
.idea/
.vscode/
*.sublime-project
*.sublime-workspace
.DS_Store
Thumbs.db
*.bak
*.swp
*~

# --- Documentation/Other ---
# Often exclude documentation source files if not needed in the final image
# docs/
# notebooks/

websiteToTest
data
data_parse

# Venvs and caches
.venv
venv
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
ruff_cache/

# Git and IDE
.git
.gitignore
.vscode
.idea
.DS_Store

# Build artifacts
dist
build
*.egg-info

# Tests (not needed in runtime image)
tests

# Local data (volume-mounted at runtime)
data/*
!data/.gitkeep

# Playwright/Reports
playwright-report
test-results

```

### File: a11y_scanner_v1/.github/workflows/ci.yml

<!-- This is the file '.github/workflows/ci.yml', a yaml file. -->

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
          cache-dependency-path: "pyproject.toml"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run format and lint checks
        run: |
          black --check src tests
          ruff check src tests

  tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"
          cache-dependency-path: "pyproject.toml"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run pytest (skip browser-heavy test)
        run: pytest -q -k "not test_playwright_axe_service"

```

### File: a11y_scanner_v1/CONTRIBUTORS.md

<!-- This is the file 'CONTRIBUTORS.md', a markdown file. -->

```markdown
# Contributors

Thanks to everyone investing time in `a11y-scanner`. Add yourself in a pull
request after your first contribution so the list stays up to date.

## Core Team

- Matt — project creator and maintainer (`pyproject.toml` author).

## How to Contribute

1. Discuss substantial changes in an issue before opening a pull request.
2. Fork the repository and work from a feature branch.
3. Follow the workflow documented in `docs/development-guide.md`:
   - create/activate the local virtual environment
   - run `pip install -e ".[dev]"`
   - execute unit tests and linting locally
4. Run Docker-backed integration tests (`python -m scanner.container.integration`)
   when changing the container, scanning pipeline, or Playwright services.
5. Update documentation and this file as part of your PR when applicable.

## Pull Request Expectations

- Include focused commits with descriptive messages.
- Link related issues in the PR description.
- Provide context for UI-facing changes (screenshots of `data/reports/latest.html`
  or sample JSON artifacts).
- Ensure CI passes (GitHub Actions run linting and tests automatically).

## Code of Conduct

Treat all contributors and users with respect. Be patient with questions and
assume positive intent. If a situation escalates, contact the maintainer directly
before continuing the discussion in public threads.

```

### File: a11y_scanner_v1/LICENSE

<!-- This is the file 'LICENSE', a text file. -->

```text

MIT License

Copyright (c) 2025 Matthew Boback

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

```

### File: a11y_scanner_v1/Makefile

<!-- This is the file 'Makefile', a makefile file. -->

```makefile
# Makefile — Docker-only workflow
PY := .venv/bin/python
.PHONY: help venv install docker-prepare scan-local integration live-scan clean serve test-reporting

help:
	@echo "Targets:"
	@echo "  venv            Create local virtualenv (.venv)"
	@echo "  install         Install project in editable mode with dev deps into .venv"
	@echo "  docker-prepare  Build/rebuild the cached Docker image"
	@echo "  scan-local      Package sample site and run scanner in Docker"
	@echo "  integration     Run integration suite in Docker"
	@echo "  live-scan       Run scan_live_site.py in Docker (uses container entrypoint)"
	@echo "  serve           Run the long-lived FastAPI server in Docker (port 8008)"
	@echo "  clean           Remove data artifacts"
	@echo "  test-reporting  Test the reporting system locally"

venv:
	python3 -m venv .venv

install: venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"

docker-prepare: install
	$(PY) -m scanner.container.runner prepare

scan-local: install
	./scripts/create_test_site.sh
	$(PY) -m scanner.container.runner run

integration: install
	$(PY) -m scanner.container.integration

# Note: live-scan uses the same container entrypoint (scanner.main).
# To run scan_live_site.py specifically inside the container, you can
# temporarily switch the container ENTRYPOINT, or keep scan_live_site
# as a separate command you exec inside. For simplicity we keep main.
live-scan: install
	@echo "Running main pipeline (see scan_live_site.py for a live variant)"
	$(PY) -m scanner.container.runner run

serve: install
	@echo "Starting FastAPI server at http://127.0.0.1:8008 (Ctrl+C to stop)"
	$(PY) -m scanner.container.runner serve --port 8008

clean:
	rm -rf data/scan data/results data/unzip data/live_results data/reports
	mkdir -p data/unzip data/results data/scan data/live_results data/reports

test-reporting: install
	@echo "Testing reporting system..."
	./scripts/test_reporting.sh

```

### File: a11y_scanner_v1/README.md

```markdown
<!-- This is a reference to the README file, which is shown in full at the top of the document -->
# Content omitted — full README shown at top
```

### File: a11y_scanner_v1/data/scan/index.html

<!-- This is the file 'data/scan/index.html', a html file. -->

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Sample A11y Site</title>
    <style>
      .low-contrast-text { color: #999; background: #888; }
    </style>
  </head>
  <body>
    <h1>Sample Page</h1>
    <img src="logo.png">
    <p class="low-contrast-text">Low contrast text</p>
  </body>
</html>

```

### File: a11y_scanner_v1/data/unzip/site_tmp/index.html

<!-- This is the file 'data/unzip/site_tmp/index.html', a html file. -->

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Sample A11y Site</title>
    <style>
      .low-contrast-text { color: #999; background: #888; }
    </style>
  </head>
  <body>
    <h1>Sample Page</h1>
    <img src="logo.png">
    <p class="low-contrast-text">Low contrast text</p>
  </body>
</html>

```

### File: a11y_scanner_v1/docker-compose.yml

<!-- This is the file 'docker-compose.yml', a yaml file. -->

```yaml
services:
  scanner:
    build:
      context: .
      dockerfile: docker/Dockerfile
    volumes:
      - ./data:/home/pwuser/data
    shm_size: "2gb"

  scanner-debug:
    build:
      context: .
      dockerfile: docker/Dockerfile
    volumes:
      - ./data:/home/pwuser/data
    shm_size: "2gb"
    entrypoint: ["tail", "-f", "/dev/null"]

```

### File: a11y_scanner_v1/docker/Dockerfile

<!-- This is the file 'docker/Dockerfile', a dockerfile file. -->

```dockerfile
FROM mcr.microsoft.com/playwright:v1.54.0-jammy

ENV VIRTUAL_ENV=/home/pwuser/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip python3.10-venv && \
    rm -rf /var/lib/apt/lists/*

USER pwuser

WORKDIR /home/pwuser

RUN python3 -m venv $VIRTUAL_ENV

COPY --chown=pwuser:pwuser . .

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "scanner.main"]

```

### File: a11y_scanner_v1/docs/architecture-overview.md

<!-- This is the file 'docs/architecture-overview.md', a markdown file. -->

````markdown
# Architecture Overview

The accessibility scanner is split into three major layers: orchestration (Docker
and CLI tooling), the scanning pipeline, and reporting/web delivery. This
document highlights the key modules so new contributors can navigate the codebase
quickly.

## High-Level Flow

1. **Container orchestration** uses `scanner.container.runner` to build a Docker
   image with Playwright browsers and execute commands inside it via the Docker SDK.
2. The **pipeline** (`scanner.pipeline.Pipeline`) prepares the workspace, hosts
   the extracted site locally, and iterates over each HTML page.
3. **Services** underneath the pipeline perform specialized work:
   - `ZipService` unpacks `data/unzip/site.zip` into `data/scan`.
   - `HtmlDiscoveryService` enumerates HTML files and relative paths.
   - `HttpService` serves `data/scan` over HTTP so Playwright can access
     `http://127.0.0.1:<port>/...` URLs.
   - `PlaywrightAxeService` launches Chromium via `playwright.sync_api`, runs
     `axe-playwright-python`, captures screenshots, and writes JSON artifacts.
4. **Reporting** composes Jinja templates into consolidated HTML under
   `data/reports/` and is reused by the FastAPI server (`scanner.web.server`).

The diagram below summarizes the relationships:

```
┌────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌────────────┐
│ CLI / Make │──▶──│ container.runner │──▶──│ pipeline.Pipeline│──▶──│ report HTML │
└────────────┘     └────────┬─────────┘     └──────┬──────────┘     └──────┬─────┘
                            │                    ┌──▼────────┐             │
                            │                    │ZipService │             │
                            │                    ├───────────┤             │
                            │                    │HtmlDiscovery           │
                            │                    ├───────────┤             │
                            │                    │HttpService │             │
                            │                    ├───────────┤             │
                            │                    │Playwright  │             │
                            │                    │AxeService  │             │
                            │                    └─────▲──────┘             │
                            │                          │                    │
                            │                    ┌─────┴──────┐             │
                            └────────────────────│ JSON + PNG │◀────────────┘
                                                 └────────────┘
```

## Key Entry Points

- `scan_live_site.py`: standalone script that proxies to the same container runner.
- `scanner/main.py`: ensures the process only runs inside Docker (`A11Y_SCANNER_IN_CONTAINER`).
- `scanner/web/server.py`: FastAPI app exposing `/api/scan/zip`, `/api/scan/url`,
  and `/reports/latest.html`.
- `scanner/container/integration.py`: convenience harness for running end-to-end
  tests inside the prepared container.

## Configuration & Settings

The `Settings` object (`scanner.core.settings.Settings`) is the central place for
filesystem paths, ports, and feature flags. Values default to directories under
`data/` but respect environment variables when running inside Docker.

## Reporting Stack

- Template source lives in `scanner/templates/`.
- `scanner.reporting.jinja_report.build_report` renders aggregated results into
  `data/reports/latest.html`.
- Static assets (screenshots, JSON) are linked relative to `data/results/`.

## Extending the Pipeline

When adding new capabilities:
- Place reusable behavior in `scanner/services/` and keep `Pipeline` focused on
  orchestration.
- Thread new configuration through `Settings` rather than hard-coding paths.
- Ensure JSON artifacts stay backward compatible; downstream consumers rely on
  keys like `scanned_url` and `source_file`.

If the pipeline shape changes, update the integration suite and documentation in
`README.md` and `docs/development-guide.md`.

````

### File: a11y_scanner_v1/docs/development-guide.md

<!-- This is the file 'docs/development-guide.md', a markdown file. -->

````markdown
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

````

### File: a11y_scanner_v1/pyproject.toml

<!-- This is the file 'pyproject.toml', a toml file. -->

```toml
[build-system]
requires = ["setuptools>=61", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "a11y-scanner"
version = "0.4.0"
description = "A web accessibility scanner using Playwright and axe-core for comprehensive testing."
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [{ name = "Matt", email = "matt@example.com" }]

dependencies = [
  "rich>=13.0.0",
  "axe-playwright-python==0.1.4",
  "playwright==1.54.0",
  "docker>=6.0.0",
  "jinja2>=3.1.3",
  "fastapi>=0.111.0",
  "uvicorn[standard]>=0.30.0",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
test = ["pytest>=8.0", "pyfakefs", "pytest-cov", "requests", "httpx"]
dev = ["a11y-scanner[test]", "black", "ruff"]

[tool.setuptools.package-data]
"scanner" = ["templates/*.j2"]
[project.scripts]
scanner = "scanner.main:main"
scanner-docker = "scanner.container.runner:main"
scanner-integration = "scanner.container.integration:main"
scanner-api = "scanner.web.server:run"

[tool.setuptools.packages.find]
where = ["src"]

[tool.black]
line-length = 88
target-version = ["py310"]

[tool.ruff]
line-length = 88
target-version = "py310"
select = ["E", "F", "W", "I", "B", "UP"]
exclude = ["tests"]

[tool.pytest.ini_options]
addopts = "-ra -q --strict-markers --cov=src --cov-report=html"
testpaths = ["tests"]
log_cli = true
log_cli_level = "INFO"

```

### File: a11y_scanner_v1/scan_live_site.py

<!-- This is the file 'scan_live_site.py', a python file. -->

```python
# scan_live_site.py
import logging
import os
import sys

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.reporting.jinja_report import build_report
from scanner.services.playwright_axe_service import PlaywrightAxeService

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"

# --- Configuration ---
BASE_URL = "https://loftcs.org/"
PAGES_TO_SCAN = ["/"]
# --- End Configuration ---

log = logging.getLogger(__name__)


def _assert_docker_context() -> None:
    """Ensure we are running inside the Docker container."""
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        print(
            "\n[ERROR] This CLI is Docker-only.\n"
            "Run via the container runner instead:\n"
            "  python -m scanner.container.runner prepare\n"
            "  python -m scanner.container.runner run\n",
            file=sys.stderr,
        )
        sys.exit(2)


def create_safe_filename(base_url: str, page_path: str) -> str:
    """Creates a filesystem-safe filename from a URL path."""
    domain = base_url.replace("https://", "").replace("http://", "")
    path_part = "root" if page_path == "/" else page_path.strip("/").replace("/", "_")
    return f"{domain}_{path_part}.json"


def main():
    """Scan a predefined list of URLs on a live website (Docker-only)."""
    _assert_docker_context()
    setup_logging(level=logging.INFO)
    log.info("--- Starting Live A11y Site Scanner ---")
    log.info("Target site: %s", BASE_URL)
    settings = Settings()
    live_results_dir = settings.data_dir / "live_results"
    live_results_dir.mkdir(parents=True, exist_ok=True)
    log.info("Results will be saved in: %s", live_results_dir.resolve())

    reports_dir = settings.data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    axe_service = PlaywrightAxeService()
    total_violations_count = 0
    try:
        for page_path in PAGES_TO_SCAN:
            url_to_scan = f"{BASE_URL}{page_path}"
            report_filename = create_safe_filename(BASE_URL, page_path)
            report_path = live_results_dir / report_filename
            log.info("--- Scanning page: %s ---", url_to_scan)
            try:
                violations = axe_service.scan_url(url_to_scan, report_path)
                if violations:
                    log.warning(
                        "Found %d violation(s) on %s", len(violations), url_to_scan
                    )
                    total_violations_count += len(violations)
                else:
                    log.info("✅ No violations found on %s", url_to_scan)
            except Exception as e:
                log.error("Failed to scan %s: %s", url_to_scan, e, exc_info=True)
                continue

        # Generate consolidated HTML report
        output_html = reports_dir / "latest.html"
        build_report(
            live_results_dir, output_html, title="Accessibility Report (Live Site)"
        )
        log.info("Consolidated HTML report generated at: %s", output_html)

        log.info("--- Live Scan Finished ---")
        pages_count = len(PAGES_TO_SCAN)
        if total_violations_count > 0:
            print("\n--- Accessibility Scan Summary ---")
            print(
                f"Found a total of {total_violations_count} accessibility violation(s)."
            )
            print(f"Scanned {pages_count} page(s).")
            print(f"Detailed JSON reports: {live_results_dir.resolve()}")
            print(f"HTML report available at: {output_html}")
        else:
            print(
                "\n✅ Excellent! No accessibility violations were found on the scanned pages."
            )
            print(f"Full report available at: {output_html}")
        sys.exit(0)
    except Exception:
        log.exception("An unexpected error occurred during the live scan.")
        sys.exit(1)


if __name__ == "__main__":
    main()

```

### File: a11y_scanner_v1/scripts/create_test_site.sh

<!-- This is the file 'scripts/create_test_site.sh', a bash file. -->

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
UNZIP_DIR="$ROOT_DIR/data/unzip"
TMP_DIR="$UNZIP_DIR/site_tmp"
ZIP_PATH="$UNZIP_DIR/site.zip"

mkdir -p "$TMP_DIR"

cat >"$TMP_DIR/index.html" <<'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Sample A11y Site</title>
    <style>
      .low-contrast-text { color: #999; background: #888; }
    </style>
  </head>
  <body>
    <h1>Sample Page</h1>
    <img src="logo.png">
    <p class="low-contrast-text">Low contrast text</p>
  </body>
</html>
HTML

echo "Zipping sample site to $ZIP_PATH"
rm -f "$ZIP_PATH"
(cd "$TMP_DIR" && zip -r "$ZIP_PATH" . >/dev/null)

echo "✅ Created $ZIP_PATH"

```

### File: a11y_scanner_v1/scripts/run_integration_tests.sh

<!-- This is the file 'scripts/run_integration_tests.sh', a bash file. -->

```bash
#!/usr/bin/env bash
set -euo pipefail

# This wrapper now delegates to the Python-based integration runner,
# which uses the Docker SDK for Python (no docker-compose or Dockerfiles).
python -m scanner.container.integration

```

### File: a11y_scanner_v1/scripts/test_reporting.sh

<!-- This is the file 'scripts/test_reporting.sh', a bash file. -->

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"

PYTHON="${PYTHON:-python}"

echo "Building local report from test_data/results -> test_data/reports/test_report.html"

$PYTHON - <<'PY'
from pathlib import Path
from scanner.reporting.jinja_report import build_report
base = Path('test_data')
results = base / 'results'
out = base / 'reports' / 'test_report.html'
out.parent.mkdir(parents=True, exist_ok=True)
res = build_report(results, out, title='Test Accessibility Report')
print('✅ Wrote', res.resolve())
PY


```

### File: a11y_scanner_v1/scripts/update_golden_files.sh

<!-- This is the file 'scripts/update_golden_files.sh', a bash file. -->

```bash
#!/usr/bin/env bash
set -euo pipefail

# Rebuild all golden files to match the current raw per-page reports contract:
# equivalent to: jq -s 'sort_by(.scanned_url)' data/results/*.json

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
ASSETS_DIR="$ROOT/tests/assets/html_sets"
DATA_DIR="$ROOT/data"
UNZIP_DIR="$DATA_DIR/unzip"
RESULTS_DIR="$DATA_DIR/results"

echo "--- Updating golden files ---"

# Make sure the Playwright image is present at least once
python - <<'PY'
from scanner.container.manager import ContainerManager, find_project_root
root = find_project_root()
m = ContainerManager(project_root=root)
if hasattr(m, "ensure_image"):
    m.ensure_image()
else:
    m.ensure_base_image()
print("[prep] Base image ensured.")
PY

for case_dir in "$ASSETS_DIR"/*; do
    [ -d "$case_dir" ] || continue
    name="$(basename "$case_dir")"
    echo -e "\n--- Case: $name ---"

    # Clean data dirs
    rm -rf "$UNZIP_DIR" "$RESULTS_DIR" "$DATA_DIR/scan"
    mkdir -p "$UNZIP_DIR" "$RESULTS_DIR" "$DATA_DIR/scan"

    # Zip inputs (exclude golden_results)
    (cd "$case_dir" && zip -r "$UNZIP_DIR/site.zip" . -x "golden_results/*" >/dev/null)

    # Run scanner container
    python -m scanner.container.runner run >/dev/null

    # Aggregate raw reports and write golden
    GOLDEN_DIR="$case_dir/golden_results"
    mkdir -p "$GOLDEN_DIR"

    if ls "$RESULTS_DIR"/*.json >/dev/null 2>&1; then
        # requires jq
        jq -s 'sort_by(.scanned_url)' "$RESULTS_DIR"/*.json >"$GOLDEN_DIR/report.json"
    else
        echo "[]" >"$GOLDEN_DIR/report.json"
    fi

    echo "Updated: $GOLDEN_DIR/report.json"
done

echo -e "\n--- ✅ Golden files updated ---"

```

### File: a11y_scanner_v1/src/a11y_scanner.egg-info/SOURCES.txt

<!-- This is the file 'src/a11y_scanner.egg-info/SOURCES.txt', a text file. -->

```
LICENSE
README.md
pyproject.toml
src/a11y_scanner.egg-info/PKG-INFO
src/a11y_scanner.egg-info/SOURCES.txt
src/a11y_scanner.egg-info/dependency_links.txt
src/a11y_scanner.egg-info/entry_points.txt
src/a11y_scanner.egg-info/requires.txt
src/a11y_scanner.egg-info/top_level.txt
src/scanner/__init__.py
src/scanner/main.py
src/scanner/pipeline.py
src/scanner/container/__init__.py
src/scanner/container/integration.py
src/scanner/container/manager.py
src/scanner/container/runner.py
src/scanner/core/logging_setup.py
src/scanner/core/settings.py
src/scanner/reporting/__init__.py
src/scanner/reporting/jinja_report.py
src/scanner/services/html_discovery_service.py
src/scanner/services/http_service.py
src/scanner/services/playwright_axe_service.py
src/scanner/services/zip_service.py
src/scanner/templates/__init__.py
src/scanner/templates/a11y_report.html.j2
src/scanner/web/server.py
tests/test_html_discovery_service.py
tests/test_http_service.py
tests/test_pipeline.py
tests/test_reporting.py
tests/test_settings.py
tests/test_zip_service.py
```

### File: a11y_scanner_v1/src/a11y_scanner.egg-info/dependency_links.txt

<!-- This is the file 'src/a11y_scanner.egg-info/dependency_links.txt', a text file. -->

```


```

### File: a11y_scanner_v1/src/a11y_scanner.egg-info/entry_points.txt

<!-- This is the file 'src/a11y_scanner.egg-info/entry_points.txt', a text file. -->

```
[console_scripts]
scanner = scanner.main:main
scanner-api = scanner.web.server:run
scanner-docker = scanner.container.runner:main
scanner-integration = scanner.container.integration:main

```

### File: a11y_scanner_v1/src/a11y_scanner.egg-info/requires.txt

<!-- This is the file 'src/a11y_scanner.egg-info/requires.txt', a text file. -->

```
rich>=13.0.0
axe-playwright-python==0.1.4
playwright==1.54.0
docker>=6.0.0
jinja2>=3.1.3
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9

[dev]
a11y-scanner[test]
black
ruff

[test]
pytest>=8.0
pyfakefs
pytest-cov
requests
httpx

```

### File: a11y_scanner_v1/src/a11y_scanner.egg-info/top_level.txt

<!-- This is the file 'src/a11y_scanner.egg-info/top_level.txt', a text file. -->

```
scanner

```

### File: a11y_scanner_v1/src/python_scanner.egg-info/SOURCES.txt

<!-- This is the file 'src/python_scanner.egg-info/SOURCES.txt', a text file. -->

```
README.md
pyproject.toml
src/python_scanner.egg-info/PKG-INFO
src/python_scanner.egg-info/SOURCES.txt
src/python_scanner.egg-info/dependency_links.txt
src/python_scanner.egg-info/entry_points.txt
src/python_scanner.egg-info/requires.txt
src/python_scanner.egg-info/top_level.txt
src/scanner/__init__.py
src/scanner/main.py
src/scanner/pipeline.py
src/scanner/core/logging_setup.py
src/scanner/core/settings.py
src/scanner/services/html_discovery_service.py
src/scanner/services/http_service.py
src/scanner/services/playwright_axe_service.py
src/scanner/services/zip_service.py
tests/test_html_discovery_service.py
tests/test_http_service.py
tests/test_pipeline.py
tests/test_settings.py
tests/test_zip_service.py
```

### File: a11y_scanner_v1/src/python_scanner.egg-info/dependency_links.txt

<!-- This is the file 'src/python_scanner.egg-info/dependency_links.txt', a text file. -->

```


```

### File: a11y_scanner_v1/src/python_scanner.egg-info/entry_points.txt

<!-- This is the file 'src/python_scanner.egg-info/entry_points.txt', a text file. -->

```
[console_scripts]
scanner = scanner.main:main

```

### File: a11y_scanner_v1/src/python_scanner.egg-info/requires.txt

<!-- This is the file 'src/python_scanner.egg-info/requires.txt', a text file. -->

```
rich>=13.0.0
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
axe-playwright-python==0.1.4
playwright==1.54.0

[dev]
python-scanner[test]
black
ruff

[test]
pytest>=8.0
pyfakefs
pytest-cov
requests
httpx

```

### File: a11y_scanner_v1/src/python_scanner.egg-info/top_level.txt

<!-- This is the file 'src/python_scanner.egg-info/top_level.txt', a text file. -->

```
scanner

```

### File: a11y_scanner_v1/src/scanner/__init__.py

```python
# Empty file
```

### File: a11y_scanner_v1/src/scanner/container/__init__.py

<!-- This is the file 'src/scanner/container/__init__.py', a python file. -->

```python
"""
Lightweight container management utilities using the Docker SDK for Python.

This package removes the need for docker-compose and Dockerfiles by:
- pulling a Playwright Python base image,
- mounting the repository and data directories,
- installing the project into a virtualenv inside the container,
- running the scanner as `python -m scanner.main`.

Public entrypoints:
- scanner.container.runner: CLI to run a one-off scan in a container.
- scanner.container.integration: Integration test harness using the container.
"""

```

### File: a11y_scanner_v1/src/scanner/container/integration.py

<!-- This is the file 'src/scanner/container/integration.py', a python file. -->

```python
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .manager import ContainerManager, find_project_root


def _zip_test_case(src_dir: Path, zip_path: Path) -> None:
    """
    Recursively zip the contents of `src_dir` (excluding `golden_results`)
    into `zip_path`.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for p in src_dir.rglob("*"):
            if "golden_results" in p.parts:
                continue
            if p.is_file():
                arcname = p.relative_to(src_dir)
                zf.write(p, arcname)


def _clean_data_dirs(data_dir: Path) -> None:
    """Remove contents of unzip, results, and scan dirs; recreate them."""
    for name in ("unzip", "results", "scan"):
        d = data_dir / name
        if d.exists():
            for f in sorted(d.rglob("*"), reverse=True):
                try:
                    if f.is_file() or f.is_symlink():
                        f.unlink()
                    else:
                        f.rmdir()
                except Exception:
                    pass
            try:
                d.rmdir()
            except Exception:
                pass
        d.mkdir(parents=True, exist_ok=True)


def _slurp_raw_reports(results_dir: Path) -> list[dict]:
    """
    Emulate: jq -s 'sort_by(.scanned_url)' results/*.json

    Read each per-page JSON report (raw axe report we saved), ensure it has
    a top-level 'scanned_url' (we now write it in PlaywrightAxeService), and
    return a list sorted by that key.
    """
    items: list[dict] = []
    for f in sorted(results_dir.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "scanned_url" not in data:
                data["scanned_url"] = data.get("url", "")
            items.append(data)
        except Exception:
            continue

    items.sort(key=lambda d: d.get("scanned_url", ""))
    return items


def _unified_diff_str(a: str, b: str, fromfile: str, tofile: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def main() -> int:
    print("--- A11y Scanner: Integration Test Suite (Docker SDK) ---")
    project_root = find_project_root()
    tests_assets = project_root / "tests" / "assets" / "html_sets"
    data_dir = project_root / "data"
    unzip_dir = data_dir / "unzip"
    results_dir = data_dir / "results"

    if not tests_assets.exists():
        print(f"ERROR: Assets directory not found: {tests_assets}", file=sys.stderr)
        return 1

    manager = ContainerManager(project_root=project_root)
    if hasattr(manager, "ensure_image"):
        manager.ensure_image()
    else:
        manager.ensure_base_image()  # type: ignore[attr-defined]

    failures: list[str] = []

    for test_case_dir in sorted(p for p in tests_assets.iterdir() if p.is_dir()):
        test_case_name = test_case_dir.name
        print(f"\n--- Running Test Case: {test_case_name} ---")

        # 1) Prepare inputs
        print("[PREPARE] Cleaning 'data' directories and creating input zip...")
        _clean_data_dirs(data_dir)
        zip_path = unzip_dir / "site.zip"
        _zip_test_case(test_case_dir, zip_path)

        # 2) Execute
        print("[EXECUTE] Running scanner container...")
        exit_code = manager.run_scanner(stream_logs=False)
        if exit_code != 0:
            print(
                f"[ERROR] Scanner exited with code {exit_code}",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        # 3) Verify
        print("[VERIFY] Comparing results to golden file...")
        golden_file = test_case_dir / "golden_results" / "report.json"
        if not golden_file.exists():
            print(
                f"❌ FAILURE: Golden file not found for '{test_case_name}'.",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        actual_list = _slurp_raw_reports(results_dir)
        actual_str = json.dumps(actual_list, indent=2, sort_keys=True)

        try:
            with open(golden_file, encoding="utf-8") as fh:
                golden_str = fh.read()
        except Exception as e:
            print(
                f"❌ FAILURE: Could not read golden file for '{test_case_name}': {e}",
                file=sys.stderr,
            )
            failures.append(test_case_name)
            continue

        if actual_str.strip() == golden_str.strip():
            print(f"✅ SUCCESS: '{test_case_name}' matches the golden file.")
        else:
            print(
                f"❌ FAILURE: '{test_case_name}' does not match golden.",
                file=sys.stderr,
            )
            diff = _unified_diff_str(
                golden_str, actual_str, fromfile="golden", tofile="actual"
            )
            print(diff)
            failures.append(test_case_name)

    if failures:
        print("\n--- FAILURES ---")
        for name in failures:
            print(f"- {name}")
        return 1

    print("\n--- ✅ All integration tests passed successfully! ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### File: a11y_scanner_v1/src/scanner/container/manager.py

<!-- This is the file 'src/scanner/container/manager.py', a python file. -->

```python
from __future__ import annotations

import hashlib
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import docker

DEFAULT_BASE_IMAGE = "mcr.microsoft.com/playwright/python:v1.54.0-jammy"
CACHED_REPO_NAME = "a11y-scanner-cache"
CACHED_VENV_PATH = "/opt/a11y/venv"
IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"


def find_project_root(start: Optional[Path] = None) -> Path:
    """
    Locate the project root by searching upwards for pyproject.toml.
    Falls back to the current working directory if not found.
    """
    start = start or Path.cwd()
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return current


@dataclass
class ContainerConfig:
    base_image: str = DEFAULT_BASE_IMAGE
    workdir: str = "/worksrc"
    data_subdir: str = "data"
    shm_size: str = "2g"
    env: dict[str, str] | None = None

    def __post_init__(self):
        if self.env is None:
            # Keep output unbuffered and quiet apt dialogs.
            self.env = {
                "PYTHONUNBUFFERED": "1",
                "DEBIAN_FRONTEND": "noninteractive",
            }


class ContainerManager:
    """
    Run the scanner in Docker with a fast path:
      - A cached derived image with python3-venv + your package in /opt/a11y/venv
      - Cache key = sha256(pyproject.toml + contents of src/)
    Fallback slow path (no cache):
      - apt-get python3-venv + pip install on each run

    Also supports running a long-lived API server (FastAPI+Uvicorn) in a container.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        config: ContainerConfig | None = None,
    ):
        self.client = docker.from_env()
        self.project_root = (project_root or find_project_root()).resolve()
        self.config = config or ContainerConfig()

        # Detect Podman engine to avoid unsupported options (e.g., shm_size in host IPC)
        self._is_podman = False
        try:
            ver = self.client.version()
            comps = ver.get("Components") or []
            if any((c.get("Name") or "").lower().startswith("podman") for c in comps):
                self._is_podman = True
        except Exception:
            # Default to Docker-compatible behavior
            self._is_podman = False

        # Host paths
        self.repo_src = self.project_root
        self.data_dir = self.project_root / self.config.data_subdir

        # Container paths
        self.container_workdir = self.config.workdir
        self.container_repo_path = self.container_workdir  # bind repo here (ro)
        self.container_data_path = str(
            Path(self.container_workdir) / self.config.data_subdir
        )

    # ---------- generic helpers ----------

    def _host_uid_gid(self) -> tuple[int | None, int | None]:
        """Return (uid, gid) on Unix; (None, None) on Windows."""
        if platform.system().lower().startswith("win"):
            return (None, None)
        try:
            return (os.getuid(), os.getgid())
        except AttributeError:
            return (None, None)

    def _prepare_host_dirs(self) -> None:
        """Ensure host 'data' directory exists before binding it into the container."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ensure_image(self) -> None:
        self.ensure_base_image()

    def _volumes(self) -> dict[str, dict[str, str]]:
        """
        Bind mount configuration.
        - repo: read-only at /worksrc (for data dir + visibility)
        - data: read-write at /worksrc/data for inputs/outputs
        """
        # On Podman (rootless + SELinux), require relabeling (":Z") for mounts
        repo_mode = "ro,Z" if self._is_podman else "ro"
        data_mode = "rw,Z" if self._is_podman else "rw"
        return {
            str(self.repo_src): {"bind": self.container_repo_path, "mode": repo_mode},
            str(self.data_dir): {"bind": self.container_data_path, "mode": data_mode},
        }

    def ensure_base_image(self) -> None:
        """Pull the base Playwright Python image if it is not present locally."""
        try:
            self.client.images.get(self.config.base_image)
        except docker.errors.ImageNotFound:
            print(f"[container] Pulling base image: {self.config.base_image}")
            self.client.images.pull(self.config.base_image)

    # ---------- cache key / image name ----------

    def _hash_file(self, path: Path, h: "hashlib._Hash") -> None:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)

    def _compute_cache_key(self) -> str:
        """
        Compute a stable key using pyproject.toml + src/ tree.
        If either changes, the cache invalidates.
        """
        h = hashlib.sha256()
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            self._hash_file(pyproject, h)

        src_root = self.project_root / "src"
        if src_root.exists():
            for p in sorted(src_root.rglob("*")):
                if p.is_file():
                    # skip compiled junk
                    if p.suffix in {".pyc", ".pyo"}:
                        continue
                    self._hash_file(p, h)

        return h.hexdigest()

    def _cached_image_ref(self) -> tuple[str, str, str]:
        """
        Return (repository, tag, full_ref) for the cache image.
        Example:
          repo='a11y-scanner-cache', tag='9f1a0c3d2a10',
          full='a11y-scanner-cache:9f1a0c3d2a10'
        """
        key = self._compute_cache_key()[:12]
        repo = CACHED_REPO_NAME
        tag = key
        return repo, tag, f"{repo}:{tag}"

    def cached_image_exists(self) -> bool:
        _, _, full = self._cached_image_ref()
        try:
            self.client.images.get(full)
            return True
        except docker.errors.ImageNotFound:
            return False

    # ---------- prepare cached image ----------

    def prepare_cached_image(self) -> str:
        """
        Build a derived image with:
          - python3-venv installed
          - your project installed into /opt/a11y/venv
        Returns the full image ref (e.g. a11y-scanner-cache:<sha12>).
        """
        self.ensure_base_image()
        self._prepare_host_dirs()

        repo, tag, full = self._cached_image_ref()
        print(f"[cache] Building cached image {full} ...")

        volumes = self._volumes()

        # Command to install venv + your package into /opt/a11y/venv
        # We copy /worksrc (ro) -> /tmp/src so pip can write metadata.
        cmd = (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "rm -rf /var/lib/apt/lists/* && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            f"python3 -m venv {CACHED_VENV_PATH} && "
            f"{CACHED_VENV_PATH}/bin/pip install --no-cache-dir /tmp/src && "
            "true'"
        )

        # Run as root, we need apt-get and /opt writes
        run_kwargs = dict(
            command=cmd,
            working_dir=self.container_workdir,
            environment=self.config.env,
            user="root",
            volumes=volumes,
            detach=True,
            auto_remove=False,  # we will commit it
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(self.config.base_image, **run_kwargs)

        # Stream logs
        try:
            for line in container.logs(stream=True, follow=True):
                sys.stdout.buffer.write(line)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n[cache] Interrupted; stopping container...")
            container.stop(timeout=5)

        status = container.wait()
        code = int(status.get("StatusCode", 1))
        if code != 0:
            logs = container.logs().decode("utf-8", errors="ignore")
            container.remove(force=True)
            raise RuntimeError(f"[cache] Prepare failed with exit code {code}\n{logs}")

        # Commit the prepared container as a new image
        print(f"[cache] Committing image: {full}")
        container.commit(repository=repo, tag=tag)
        container.remove()

        print(f"[cache] Cached image ready: {full}")
        return full

    # ---------- run (cached / uncached) ----------

    def _command_uncached(self, chown_uid: int | None, chown_gid: int | None) -> str:
        chown_clause = ""
        if chown_uid is not None and chown_gid is not None:
            chown_clause = f" && chown -R {chown_uid}:{chown_gid} /worksrc/data"

        # Install on every run (slow path)
        return (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "python3 -m venv /tmp/venv && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            "/tmp/venv/bin/pip install --no-cache-dir /tmp/src && "
            "cd /worksrc && /tmp/venv/bin/python -m scanner.main"
            f"{chown_clause}"
            "'"
        )

    def _command_cached(self) -> str:
        # Use the preinstalled venv from the cached image
        return (
            f"bash -lc 'set -e; cd /worksrc; "
            f"{CACHED_VENV_PATH}/bin/python -m scanner.main'"
        )

    def _command_api_uncached(self) -> str:
        # Slow path for API server
        return (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "python3 -m venv /tmp/venv && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            "/tmp/venv/bin/pip install --no-cache-dir /tmp/src && "
            "cd /worksrc && /tmp/venv/bin/python -m scanner.web.server'"
        )

    def _command_api_cached(self) -> str:
        # Cached path for API server
        return (
            f"bash -lc 'set -e; cd /worksrc; "
            f"{CACHED_VENV_PATH}/bin/python -m scanner.web.server'"
        )

    def run_scanner(
        self,
        use_cache: bool = True,
        rebuild_cache: bool = False,
        stream_logs: bool = True,
    ) -> int:
        """
        Run the scanner and return its exit code.
        - use_cache: prefer cached image; auto-build if missing or rebuild requested
        - rebuild_cache: force rebuild of cached image
        """
        self._prepare_host_dirs()

        if use_cache:
            if rebuild_cache or not self.cached_image_exists():
                self.prepare_cached_image()
            _, _, cached_ref = self._cached_image_ref()
            return self._run_with_image(
                cached_ref, cached=True, stream_logs=stream_logs
            )
        else:
            # Slow path: base image + apt-get + pip each run
            self.ensure_base_image()
            return self._run_with_image(
                self.config.base_image, cached=False, stream_logs=stream_logs
            )

    def _run_with_image(self, image_ref: str, cached: bool, stream_logs: bool) -> int:
        volumes = self._volumes()

        # Merge env + mark container context for the app guards.
        env = dict(self.config.env or {})
        env[IN_CONTAINER_ENV] = IN_CONTAINER_VALUE

        if cached:
            # Run as host uid:gid so result files are owned by you.
            uid, gid = self._host_uid_gid()
            user = f"{uid}:{gid}" if uid is not None and gid is not None else None
            command = self._command_cached()
        else:
            # Need root for apt-get on the slow path
            user = "root"
            command = self._command_uncached(None, None)

        print(f"[container] Starting scanner container (image: {image_ref})...")
        run_kwargs = dict(
            command=command,
            working_dir=self.container_workdir,
            environment=env,
            user=user,
            volumes=volumes,
            detach=True,
            auto_remove=False,
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(image_ref, **run_kwargs)

        if stream_logs:
            try:
                for line in container.logs(stream=True, follow=True):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n[container] Interrupted by user, stopping container...")
                container.stop(timeout=5)

        try:
            status = container.wait()
            code = int(status.get("StatusCode", 1))
        except Exception:
            # Some engines (e.g., Podman) may remove container early; fall back to 0
            code = 0
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
        print(f"[container] Exit code: {code}")
        return code

    # ---------- API server (long-running) ----------

    def run_api_server(
        self,
        host_port: int = 8008,
        use_cache: bool = True,
        rebuild_cache: bool = False,
        stream_logs: bool = True,
    ) -> int:
        """
        Launch the FastAPI server inside a container and port-forward to host_port.
        Blocks until Ctrl+C. Returns the container exit code.
        """
        self._prepare_host_dirs()
        if use_cache:
            if rebuild_cache or not self.cached_image_exists():
                self.prepare_cached_image()
            _, _, cached_ref = self._cached_image_ref()
            return self._run_api_with_image(
                cached_ref,
                cached=True,
                host_port=host_port,
                stream_logs=stream_logs,
            )
        else:
            self.ensure_base_image()
            return self._run_api_with_image(
                self.config.base_image,
                cached=False,
                host_port=host_port,
                stream_logs=stream_logs,
            )

    def _run_api_with_image(
        self, image_ref: str, cached: bool, host_port: int, stream_logs: bool
    ) -> int:
        volumes = self._volumes()

        env = dict(self.config.env or {})
        env[IN_CONTAINER_ENV] = IN_CONTAINER_VALUE

        if cached:
            uid, gid = self._host_uid_gid()
            user = f"{uid}:{gid}" if uid is not None and gid is not None else None
            command = self._command_api_cached()
        else:
            user = "root"
            command = self._command_api_uncached()

        print(
            f"[container] Starting API server (image: {image_ref}) at http://127.0.0.1:{host_port}"
        )
        run_kwargs = dict(
            command=command,
            working_dir=self.container_workdir,
            environment=env,
            user=user,
            volumes=volumes,
            ports={"8008/tcp": host_port},
            detach=True,
            auto_remove=False,
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(image_ref, **run_kwargs)

        if stream_logs:
            try:
                for line in container.logs(stream=True, follow=True):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n[container] Stopping API server container...")
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass

        try:
            status = container.wait()
            code = int(status.get("StatusCode", 1))
        except Exception:
            code = 0
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
        print(f"[container] API server exit code: {code}")
        return code

```

### File: a11y_scanner_v1/src/scanner/container/runner.py

<!-- This is the file 'src/scanner/container/runner.py', a python file. -->

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manager import ContainerManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the a11y-scanner in a Playwright container using the Docker SDK (with caching)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # prepare cache image
    prep = subparsers.add_parser(
        "prepare", help="Build or rebuild the cached image (python3-venv + deps)."
    )
    prep.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Path to the project root (where pyproject.toml lives). Defaults to auto-discovery.",
    )

    # run scan (one-off)
    run = subparsers.add_parser(
        "run", help="Run a one-off scan (site.zip -> results) in a container."
    )
    run.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Path to the project root (where pyproject.toml lives). Defaults to auto-discovery.",
    )
    run.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (run slow path: apt-get + pip every time).",
    )
    run.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force rebuild of the cached image before running.",
    )

    # serve API (long-running)
    serve = subparsers.add_parser(
        "serve", help="Run the FastAPI server in a container and expose port 8008."
    )
    serve.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Path to the project root (where pyproject.toml lives). Defaults to auto-discovery.",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=8008,
        help="Host port to bind to the container's 8008/tcp (default: 8008).",
    )
    serve.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache (run slow path: apt-get + pip every time).",
    )
    serve.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force rebuild of the cached image before running.",
    )

    args = parser.parse_args(argv)

    if args.command == "prepare":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            ref = mgr.prepare_cached_image()
            print(ref)
            return 0
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.command == "run":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            return mgr.run_scanner(
                use_cache=not args.no_cache,
                rebuild_cache=args.rebuild_cache,
                stream_logs=True,
            )
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.command == "serve":
        mgr = ContainerManager(project_root=args.project_root)
        try:
            return mgr.run_api_server(
                host_port=args.port,
                use_cache=not args.no_cache,
                rebuild_cache=args.rebuild_cache,
                stream_logs=True,
            )
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            return 130
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

```

### File: a11y_scanner_v1/src/scanner/core/logging_setup.py

<!-- This is the file 'src/scanner/core/logging_setup.py', a python file. -->

```python
import logging
import sys


def setup_logging(level=logging.INFO):
    """Configure logging with a consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

```

### File: a11y_scanner_v1/src/scanner/core/settings.py

<!-- This is the file 'src/scanner/core/settings.py', a python file. -->

```python
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
# Basic config in case logging wasn't set up earlier
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class Settings:
    """
    Configuration settings for the scanner application.
    Paths are derived relative to a base path. By default, this is the
    current working directory, making paths portable for CLI tools.
    """

    def __init__(self, root_path: Path | None = None):
        """
        Initializes settings.
        Args:
            root_path: An optional Path object. If provided, this path
                       is used as the base for deriving data directories.
                       If None (default), paths are generated relative to the
                       current working directory (e.g., 'data/scan').
        """
        if root_path is None:
            # Default to relative paths from the CWD. This is more robust for
            # external tools and container environments.
            self._base_path: Path = Path(".")
            logger.debug("Settings initialized using relative base path: '.'")
        else:
            # For tests or specific cases, use the provided path and resolve it.
            self._base_path: Path = root_path.resolve()
            logger.debug(
                "Settings initialized using provided base path: %s", self._base_path
            )

        self._data_dir: Path = self._base_path / "data"
        self._scan_dir: Path = self._data_dir / "scan"
        self._unzip_dir: Path = self._data_dir / "unzip"
        self._results_dir: Path = self._data_dir / "results"

        self._port: int = 8000

    @property
    def base_path(self) -> Path:
        """The base path used for deriving other paths."""
        return self._base_path

    @property
    def data_dir(self) -> Path:
        """Path to the main data directory."""
        return self._data_dir

    @property
    def scan_dir(self) -> Path:
        """Path to the directory for storing extracted scan files."""
        return self._scan_dir

    @property
    def unzip_dir(self) -> Path:
        """Path to the directory containing the zip file to be processed."""
        return self._unzip_dir

    @property
    def results_dir(self) -> Path:
        """Path to the directory for storing scan results."""
        return self._results_dir

    @property
    def port(self) -> int:
        """Port number (currently unused, potential future use)."""
        return self._port

    def __repr__(self):
        # Format paths nicely for representation using repr() for quotes
        return (
            "Settings(\n"
            f"  base_path={str(self.base_path)!r},\n"
            f"  data_dir={str(self.data_dir)!r},\n"
            f"  scan_dir={str(self.scan_dir)!r},\n"
            f"  unzip_dir={str(self.unzip_dir)!r},\n"
            f"  results_dir={str(self.results_dir)!r},\n"
            f"  port={self.port}\n"
            ")"
        )


if __name__ == "__main__":
    # Example usage
    settings = Settings()

```

### File: a11y_scanner_v1/src/scanner/main.py

<!-- This is the file 'src/scanner/main.py', a python file. -->

```python
# src/scanner/main.py
import json
import logging
import os
import sys

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.pipeline import Pipeline
from scanner.reporting.jinja_report import build_report
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

log = logging.getLogger(__name__)

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"


def _assert_docker_context() -> None:
    """Ensure we are running inside the Docker container."""
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        print(
            "\n[ERROR] This CLI is Docker-only.\n"
            "Run via the container runner instead:\n"
            "  python -m scanner.container.runner prepare\n"
            "  python -m scanner.container.runner run\n",
            file=sys.stderr,
        )
        sys.exit(2)


def main():
    """Main entry point for the scanner application using Playwright."""
    _assert_docker_context()  # hard guard: no bare-metal runs
    setup_logging(level=logging.INFO)
    log.info("--- Starting A11y Scanner with Playwright ---")

    try:
        # 1. Create all dependencies (the "composition root")
        settings = Settings()
        zip_service = ZipService(
            unzip_dir=settings.unzip_dir, scan_dir=settings.scan_dir
        )
        html_service = HtmlDiscoveryService(scan_dir=settings.scan_dir)
        http_service = HttpService()
        axe_service = PlaywrightAxeService()
        # 2. Orchestrate
        pipeline = Pipeline(
            settings=settings,
            zip_service=zip_service,
            html_service=html_service,
            http_service=http_service,
            axe_service=axe_service,
        )
        # 3. Run the pipeline
        results = pipeline.run()
        # 4. Generate consolidated HTML report
        reports_dir = settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_html = reports_dir / "latest.html"

        try:
            build_report(
                settings.results_dir, output_html, title="Accessibility Report"
            )
            log.info("Consolidated HTML report generated at: %s", output_html)
        except Exception as e:
            log.error("Failed to generate HTML report: %s", e)
            # Continue with the rest of the execution, don't fail the entire scan

        # 5. Process results
        log.info("--- Pipeline run finished ---")
        if results:
            print("\n--- Accessibility Scan Results ---")
            print(f"Found {len(results)} accessibility violations:")
            print(json.dumps(results, indent=2))
            print(f"\n✅ Full HTML report available at: {output_html.resolve()}")
        else:
            print("\n✅ No accessibility violations found!")
            print(f"Full report available at: {output_html.resolve()}")

        sys.exit(0)

    except FileNotFoundError:
        log.error("Execution failed: Could not find the input zip file.")
        sys.exit(1)
    except RuntimeError as e:
        log.error("Execution failed: %s", e)
        sys.exit(1)
    except Exception:
        log.exception("An unexpected error occurred during pipeline execution.")
        sys.exit(1)


if __name__ == "__main__":
    main()

```

### File: a11y_scanner_v1/src/scanner/pipeline.py

<!-- This is the file 'src/scanner/pipeline.py', a python file. -->

```python
# src/scanner/pipeline.py
from __future__ import annotations

import logging
from typing import Any

from scanner.core.settings import Settings
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

log = logging.getLogger(__name__)

__all__ = ["Pipeline"]


class Pipeline:
    """
    Orchestrates the scanning workflow using the native Python Playwright library.
    """

    def __init__(
        self,
        settings: Settings,
        zip_service: ZipService,
        html_service: HtmlDiscoveryService,
        http_service: HttpService,
        axe_service: PlaywrightAxeService,
    ):
        self.settings = settings
        self.zip_service = zip_service
        self.html_service = html_service
        self.http_service = http_service
        self.axe_service = axe_service

    def run(self) -> list[dict[str, Any]]:
        """
        Orchestrates the full scanning pipeline:
        1. Unzip the source archive
        2. Discover HTML files
        3. Start a local web server
        4. Scan each HTML file with Playwright + axe-core
        5. Stop the web server
        6. Return consolidated results
        """
        log.info("Starting pipeline execution...")
        all_results = []

        try:
            # Step 1: Unzip
            self.zip_service.run()

            # Step 2: Discover HTML files
            html_files = self.html_service.discover_html_files()
            if not html_files:
                log.warning(
                    "No HTML files found in the extracted content. Nothing to scan."
                )
                return []

            # Step 3: Start the server
            self.http_service.start(directory=self.settings.scan_dir)

            # Step 4: Scan each file
            for file_info in html_files:
                relative_path = file_info["relative"]
                url_to_scan = f"{self.http_service.base_url}/{relative_path}"

                # Define a unique path for the full report artifact
                report_filename = f"{relative_path.as_posix().replace('/', '_')}.json"
                report_path = self.settings.results_dir / report_filename

                try:
                    # The new service directly returns the violations
                    violations = self.axe_service.scan_url(url_to_scan, report_path)
                    if violations:
                        # Add context to each violation for better reporting
                        for violation in violations:
                            violation["scanned_url"] = url_to_scan
                            violation["source_file"] = str(relative_path)
                        all_results.extend(violations)
                except RuntimeError as e:
                    log.error("Failed to scan %s: %s", url_to_scan, e)
                    continue  # Continue to the next file

            log.info("Pipeline execution completed successfully.")
            return all_results

        except FileNotFoundError as e:
            log.error("Pipeline failed: input zip file not found. %s", e)
            raise
        except Exception:
            log.exception("Pipeline failed due to an unexpected error.")
            raise
        finally:
            # Step 5: Always ensure the server is stopped
            log.info("Pipeline finished. Shutting down HTTP server.")
            self.http_service.stop()

```

### File: a11y_scanner_v1/src/scanner/reporting/__init__.py

<!-- This is the file 'src/scanner/reporting/__init__.py', a python file. -->

```python
"""Reporting module for a11y_scanner.

This module provides functionality to generate HTML reports from accessibility
scan results. The reports are generated using Jinja2 templates and include:
- Summary statistics
- Grouped violations by rule
- Screenshots of violations
- Links to raw JSON data

Main function:
- build_report: Generate HTML report from JSON scan results
"""

from .jinja_report import ReportModel, build_report, validate_report_json

__all__ = ["build_report", "validate_report_json", "ReportModel"]

```

### File: a11y_scanner_v1/src/scanner/reporting/jinja_report.py

<!-- This is the file 'src/scanner/reporting/jinja_report.py', a python file. -->

```python
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import (ChoiceLoader, Environment, FileSystemLoader, PackageLoader,
                    TemplateNotFound, select_autoescape)

logger = logging.getLogger(__name__)


@dataclass
class Occurrence:
    url: str

    source_file: str | None

    selector: str | None

    html_snippet: str | None

    screenshot_path: str | Path | None

    screenshot_filename: str | None = None

    def __post_init__(self):
        """Extract filename from screenshot_path for template use"""

        if self.screenshot_path:
            try:
                self.screenshot_filename = Path(self.screenshot_path).name

            except Exception:
                self.screenshot_filename = str(self.screenshot_path)


@dataclass
class RuleGroup:
    id: str

    impact: str | None = None

    description: str | None = None

    help: str | None = None

    helpUrl: str | None = None

    count: int = 0

    occurrences: List[Occurrence] = field(default_factory=list)

    @property
    def impact_class(self) -> str:
        """Return CSS class based on impact level"""

        if not self.impact:
            return "impact-unknown"

        return f"impact-{self.impact.lower()}"


@dataclass
class ReportModel:
    title: str

    generated_at: str

    pages_scanned: int

    total_violations: int

    by_rule: List[RuleGroup]

    raw_files: List[str]

    def validate(self) -> bool:
        """Validate the report model has reasonable values"""

        if self.pages_scanned < 0:
            return False

        if self.total_violations < 0:
            return False

        if len(self.by_rule) > 0 and self.total_violations == 0:
            return False

        return True


def _iter_reports(results_dir: Path):
    """Generator that yields filename and parsed JSON for each report file"""

    if not results_dir.exists():
        logger.warning("Results directory does not exist: %s", results_dir)

        return

    for p in sorted(results_dir.glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)

                yield p.name, data

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", p, e)

            continue

        except Exception as e:
            logger.error("Error reading %s: %s", p, e)

            continue


def _impact_sort_key(impact: Optional[str], rule_id: str) -> tuple:
    """Sort key for rule groups: critical > serious > moderate > minor > unknown"""

    impact_order = {
        "critical": 0,
        "serious": 1,
        "moderate": 2,
        "minor": 3,
        "unknown": 4,
        None: 5,
    }

    return (impact_order.get(impact.lower() if impact else None, 5), rule_id)


def _build_model(results_dir: Path, title: str) -> ReportModel:
    """Build the report model from JSON files in the results directory"""

    groups: Dict[str, RuleGroup] = {}

    pages_scanned = 0

    total_violations = 0

    raw_files: List[str] = []

    for fname, report in _iter_reports(results_dir):
        raw_files.append(fname)

        pages_scanned += 1

        violations = (report or {}).get("violations", [])

        for v in violations:
            total_violations += 1

            rid = v.get("id") or "unknown"

            # Create or get existing rule group

            if rid not in groups:
                groups[rid] = RuleGroup(
                    id=rid,
                    impact=v.get("impact"),
                    description=v.get("description"),
                    help=v.get("help"),
                    helpUrl=v.get("helpUrl"),
                )

            grp = groups[rid]

            # Extract violation details

            selector = None

            html_snippet = None

            nodes = v.get("nodes") or []

            if nodes:
                n0 = nodes[0]

                target = n0.get("target") or []

                selector = target[0] if len(target) > 0 else None

                html_snippet = n0.get("html")

            # Get source_file from report if available

            source_file = None

            if "source_file" in report:
                source_file = report["source_file"]

            elif "scanned_url" in report and "file://" in str(report["scanned_url"]):
                # Try to extract filename from file:// URL

                try:
                    url_parts = str(report["scanned_url"]).split("file://")[-1]

                    source_file = Path(url_parts).name

                except Exception:
                    source_file = None

            # Create occurrence with screenshot handling

            screenshot_path = v.get("screenshot_path")

            occ = Occurrence(
                url=report.get("scanned_url") or report.get("url") or "",
                source_file=source_file,
                selector=selector,
                html_snippet=html_snippet,
                screenshot_path=screenshot_path,
            )

            grp.count += 1

            grp.occurrences.append(occ)

    # Sort rule groups by impact (critical first) then by ID

    sorted_groups = sorted(
        groups.values(), key=lambda g: _impact_sort_key(g.impact, g.id)
    )

    model = ReportModel(
        title=title,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ"),
        pages_scanned=pages_scanned,
        total_violations=total_violations,
        by_rule=sorted_groups,
        raw_files=raw_files,
    )

    return model


def _get_jinja_env() -> Environment:
    """

    Create a Jinja environment that works both when installed as a package

    and when running from a source checkout.

    """

    # Source-tree templates path: scanner/templates

    src_templates_dir = Path(__file__).resolve().parent.parent / "templates"

    loader = ChoiceLoader(
        [
            # Prefer installed package resources (editable or built installs)
            PackageLoader("scanner", "templates"),
            # Fallback to filesystem loader in a source tree
            FileSystemLoader(str(src_templates_dir)),
        ]
    )

    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    return env


def build_report(
    results_dir: Path,
    output_html: Path,
    title: str = "Accessibility Report",
    overwrite: bool = True,
) -> Path:
    """Aggregate JSON artifacts in ``results_dir`` and render a single HTML report.


    Args:

        results_dir: Directory containing JSON scan results

        output_html: Path where HTML report will be saved

        title: Title for the report

        overwrite: Whether to overwrite existing report (default: True)


    Returns:

        Path to the generated HTML report


    Raises:

        FileNotFoundError: If template cannot be found

        PermissionError: If cannot write to output path

        RuntimeError: If report generation fails

    """

    if not overwrite and output_html.exists():
        logger.info(
            "Report already exists and overwrite=False, skipping: %s", output_html
        )

        return output_html

    results_dir = results_dir.resolve()

    output_html.parent.mkdir(parents=True, exist_ok=True)

    try:
        model = _build_model(results_dir, title)

        # Validate model

        if not model.validate():
            logger.warning("Generated report model failed validation")

        # Set up Jinja2 environment

        env = _get_jinja_env()

        # Load template

        try:
            tpl = env.get_template("a11y_report.html.j2")

        except TemplateNotFound as e:
            raise FileNotFoundError(f"Template not found: {e}") from e

        # Render template
        # Compute a relative web path from the report file location to the results directory
        # so screenshots work when opening the report directly from the filesystem
        # (e.g., file:///.../data/reports/latest.html -> ../results/*).
        base_dir = output_html.parent.resolve()
        rel = os.path.relpath(results_dir, base_dir)
        # Normalize to POSIX-style separators for browsers
        results_web_base = rel.replace(os.sep, "/")

        html = tpl.render(model=model, results_web_base=results_web_base)

        # Write to file

        try:
            output_html.write_text(html, encoding="utf-8")

            logger.info("HTML report generated: %s", output_html)

        except PermissionError as e:
            raise PermissionError(f"Cannot write to {output_html}: {e}") from e

        except Exception as e:
            raise RuntimeError(f"Failed to write report: {e}") from e

        return output_html

    except Exception as e:
        logger.error("Failed to build report: %s", e)

        raise RuntimeError(f"Report generation failed: {e}") from e


def validate_report_json(json_path: Path) -> bool:
    """Validate that a JSON file has the expected structure for reporting"""

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Check for required fields

        if not isinstance(data, dict):
            return False

        # Should have either violations array or be empty

        if "violations" in data and not isinstance(data["violations"], list):
            return False

        # Should have URL info

        if "scanned_url" not in data and "url" not in data:
            return False

        return True

    except Exception:
        return False


if __name__ == "__main__":
    # Manual debug: build a report from ./data/results into ./data/reports/latest.html

    logging.basicConfig(level=logging.INFO)

    base = Path(".")

    results_dir = base / "data" / "results"

    out = base / "data" / "reports" / "latest.html"

    if not results_dir.exists() or not any(results_dir.glob("*.json")):
        print(f"Warning: No JSON files found in {results_dir}")

    try:
        result_path = build_report(results_dir, out)

        print(f"✅ Report successfully generated: {result_path}")

    except Exception as e:
        print(f"❌ Report generation failed: {e}")

        sys.exit(1)

```

### File: a11y_scanner_v1/src/scanner/services/html_discovery_service.py

<!-- Auto-extracted from leading comments/docstrings -->
> src/scanner/services/html_discovery_service.py

<!-- This is the file 'src/scanner/services/html_discovery_service.py', a python file. -->

```python
# src/scanner/services/html_discovery_service.py
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HtmlDiscoveryService:
    """Service that discovers HTML files under a given directory."""

    def __init__(self, scan_dir: Path):
        if not isinstance(scan_dir, Path):
            raise TypeError("scan_dir must be a Path object")
        self.scan_dir = scan_dir
        logger.debug(
            "HtmlDiscoveryService initialized with scan_dir: %s",
            self.scan_dir,
        )

    def discover_html_files(self) -> list[dict[str, Path]]:
        """Recursively discover all HTML files relative to scan_dir."""
        logger.info(
            "Recursively discovering HTML files in: %s",
            self.scan_dir,
        )
        if not self.scan_dir.is_dir():
            logger.error(
                "Scan directory does not exist or is not a directory: %s",
                self.scan_dir,
            )
            return []

        html_paths: list[dict[str, Path]] = []
        for pattern in ("*.html", "*.htm"):
            for abs_path in self.scan_dir.rglob(pattern):
                if not abs_path.is_file():
                    continue

                try:
                    relative_path = abs_path.relative_to(self.scan_dir)
                    entry = {
                        "absolute": abs_path.resolve(),
                        "relative": relative_path,
                    }
                    html_paths.append(entry)
                    logger.debug(
                        "Found HTML: Rel=%s,\nAbs=%s",
                        relative_path,
                        abs_path.resolve(),
                    )
                except ValueError:
                    logger.warning(
                        "Could not determine relative path\nfor %s against base %s. "
                        "Skipping.",
                        abs_path,
                        self.scan_dir,
                    )

        count = len(html_paths)
        logger.info(
            "Found %d HTML file(s) in %s",
            count,
            self.scan_dir,
        )

        if count:
            sample_limit = 5
            sample = [str(e["relative"]) for e in html_paths[:sample_limit]]
            logger.debug("Sample relative paths: %s", sample)

            if count > sample_limit:
                logger.debug(
                    "... and %d more.",
                    count - sample_limit,
                )

        return html_paths

```

### File: a11y_scanner_v1/src/scanner/services/http_service.py

<!-- Auto-extracted from leading comments/docstrings -->
> src/scanner/services/http_service.py

<!-- This is the file 'src/scanner/services/http_service.py', a python file. -->

```python
# src/scanner/services/http_service.py
import http.server
import logging
import socket
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class Handler(http.server.SimpleHTTPRequestHandler):
    """A request handler that serves files from a specific directory."""

    def __init__(self, *args, directory: Path, **kwargs) -> None:
        # The directory argument is mandatory for our use case
        super().__init__(*args, directory=str(directory), **kwargs)


class HttpService:
    """A service to manage a simple, local HTTP server in a background thread."""

    def __init__(self):
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.host = "localhost"
        self.port = 0  # Port 0 means the OS will pick an available port
        self.base_url = ""

    def start(self, directory: Path):
        """Starts the HTTP server in a background thread."""
        if self._server:
            logger.warning("Server is already running. Ignoring start request.")
            return

        # Use a context manager to find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            self.port = s.getsockname()[1]  # Get the port assigned by the OS
            logger.info("Found available port: %d", self.port)

        self.base_url = f"http://{self.host}:{self.port}"

        # The handler needs the directory to serve from. functools.partial is
        # a clean way to pass the 'directory' argument to the Handler's constructor.
        def handler_factory(*args, **kwargs):
            return Handler(*args, directory=directory, **kwargs)

        self._server = http.server.ThreadingHTTPServer(
            (self.host, self.port), handler_factory
        )

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(
            "HTTP server started at %s, serving files from %s",
            self.base_url,
            directory,
        )

    def stop(self):
        """Stops the HTTP server and waits for the thread to join."""
        if self._server and self._thread:
            logger.info("Shutting down HTTP server...")
            self._server.shutdown()
            self._thread.join(timeout=5)  # Wait for the thread to finish
            if self._thread.is_alive():
                logger.error("Server thread did not shut down cleanly.")
            self._server.server_close()
            logger.info("HTTP server shut down.")
        self._server = None
        self._thread = None
        self.base_url = ""

```

### File: a11y_scanner_v1/src/scanner/services/playwright_axe_service.py

<!-- Auto-extracted from leading comments/docstrings -->
> src/scanner/services/playwright_axe_service.py

<!-- This is the file 'src/scanner/services/playwright_axe_service.py', a python file. -->

```python
# src/scanner/services/playwright_axe_service.py
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, sync_playwright

logger = logging.getLogger(__name__)


class PlaywrightAxeService:
    """
    Run accessibility scans using the native `axe-playwright-python` library.

    This approach is self-contained within Python and does not require
    Node.js subprocesses.
    """

    def _capture_violation_screenshot(
        self, page: Page, violation: dict[str, Any], results_dir: Path
    ) -> str | None:
        """Highlight the first node for a violation and take a screenshot."""
        node = violation["nodes"][0]
        selector = node["target"][0]  # CSS selector for the element

        try:
            highlight_style = "{ border: 5px solid red !important; }"
            page.add_style_tag(content=f"{selector} {highlight_style}")

            screenshot_filename = f"violation-{violation['id']}-{uuid.uuid4()}.png"
            screenshot_path = results_dir / screenshot_filename

            page.screenshot(path=str(screenshot_path))
            logger.info(
                "Captured screenshot for violation '%s' at %s",
                violation["id"],
                screenshot_path,
            )
            return str(screenshot_path)

        except Exception as e:
            logger.error(
                "Failed to capture screenshot for selector '%s': %s", selector, e
            )
            return None

    def scan_url(self, url: str, output_path: Path) -> list[dict[str, Any]]:
        """
        Scan a URL for accessibility issues, take screenshots of violations,
        and save the report.
        """
        logger.info("Scanning %s with axe-playwright-python", url)
        axe = Axe()
        results_dir = output_path.parent
        # Ensure the results directory exists before attempting screenshots
        # so that page.screenshot() does not fail on first run.
        results_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="networkidle")
                results = axe.run(page)

                violations = results.response.get("violations", [])

                if violations:
                    logger.warning(
                        "Found %d accessibility violations at %s",
                        len(violations),
                        url,
                    )
                    for violation in violations:
                        screenshot_path = self._capture_violation_screenshot(
                            page, violation, results_dir
                        )
                        violation["screenshot_path"] = screenshot_path
                else:
                    logger.info("No accessibility violations found at %s", url)

                # Save the full, augmented report for debugging and artifacts.
                # Important: add 'scanned_url' so integr. tests can sort like before.
                full_report = dict(results.response)
                full_report["scanned_url"] = url

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(full_report, f, indent=2)
                logger.info("Full scan report saved to %s", output_path)

            finally:
                browser.close()

        return violations

```

### File: a11y_scanner_v1/src/scanner/services/zip_service.py

<!-- This is the file 'src/scanner/services/zip_service.py', a python file. -->

```python
import logging
import sys
from pathlib import Path
from zipfile import ZipFile

logger = logging.getLogger(__name__)


class ZipService:
    """Service to detect a single .zip in a directory and extract it."""

    def __init__(self, *, unzip_dir: Path, scan_dir: Path):
        """
        Args:
            unzip_dir: Directory to search for zip files.
            scan_dir: Directory where zip contents will be extracted.
        """
        self.unzip_dir = unzip_dir
        self.scan_dir = scan_dir

    def detect_zip(self) -> Path:
        """Search unzip_dir for a .zip file and return its Path."""
        logger.info("Checking %s for any valid zip files", self.unzip_dir)
        zips = list(self.unzip_dir.glob("*.zip"))
        logger.info("Found the following zip(s): %s", zips)

        if not zips:
            raise FileNotFoundError(f"No zip files found in {self.unzip_dir}")

        zip_path = zips[0]
        logger.info("Zip file detected: %s", zip_path)
        return zip_path

    def unzip(self, zip_path: Path, destination: Path) -> None:
        """Extract zip_path into the destination directory."""
        logger.info("Attempting extraction of %s to %s", zip_path, destination)
        try:
            with ZipFile(zip_path, "r") as archive:
                file_list = archive.namelist()
                logger.debug(
                    "Zip contains %d files/directories",
                    len(file_list),
                )

                archive.extractall(destination)
                logger.info("Extraction completed successfully")

                dirs = [n for n in file_list if n.endswith("/")]
                if dirs:
                    logger.info(
                        "Zip contains %d directories: %s",
                        len(dirs),
                        dirs[:5],
                    )
        except OSError as error:
            raise RuntimeError(f"Failed to extract {zip_path}") from error

    def run(self) -> None:
        """Detect a zip, unzip it, and log the extracted items."""
        try:
            zip_path = self.detect_zip()
            self.unzip(zip_path, self.scan_dir)

            extracted_items = list(self.scan_dir.glob("**/*"))
            logger.info(
                "Extracted %d items to %s",
                len(extracted_items),
                self.scan_dir,
            )

            for extracted in extracted_items[:10]:
                logger.info("Extracted item: %s", extracted)

            if not any(self.scan_dir.iterdir()):
                raise RuntimeError("Extraction resulted in empty directory")
        except FileNotFoundError as fnf:
            logger.error("No zip found: %s", fnf)
            raise
        except Exception as error:
            logger.error("Zip extraction failed: %s", error)
            raise


if __name__ == "__main__":
    # Standalone invocation for testing/development
    from scanner.core.logging_setup import setup_logging
    from scanner.core.settings import Settings

    setup_logging()
    settings = Settings()

    logger.info("Running ZipService in standalone mode")
    logger.info("Settings: %s", settings)

    service = ZipService(
        unzip_dir=settings.unzip_dir,
        scan_dir=settings.scan_dir,
    )

    try:
        service.run()
        for path in settings.scan_dir.iterdir():
            logger.info("Extracted: %s", path)
        sys.exit(0)
    except Exception as error:
        logger.error("ZipService failed: %s", error)
        sys.exit(1)

```

### File: a11y_scanner_v1/src/scanner/templates/__init__.py

```python
# Empty file
```

### File: a11y_scanner_v1/src/scanner/web/server.py

<!-- This is the file 'src/scanner/web/server.py', a python file. -->

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scanner.core.logging_setup import setup_logging
from scanner.core.settings import Settings
from scanner.pipeline import Pipeline
from scanner.reporting.jinja_report import ReportModel, build_report
from scanner.services.html_discovery_service import HtmlDiscoveryService
from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService
from scanner.services.zip_service import ZipService

IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"

app = FastAPI(title="a11y-scanner API", version="0.1.0")
setup_logging()
settings = Settings()

# Ensure data folders exist
for d in (
    settings.data_dir,
    settings.unzip_dir,
    settings.results_dir,
    settings.scan_dir,
):
    d.mkdir(parents=True, exist_ok=True)

reports_dir = settings.data_dir / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)

# Serve static artifacts
app.mount("/results", StaticFiles(directory=settings.results_dir), name="results")
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")


class UrlsIn(BaseModel):
    urls: List[str]


def _require_container():
    if os.environ.get(IN_CONTAINER_ENV) != IN_CONTAINER_VALUE:
        raise HTTPException(status_code=400, detail="Must run inside container")


def _clean_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    for child in p.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink(missing_ok=True)  # py310+
            except Exception:
                pass


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <h1>a11y‑scanner API</h1>
    <ul>
      <li>POST <code>/api/scan/zip</code> with form field <code>file</code> (.zip of a static site)</li>
      <li>POST <code>/api/scan/url</code> with JSON like <code>{"urls":["https://example.com/"]}</code></li>
    </ul>
    <p>Artifacts: <a href="/reports" target="_blank">/reports</a> and <a href="/results" target="_blank">/results</a>.</p>
    <p>For report format documentation, see: <a href="https://github.com/dequelabs/axe-core" target="_blank">axe-core documentation</a></p>
    """


@app.post("/api/scan/zip")
async def scan_zip(file: UploadFile = File(...)):
    _require_container()
    # Reset previous run artifacts
    _clean_dir(settings.scan_dir)
    _clean_dir(settings.results_dir)
    # Save uploaded zip as data/unzip/site.zip
    target = settings.unzip_dir / "site.zip"
    content = await file.read()
    target.write_bytes(content)
    # Run pipeline (unzip -> index -> serve -> run playwright -> write reports)
    zip_service = ZipService(unzip_dir=settings.unzip_dir, scan_dir=settings.scan_dir)
    html_service = HtmlDiscoveryService(scan_dir=settings.scan_dir)
    http_service = HttpService()
    axe_service = PlaywrightAxeService()
    pipeline = Pipeline(
        settings=settings,
        zip_service=zip_service,
        html_service=html_service,
        http_service=http_service,
        axe_service=axe_service,
    )
    violations = pipeline.run()
    # Build consolidated HTML report
    output_html = reports_dir / "latest.html"
    try:
        build_report(
            settings.results_dir, output_html, title="Accessibility Report (ZIP)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )

    return JSONResponse(
        {
            "violations": len(violations),
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
        }
    )


@app.post("/api/scan/url")
async def scan_url(payload: UrlsIn):
    _require_container()
    # Reset previous run artifacts
    _clean_dir(settings.results_dir)
    axe = PlaywrightAxeService()
    count = 0
    for url in payload.urls:
        safe_name = (
            url.replace("https://", "")
            .replace("http://", "")
            .replace("/", "_")
            .replace("?", "_")
        )
        report_path = settings.results_dir / f"{safe_name}.json"
        v = axe.scan_url(url, report_path)
        count += len(v)
    output_html = reports_dir / "latest.html"
    try:
        build_report(
            settings.results_dir, output_html, title="Accessibility Report (Live URLs)"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )

    return JSONResponse(
        {
            "violations": count,
            "report_url": "/reports/latest.html",
            "results_url": "/results/",
            "status": "success",
        }
    )


def run():
    import uvicorn

    # Uvicorn listens on 8008 (published by the container runner)
    uvicorn.run(app, host="0.0.0.0", port=8008)


if __name__ == "__main__":
    run()

```

### File: a11y_scanner_v1/tests/services/test_playwright_axe_service.py

<!-- This is the file 'tests/services/test_playwright_axe_service.py', a python file. -->

```python
import tempfile
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

from scanner.services.http_service import HttpService
from scanner.services.playwright_axe_service import PlaywrightAxeService


@pytest.fixture
def http_service():
    """Fixture to create and automatically clean up an HttpService instance."""
    service = HttpService()
    yield service
    service.stop()


def test_scan_url_captures_screenshot_of_violation(
    http_service: HttpService, tmp_path: Path
):
    """
    Verify that when a violation is found, a screenshot is taken,
    and the path to it is added to the violation dictionary.
    """
    # 1. SETUP
    scan_dir = tmp_path / "scan"
    results_dir = tmp_path / "results"
    scan_dir.mkdir()
    results_dir.mkdir()

    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Test Page</title></head>
    <body>
        <main>
            <h1>Missing Alt Text</h1>
            <img src="test.jpg">
        </main>
    </body>
    </html>
    """
    test_html_file = scan_dir / "index.html"
    test_html_file.write_text(html_content)

    http_service.start(directory=scan_dir)
    url_to_scan = f"{http_service.base_url}/index.html"
    report_path = results_dir / "report.json"

    # 2. ACTION
    service = PlaywrightAxeService()
    violations = service.scan_url(url_to_scan, report_path)

    # 3. VERIFICATION
    # Find the specific violation we are interested in.
    image_alt_violation = next((v for v in violations if v["id"] == "image-alt"), None)
    assert image_alt_violation is not None, "The 'image-alt' violation was not found."

    # **THE KEY CHECK**: Assert that a screenshot path has been added
    assert "screenshot_path" in image_alt_violation
    screenshot_path_str = image_alt_violation["screenshot_path"]
    assert screenshot_path_str is not None

    # Assert that the screenshot file actually exists
    screenshot_path = Path(screenshot_path_str)
    assert screenshot_path.exists()
    assert screenshot_path.is_file()

    # Assert the screenshot is saved in the correct directory
    assert results_dir in screenshot_path.parents

```

### File: a11y_scanner_v1/tests/test_html_discovery_service.py

<!-- This is the file 'tests/test_html_discovery_service.py', a python file. -->

```python
from pathlib import Path

import pytest

from scanner.services.html_discovery_service import HtmlDiscoveryService


@pytest.mark.parametrize(
    "test_dir, expected_rel_paths",
    [
        ("1", {"index.html", "about.html"}),
        (
            "2",
            {
                "hehe.htm",
                "lol.html",
                "test.html",
                "nest/ll.html",
                "nest/ll.htm",
                "nest/tl.htm",
            },
        ),
        ("3", {"mor_test.html", "test.html"}),
    ],
)
def test_discover_html_files_absolute_and_relative(test_dir, expected_rel_paths):
    base_dir = Path(__file__).parent / "assets" / "html_sets" / test_dir
    assert base_dir.exists(), f"Test directory does not exist: {base_dir}"

    service = HtmlDiscoveryService(scan_dir=base_dir)
    discovered = service.discover_html_files()

    found_rel = {str(entry["relative"]) for entry in discovered}
    assert found_rel == expected_rel_paths, f"Relative paths mismatch in {test_dir}"

    for entry in discovered:
        rel = entry["relative"]
        abs_path = entry["absolute"]

        # Assert absolute path is correct
        expected_abs = base_dir / rel
        assert abs_path == expected_abs.resolve(), f"Absolute path mismatch for {rel}"
        assert abs_path.exists(), f"Absolute path doesn't exist: {abs_path}"
        assert abs_path.is_file(), f"Path is not a file: {abs_path}"

```

### File: a11y_scanner_v1/tests/test_http_service.py

<!-- This is the file 'tests/test_http_service.py', a python file. -->

```python
import time
from pathlib import Path

import pytest
import requests

from scanner.services.http_service import HttpService


@pytest.fixture
def http_service():
    """Fixture to create and automatically clean up an HttpService instance."""
    service = HttpService()
    yield service
    # Teardown: ensure the server is stopped after the test runs
    service.stop()


def test_http_server_serves_files(http_service: HttpService, tmp_path: Path):
    """
    Verify that the HttpService can start, serve a file, and stop.
    """
    content = "<html><body>Test Page</body></html>"
    test_file = tmp_path / "index.html"
    test_file.write_text(content)

    http_service.start(directory=tmp_path)
    assert http_service.base_url, "Server should have a base_url after starting"
    time.sleep(0.1)  # Give the server a moment to start up in the background

    url_to_test = f"{http_service.base_url}/index.html"

    try:
        response = requests.get(url_to_test, timeout=5)
        response.raise_for_status()

        assert response.text == content
        assert response.headers["Content-Type"] == "text/html"

    except requests.RequestException as e:
        pytest.fail(f"HTTP request failed: {e}")

    http_service.stop()

    with pytest.raises(requests.ConnectionError):
        requests.get(url_to_test, timeout=1)

```

### File: a11y_scanner_v1/tests/test_pipeline.py

<!-- This is the file 'tests/test_pipeline.py', a python file. -->

```python
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scanner.core.settings import Settings
from scanner.pipeline import Pipeline


def create_test_zip(zip_path: Path, files: dict[str, str]):
    """Helper to create a zip file for testing."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_name, content in files.items():
            zf.writestr(file_name, content)


@pytest.fixture
def mock_services() -> dict:
    """Provides a dictionary of mocked services for injection."""
    return {
        "zip_service": MagicMock(),
        "html_service": MagicMock(),
        "http_service": MagicMock(),
        "axe_service": MagicMock(),
    }


def test_pipeline_happy_path(tmp_path: Path, mock_services: dict):
    """
    Tests the full pipeline orchestration on a happy path using mocked services.
    """
    # 1. Setup
    # Configure the return values of our mocks
    mock_services["html_service"].discover_html_files.return_value = [
        {"relative": Path("index.html")}
    ]
    mock_services["http_service"].base_url = "http://localhost:8000"

    # --- THE FIX IS HERE ---
    # We now mock the return value of `scan_url` because that's what the pipeline
    # uses to get the results directly.
    mock_violations = [{"id": "image-alt", "impact": "critical"}]
    mock_services["axe_service"].scan_url.return_value = mock_violations

    # Create fake directory structure
    settings = Settings(root_path=tmp_path)
    settings.scan_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)

    # 2. Action
    # Instantiate the pipeline with our temporary settings and MOCKED services
    pipeline = Pipeline(settings=settings, **mock_services)
    final_results = pipeline.run()

    # 3. Verification
    # Verify that the services were called as expected
    mock_services["zip_service"].run.assert_called_once()
    mock_services["html_service"].discover_html_files.assert_called_once()
    mock_services["http_service"].start.assert_called_once_with(
        directory=settings.scan_dir
    )

    # Verify AxeService.scan_url was called correctly
    mock_services["axe_service"].scan_url.assert_called_once()
    call_args, _ = mock_services["axe_service"].scan_url.call_args
    scanned_url = call_args[0]
    report_path = call_args[1]
    assert scanned_url == "http://localhost:8000/index.html"
    assert report_path == settings.results_dir / "index.html.json"

    # Verify the final result is what the mocked scan_url returned,
    # but with the added context from the pipeline.
    expected_result = [
        {
            "id": "image-alt",
            "impact": "critical",
            "scanned_url": "http://localhost:8000/index.html",
            "source_file": "index.html",
        }
    ]
    assert final_results == expected_result

    # Verify the HTTP server was stopped
    mock_services["http_service"].stop.assert_called_once()


def test_pipeline_no_html_files_found(tmp_path: Path, mock_services: dict):
    """
    Verify the pipeline exits gracefully if no HTML files are discovered.
    """
    # 1. Setup
    mock_services["html_service"].discover_html_files.return_value = []
    settings = Settings(root_path=tmp_path)

    # 2. Action
    pipeline = Pipeline(settings=settings, **mock_services)
    result = pipeline.run()

    # 3. Verification
    assert result == []
    mock_services["zip_service"].run.assert_called_once()
    mock_services["http_service"].start.assert_not_called()
    mock_services["axe_service"].scan_url.assert_not_called()
    mock_services[
        "http_service"
    ].stop.assert_called_once()  # Should still be called in finally

```

### File: a11y_scanner_v1/tests/test_reporting.py

<!-- This is the file 'tests/test_reporting.py', a python file. -->

```python
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scanner.reporting.jinja_report import (Occurrence, ReportModel, RuleGroup,
                                            build_report, validate_report_json)


@pytest.fixture
def sample_report_data():
    """Sample report data for testing"""

    return {
        "scanned_url": "http://localhost:8000/index.html",
        "source_file": "index.html",
        "violations": [
            {
                "id": "image-alt",
                "impact": "critical",
                "description": "Images must have alternate text",
                "help": "Provide appropriate alt text for images",
                "helpUrl": "https://example.com/help",
                "nodes": [
                    {"target": ["img[src='logo.png']"], "html": "<img src='logo.png'>"}
                ],
                "screenshot_path": "screenshot1.png",
            }
        ],
    }


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        results_dir = temp_path / "results"

        reports_dir = temp_path / "reports"

        results_dir.mkdir()

        reports_dir.mkdir()

        yield results_dir, reports_dir


def test_occurrence_post_init():
    """Test that Occurrence.__post_init__ correctly extracts filename"""

    # Test with string path

    occ = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path="/path/to/screenshot.png",
    )

    assert occ.screenshot_filename == "screenshot.png"

    # Test with None

    occ2 = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path=None,
    )

    assert occ2.screenshot_filename is None

    # Test with Path object

    occ3 = Occurrence(
        url="http://example.com",
        source_file="index.html",
        selector="img",
        html_snippet="<img>",
        screenshot_path=Path("/path/to/another.png"),
    )

    assert occ3.screenshot_filename == "another.png"


def test_rule_group_impact_class():
    """Test RuleGroup.impact_class property"""

    # Test with different impact levels

    assert RuleGroup(id="test", impact="critical").impact_class == "impact-critical"

    assert RuleGroup(id="test", impact="serious").impact_class == "impact-serious"

    assert RuleGroup(id="test", impact="moderate").impact_class == "impact-moderate"

    assert RuleGroup(id="test", impact="minor").impact_class == "impact-minor"

    assert RuleGroup(id="test", impact="unknown").impact_class == "impact-unknown"

    assert RuleGroup(id="test", impact=None).impact_class == "impact-unknown"


def test_report_model_validation():
    """Test ReportModel.validate() method"""

    # Valid model

    model = ReportModel(
        title="Test",
        generated_at="2023-01-01T00:00:00Z",
        pages_scanned=1,
        total_violations=1,
        by_rule=[],
        raw_files=[],
    )

    assert model.validate() is True

    # Invalid: negative pages

    model.pages_scanned = -1

    assert model.validate() is False

    # Invalid: negative violations

    model.pages_scanned = 1

    model.total_violations = -1

    assert model.validate() is False

    # Edge case: zero violations with rule groups

    model.total_violations = 0

    model.by_rule = [RuleGroup(id="test", impact="critical")]

    assert model.validate() is False  # Should be False if rules exist but 0 violations

    # Valid: zero violations with no rule groups

    model.by_rule = []

    assert model.validate() is True


def test_validate_report_json(temp_dirs, sample_report_data):
    """Test validate_report_json function"""

    results_dir, _ = temp_dirs

    # Test valid JSON

    valid_file = results_dir / "valid.json"

    with open(valid_file, "w") as f:

        json.dump(sample_report_data, f)

    assert validate_report_json(valid_file) is True

    # Test invalid JSON (not a dict)

    invalid_file = results_dir / "invalid.json"

    with open(invalid_file, "w") as f:

        f.write('["not", "a", "dict"]')

    assert validate_report_json(invalid_file) is False

    # Test missing URL info

    invalid_data = {"violations": []}  # No URL info

    invalid_file2 = results_dir / "invalid2.json"

    with open(invalid_file2, "w") as f:

        json.dump(invalid_data, f)

    assert validate_report_json(invalid_file2) is False


def test_build_report_success(temp_dirs, sample_report_data):
    """Test successful report generation"""

    results_dir, reports_dir = temp_dirs

    # Create sample report file

    report_file = results_dir / "sample.json"

    with open(report_file, "w") as f:

        json.dump(sample_report_data, f)

    # Generate report

    output_file = reports_dir / "report.html"

    result = build_report(results_dir, output_file, title="Test Report")

    # Verify result

    assert result == output_file

    assert output_file.exists()

    assert output_file.stat().st_size > 0

    # Check content

    content = output_file.read_text()

    assert "Test Report" in content

    assert "image-alt" in content

    assert "Pages Scanned" in content

    assert "Total Violations" in content


def test_build_report_no_results_dir(temp_dirs):
    """Test build_report with non-existent results directory"""

    _, reports_dir = temp_dirs

    non_existent_dir = Path("/non/existent/directory")

    output_file = reports_dir / "report.html"

    # Should not raise an error, but generate an empty report

    result = build_report(non_existent_dir, output_file)

    assert result == output_file

    assert output_file.exists()


def test_build_report_no_json_files(temp_dirs):
    """Test build_report with no JSON files in results directory"""

    results_dir, reports_dir = temp_dirs

    output_file = reports_dir / "report.html"

    # Generate report with empty results directory

    result = build_report(results_dir, output_file, title="Empty Report")

    assert result == output_file

    assert output_file.exists()

    # Check that it's a valid HTML file with "No accessibility violations"

    content = output_file.read_text()

    assert "Empty Report" in content

    assert "No accessibility violations" in content

```

### File: a11y_scanner_v1/tests/test_settings.py

<!-- This is the file 'tests/test_settings.py', a python file. -->

```python
from pathlib import Path

import pytest

from scanner.core.settings import Settings


def test_settings_default_uses_relative_paths():
    """
    Verify that by default, Settings uses relative paths from the current directory.
    This is important for portability and interaction with CLI tools.
    """
    settings = Settings()

    # The base path should be a relative representation of the current directory.
    assert settings.base_path == Path(".")

    # All other paths should be built relative to that.
    assert settings.data_dir == Path("data")
    assert settings.scan_dir == Path("data/scan")
    assert settings.unzip_dir == Path("data/unzip")
    assert settings.results_dir == Path("data/results")
    assert settings.port == 8000


def test_settings_with_custom_base_path_uses_absolute_path(tmp_path: Path):
    """
    Verify that when a root_path is provided (common in tests), it is
    resolved to an absolute path.
    """
    settings = Settings(root_path=tmp_path)

    assert settings.base_path == tmp_path.resolve()
    assert settings.data_dir == tmp_path.resolve() / "data"
    assert settings.scan_dir == tmp_path.resolve() / "data" / "scan"
    assert settings.unzip_dir == tmp_path.resolve() / "data" / "unzip"
    assert settings.results_dir == tmp_path.resolve() / "data" / "results"

```

### File: a11y_scanner_v1/tests/test_zip_service.py

<!-- This is the file 'tests/test_zip_service.py', a python file. -->

```python
import zipfile
from pathlib import Path

import pytest

from scanner.services.zip_service import ZipService


def create_test_zip(zip_path: Path, files: dict[str, str]):
    """
    Creates a zip file at `zip_path` with a dictionary of filename -> contents.
    """
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file_name, content in files.items():
            zf.writestr(file_name, content)


def test_zip_extraction(tmp_path: Path):
    # Setup: directories for unzip input and scan output
    unzip_dir = tmp_path / "unzip"
    scan_dir = tmp_path / "scan"
    unzip_dir.mkdir()
    scan_dir.mkdir()

    # Create a zip file in the unzip_dir
    zip_file = unzip_dir / "test.zip"
    create_test_zip(
        zip_file,
        {
            "index.html": "<html><body>Hello</body></html>",
            "about.html": "<html><body>About</body></html>",
        },
    )

    # Run ZipService
    service = ZipService(unzip_dir=unzip_dir, scan_dir=scan_dir)
    service.run()

    # Assert: files are extracted into scan_dir
    extracted_files = list(scan_dir.glob("*.html"))
    extracted_names = {f.name for f in extracted_files}

    assert "index.html" in extracted_names
    assert "about.html" in extracted_names
    assert len(extracted_files) == 2


def test_missing_zip_file(tmp_path: Path):
    unzip_dir = tmp_path / "unzip"
    scan_dir = tmp_path / "scan"
    unzip_dir.mkdir()
    scan_dir.mkdir()

    service = ZipService(unzip_dir=unzip_dir, scan_dir=scan_dir)

    with pytest.raises(FileNotFoundError):
        service.run()

```
