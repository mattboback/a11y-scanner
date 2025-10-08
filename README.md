# a11y-scanner

Docker-first accessibility scanner project scaffolding.

Work in progress while core pipeline, reporting, and docs are being assembled.

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
