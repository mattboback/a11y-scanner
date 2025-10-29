# a11y-scanner

> **Containerized Accessibility Scanner** — Automated WCAG compliance testing for static websites using Playwright, axe-core, and Docker.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![axe-core](https://img.shields.io/badge/axe--core-Playwright-green)](https://github.com/dequelabs/axe-core)
[![CI](https://github.com/yourusername/a11y-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/a11y-scanner/actions)

## Overview

**a11y-scanner** is an open-source, self-hostable system for running automated accessibility audits on static websites. It combines:

- **Playwright** — Headless browser automation for page navigation
- **axe-core** — Industry-leading accessibility rule engine via `axe-playwright-python`
- **Docker** — Reproducible, isolated execution environment with smart caching
- **Jinja2** — Rich HTML report generation with violations grouped by rule and impact
- **FastAPI** (optional) — REST API for remote scanning and on-demand reporting

Built for **CI/CD pipelines, batch operations, and self-hosted deployments** where accessibility compliance is non-negotiable.

---

## Features

✨ **Comprehensive Accessibility Testing**
- WCAG 2.1 violation detection via axe-core
- Multiple impact levels (critical, serious, moderate, minor)
- Detailed violation context: selectors, HTML snippets, element screenshots

🐳 **Containerized & Reproducible**
- Docker-first architecture ensures consistency across environments
- Smart image caching by content hash (fast local iteration)
- Supports both Docker and Podman (rootless-compatible)

📦 **Multiple Scan Modes**
- Upload ZIP archives of static sites
- Scan live URLs directly
- Generate consolidated HTML reports with rule grouping and filtering

🔒 **Security Hardened**
- Zip Slip prevention (path traversal protection)
- API request validation (MIME types, upload size limits)
- Container isolation (read-only source, controlled data mounts)
- SSRF prevention for URL scanning

⚡ **High Performance**
- Browser reuse across scans (~40-80% runtime reduction)
- Element-level screenshots (not full-page) for precision
- Graceful multi-page handling (failures don't stop pipeline)

🧪 **Developer Friendly**
- Python 3.10+ with comprehensive type hints
- 30+ unit tests + integration suite
- Minimal dependencies (only Playwright, Docker SDK, FastAPI)
- Clear logging at all critical junctures

---

## When to Use a11y-scanner

| Use Case | a11y-scanner | axe DevTools | Pa11y | Lighthouse |
|----------|--------------|--------------|-------|------------|
| **CI/CD pipelines** | ✅ Perfect fit | ❌ GUI only | ✅ | ⚠️ Requires Chrome |
| **Self-hosted/air-gapped** | ✅ Docker-first | ❌ | ⚠️ Complex setup | ❌ |
| **Batch site scanning** | ✅ ZIP upload | ❌ | ⚠️ Manual scripting | ❌ |
| **Browser reuse (performance)** | ✅ 40-80% faster | N/A | ❌ | N/A |
| **Element screenshots** | ✅ Auto-highlighted | ⚠️ Manual | ⚠️ Optional | ❌ |
| **Containerized execution** | ✅ Built-in | ❌ | ⚠️ DIY | ⚠️ DIY |
| **REST API** | ✅ FastAPI | ❌ | ⚠️ DIY | ❌ |

**Choose a11y-scanner if you need:**
- Automated scanning in CI/CD without browser installation
- Self-hosted solution for compliance/security requirements
- Batch processing of multiple static sites
- Performance optimization via browser reuse
- Containerized, reproducible execution

---

## Quick Start

### Prerequisites

- **Docker** (or Podman) running locally
- **Python 3.10+** on your host machine
- ~2GB disk space for the first build

### Setup & First Scan

```bash
# 1. Clone and create virtualenv
git clone https://github.com/yourusername/a11y-scanner.git
cd a11y-scanner
python -m venv .venv
source .venv/bin/activate  # or: . .venv/Scripts/activate (Windows)

# 2. Install editable package with dev dependencies
pip install -e ".[dev]"

# 3. Build the cached Docker image (one-time, ~2-3 min)
python -m scanner.container.runner prepare

# 4. Create a sample test site (or bring your own ZIP)
python - <<'EOF'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path("data/unzip")
root.mkdir(parents=True, exist_ok=True)
site = root / "site_tmp"
site.mkdir(parents=True, exist_ok=True)

(site / "index.html").write_text("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sample Site</title>
  <style>
    .low-contrast { color: #999; background: #f0f0f0; }
  </style>
</head>
<body>
  <h1>Sample Page</h1>
  <img src="logo.png">
  <p class="low-contrast">Low contrast text</p>
</body>
</html>""")

with ZipFile(root / "site.zip", "w", ZIP_DEFLATED) as z:
    for p in site.rglob("*"):
        if p.is_file():
            z.write(p, p.relative_to(site))

print(f"Created: {(root / 'site.zip').resolve()}")
EOF

# 5. Run the scan
python -m scanner.container.runner run

# 6. View the report
# macOS:
open data/reports/latest.html
# Linux:
# xdg-open data/reports/latest.html
```

After the scan completes, check:
- **Report:** `data/reports/latest.html` — Consolidated accessibility findings
- **Raw results:** `data/results/*.json` — Per-page violation data
- **Screenshots:** `data/results/*.png` — Violation element captures

---

## Usage Modes

### Mode 1: One-Off Scanner (Batch Processing)

Perfect for CI/CD pipelines, batch jobs, or scheduled tasks.

```bash
# Prepare Docker image (run once or after dependency updates)
python -m scanner.container.runner prepare

# Run scan (reads data/unzip/site.zip, outputs to data/reports/latest.html)
python -m scanner.container.runner run

# Optional: skip cache for debugging
python -m scanner.container.runner run --no-cache

# Optional: force rebuild cache
python -m scanner.container.runner run --rebuild-cache
```

**Input:** `data/unzip/*.zip`
**Output:**
- `data/results/*.json` (per-page violation data)
- `data/results/*.png` (violation screenshots)
- `data/reports/latest.html` (consolidated report)

### Mode 2: FastAPI Server (On-Demand Scanning)

Perfect for web-based interfaces, developer tools, or integration into larger systems.

```bash
# Start the API server on port 8008
python -m scanner.container.runner serve --port 8008

# Server is now listening at http://127.0.0.1:8008
```

#### Upload & Scan a ZIP

```bash
curl -F "file=@data/unzip/site.zip" http://127.0.0.1:8008/api/scan/zip
```

Response:
```json
{
  "status": "success",
  "violations": 5,
  "pages_scanned": 3,
  "report_url": "/reports/latest.html"
}
```

#### Scan Live URLs

```bash
curl -X POST http://127.0.0.1:8008/api/scan/url \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/", "https://example.com/about"]}'
```

#### View the Report

```bash
open http://127.0.0.1:8008/reports/latest.html
```

#### Get Raw Artifacts

```bash
# List JSON violations
curl http://127.0.0.1:8008/results/

# View specific page results
curl http://127.0.0.1:8008/results/index_html.json | jq
```

### Mode 3: Live Site Scanner (Direct URL Scanning)

For scanning production sites directly without ZIP archives.

```bash
# Edit scan_live_site.py to set target URLs
cat > scan_live_site.py <<'EOF'
BASE_URL = "https://example.com"
PAGES_TO_SCAN = ["/", "/about", "/contact"]
EOF

# Run inside container
python -m scanner.container.runner serve --port 8008
# Then trigger via API, or create custom entrypoint
```

---

## API Reference

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/scan/zip` | Upload ZIP, trigger full scan |
| `POST` | `/api/scan/url` | Scan live URLs (direct navigation) |
| `GET` | `/reports/latest.html` | Consolidated HTML report |
| `GET` | `/results` | Directory listing of JSON/PNG artifacts |
| `GET` | `/healthz` | Health check (200 OK) |

### Request/Response Examples

**POST /api/scan/zip**

```bash
curl -F "file=@site.zip" http://localhost:8008/api/scan/zip
```

Response (202 or 200):
```json
{
  "status": "success",
  "violations": 12,
  "pages_scanned": 5,
  "report_url": "/reports/latest.html",
  "message": "Scan complete. Found 12 violations."
}
```

**POST /api/scan/url**

```bash
curl -X POST http://localhost:8008/api/scan/url \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/",
      "https://example.com/products"
    ]
  }'
```

**Security Constraints:**
- Max 50 URLs per request
- MIME type validation (ZIP only)
- 100 MB upload limit
- Blocks localhost and private IPs
- Container guard: must run inside Docker

---

## Installation

### From PyPI (Coming Soon)

```bash
pip install a11y-scanner
```

### From Source

```bash
git clone https://github.com/yourusername/a11y-scanner.git
cd a11y-scanner
pip install -e ".[dev]"
```

### Docker Image (Coming Soon)

```bash
docker pull yourusername/a11y-scanner:latest
```

---

## Documentation

### For Users

- **[Quick Start](#quick-start)** — Get up and running in 5 minutes
- **[Usage Modes](#usage-modes)** — Three ways to use the scanner
- **[API Reference](#api-reference)** — REST API endpoint documentation
- **[Examples](examples/)** — CI/CD configs, Docker Compose, nginx

### For Developers

- **[Development Guide](docs/development-guide.md)** — Local setup, testing, linting, troubleshooting
- **[Architecture Guide](docs/architecture.md)** — Deep dive into components, data flow, patterns
- **[Architecture Overview](docs/architecture-overview.md)** — High-level system design

### For Contributors

- **[Contributing Guide](CONTRIBUTING.md)** — PR process, code style, commit conventions
- **[Code of Conduct](CODE_OF_CONDUCT.md)** — Community guidelines
- **[Security Policy](SECURITY.md)** — Vulnerability reporting

---

## Project Layout

```
.
├── README.md                           # This file
├── CHANGELOG.md                        # Version history
├── LICENSE                             # MIT license
├── CONTRIBUTING.md                     # Contributor guidelines
├── CODE_OF_CONDUCT.md                  # Community guidelines
├── SECURITY.md                         # Security policy
├── Makefile                            # Developer shortcuts
│
├── pyproject.toml                      # Python package metadata & dependencies
├── docker/
│   └── Dockerfile                      # Container image definition
│
├── src/scanner/                        # Main application code
│   ├── __init__.py
│   ├── main.py                         # Entry point (Docker-only guard)
│   ├── pipeline.py                     # Scanning orchestration
│   │
│   ├── container/
│   │   ├── manager.py                  # Docker SDK integration & caching
│   │   ├── runner.py                   # CLI: prepare/run/serve
│   │   └── integration.py              # Integration test harness
│   │
│   ├── services/
│   │   ├── zip_service.py              # ZIP extraction (Zip Slip protection)
│   │   ├── html_discovery_service.py   # HTML file enumeration
│   │   ├── http_service.py             # Local HTTP server
│   │   └── playwright_axe_service.py   # Playwright + axe-core scanning
│   │
│   ├── web/
│   │   └── server.py                   # FastAPI application
│   │
│   ├── reporting/
│   │   └── jinja_report.py             # HTML report generation
│   │
│   ├── core/
│   │   ├── settings.py                 # Path & configuration management
│   │   └── logging_setup.py            # Logging configuration
│   │
│   └── templates/
│       └── a11y_report.html.j2         # Jinja2 report template
│
├── tests/                              # Unit & integration tests
│   ├── conftest.py                     # Pytest fixtures
│   ├── test_*.py                       # Service/pipeline/API tests
│   └── services/
│       └── test_playwright_axe_service.py
│
├── data/                               # Runtime artifacts (gitignored)
│   ├── unzip/                          # Input ZIP archives
│   ├── scan/                           # Extracted site files
│   ├── results/                        # JSON violations & screenshots
│   ├── reports/                        # Generated HTML reports
│   └── live_results/                   # Live site scanning results
│
├── scripts/
│   ├── create_test_site.sh             # Generate sample test site
│   ├── test_reporting.sh               # Reporting smoke test
│   └── update_golden_files.sh          # Integration test helpers
│
├── examples/                           # Usage examples
│   ├── ci-github-actions.yml           # GitHub Actions workflow
│   ├── docker-compose-api.yml          # Docker Compose for API
│   └── nginx.conf                      # nginx reverse proxy config
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml                      # CI/CD pipeline
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md               # Bug report template
│       └── feature_request.md          # Feature request template
│
└── docs/
    ├── architecture.md                 # In-depth architecture guide
    ├── architecture-overview.md        # High-level overview
    └── development-guide.md            # Local setup & workflow
```

---

## Development

### Local Setup

```bash
# Create virtualenv and install with dev dependencies
make install
# OR:
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
# Fast unit tests (skip real-browser tests)
pytest -q -k "not test_playwright_axe_service"

# Full integration tests inside Docker
python -m scanner.container.integration
# OR:
make integration

# Reporting system smoke test
./scripts/test_reporting.sh
# OR:
make test-reporting
```

### Code Quality

```bash
# Format with Black
black src tests

# Lint with Ruff
ruff check src tests

# Auto-fix lint issues
ruff check src tests --fix
```

### Docker Development

```bash
# Build/rebuild the cached image
make docker-prepare

# Run scanner one-off
make scan-local

# Start API server
make serve

# Clean all artifacts
make clean
```

### Common Tasks

| Task | Command |
|------|---------|
| Install dependencies | `make install` |
| Build Docker image | `make docker-prepare` |
| Run full scan | `make scan-local` |
| Start API server | `make serve` |
| Run unit tests | `pytest -q -k "not test_playwright_axe_service"` |
| Run integration tests | `make integration` |
| Format code | `black src tests` |
| Lint code | `ruff check src tests` |
| Clean artifacts | `make clean` |

---

## Third-Party Licenses

This project uses [axe-core](https://github.com/dequelabs/axe-core) (Mozilla Public License 2.0) via `axe-playwright-python` for accessibility rule evaluation. See [LICENSE](LICENSE) for this project's MIT license.

---

## Recent Improvements

### v0.4.0 (Current)

✅ **Zip Slip Protection** — Comprehensive path validation prevents directory traversal attacks
✅ **API Hardening** — Upload size limits (100MB), MIME validation, proper HTTP error codes
✅ **Browser Reuse** — Single Playwright instance across all scans (40-80% speedup)
✅ **Element Screenshots** — Focused element captures with red outline highlights
✅ **Comprehensive Tests** — 30+ unit tests covering services, pipeline, and API endpoints
✅ **Jinja Reporting** — Aggregated HTML reports with rule grouping, impact severity, and direct remediation links
✅ **Podman Support** — Works with rootless Podman and SELinux relabeling
✅ **SSRF Prevention** — Blocks localhost and private IP addresses in URL scanning

---

## Roadmap

### Short Term

- [ ] Parallel page scanning with configurable worker pools
- [ ] Advanced configuration (include/exclude patterns, timeouts, custom viewports)
- [ ] SARIF export for GitHub Code Scanning integration
- [ ] Pre-built Docker images on Docker Hub

### Medium Term

- [ ] Background job queue with status polling
- [ ] Persistent result storage (database)
- [ ] Historical trend tracking and regression detection
- [ ] GitHub Actions template for easy CI/CD setup

### Long Term

- [ ] WebSocket API for real-time progress updates
- [ ] Custom accessibility rule definitions
- [ ] Performance profiling and automated regression detection
- [ ] Web UI dashboard for report browsing

---

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and security best practices.

### Quick Security Tips

- **Never expose API to public internet** without authentication
- Set `A11Y_API_TOKEN` environment variable for API authentication
- Use HTTPS reverse proxy (nginx, Caddy) in production
- Review screenshots for sensitive content before sharing
- Keep Docker base images updated

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for our code of conduct, development workflow, and submission process.

Before opening a PR:
- Ensure all tests pass: `pytest -q && make integration`
- Format code: `black src tests`
- Lint: `ruff check src tests`
- Update docs if adding features

---

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/a11y-scanner/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/a11y-scanner/discussions)
- **Documentation:** [docs/](docs/)
- **Security:** [SECURITY.md](SECURITY.md)

---

## Acknowledgments

Built with:
- [Playwright](https://playwright.dev/) — Web automation
- [axe-core](https://github.com/dequelabs/axe-core) — Accessibility auditing (MPL-2.0)
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [Docker](https://www.docker.com/) — Containerization
- [Jinja2](https://jinja.palletsprojects.com/) — Templating

---

**Made with ❤️ for the accessibility community**
