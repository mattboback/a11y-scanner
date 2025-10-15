# a11y-scanner (Docker-only)

> Static-site Accessibility Scanner
>
> Powered by Python 3.10+, Playwright, Docker, and axe-core.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![axe-core](https://img.shields.io/badge/axe--core-Playwright-green)](https://github.com/dequelabs/axe-core)

---

## ✨ Features

- **Comprehensive Accessibility Testing** — Uses axe-core via Playwright to detect WCAG violations
- **Containerized & Reproducible** — Docker-first architecture with cached images for fast iteration
- **Multiple Scan Modes** — Upload ZIP archives or scan live URLs via REST API
- **Rich HTML Reports** — Consolidated reports with violation screenshots, rule grouping, and direct links to remediation guidance
- **Security Hardened** — Zip Slip protection, upload size limits, MIME type validation
- **High Performance** — Browser reuse across scans, element-level screenshots, configurable concurrency
- **Developer Friendly** — Python 3.10+, comprehensive test coverage, CI/CD ready

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

**Key Capabilities:**
- Scan static site archives (ZIP files) or live URLs
- Generate detailed JSON artifacts and element-level violation screenshots
- Produce consolidated HTML reports with filtering and grouping
- Secure by design: Zip Slip prevention, upload validation, container isolation

The container is prepared programmatically via the Docker SDK (no docker-compose required).

---

## 2 · How It Works

1. Place a `site.zip` archive under `data/unzip` or upload it via the API.
2. The scanner safely extracts the site (with Zip Slip protection) to a temp directory.
3. It starts a local HTTP server serving the extracted files.
4. It visits each `.html` page with Playwright + axe-core and audits a11y using a reusable browser for performance.
5. It captures element-level screenshots for each violation and writes full JSON reports to `data/results`.
6. It renders a consolidated HTML report under `data/reports/latest.html` with rule grouping and impact severity.

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

## 9 · Recent Improvements

**Security & Robustness:**
- ✅ **Zip Slip Protection** — Validates archive paths to prevent directory traversal attacks
- ✅ **API Hardening** — Upload size limits (100MB), MIME type validation, comprehensive error handling
- ✅ **Source File Tracking** — Persists `source_file` in JSON artifacts for better report context

**Performance & Quality:**
- ✅ **Browser Reuse** — Single Playwright browser reused across all scans (context manager pattern)
- ✅ **Element Screenshots** — Captures focused element screenshots with highlights instead of full-page
- ✅ **Comprehensive Tests** — 30+ unit tests including API endpoint coverage and security validation

## 10 · Future Roadmap

- **Concurrency** — Parallel page scanning with configurable worker pools
- **Advanced Configuration** — Include/exclude patterns, timeouts, viewport settings, headless toggle
- **CI/CD Integration** — SARIF export for GitHub Code Scanning, severity thresholds, GitHub Action template
- **Report Enhancements** — Client-side filtering by impact/rule, grouping by page, CSV export
- **Background Jobs** — Async scan queue with job ID and status polling for API
- **Demo & Showcase** — GitHub Pages with sample reports, animated demo GIFs

---

## 🤝 Contributing

Before filing a PR, read the [Contributors guide](CONTRIBUTORS.md) and the
[Development Guide](docs/development-guide.md). These cover the expected workflow
(virtualenv, linting, tests) and how to run the Docker-backed integration suite.
