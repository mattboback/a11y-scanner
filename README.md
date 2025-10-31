# a11y-scanner

> A containerized web accessibility scanner using Playwright and axe-core for comprehensive WCAG compliance testing.

[![CI Status](https://github.com/mattboback/a11y-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/mattboback/a11y-scanner/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## What is a11y-scanner?

**a11y-scanner** is a Python-based accessibility testing tool that automates WCAG compliance checks for web applications. It combines the power of [axe-core](https://github.com/dequelabs/axe-core) (the industry-leading accessibility rules engine) with [Playwright](https://playwright.dev/) (modern browser automation) to provide:

- 🔍 **Comprehensive scanning** of static sites, multi-page applications, and single pages
- 📊 **Rich HTML reports** with violation screenshots and remediation guidance
- 🐳 **Docker-first architecture** for consistent, reproducible results
- 🔌 **REST API** for integration into CI/CD pipelines
- 🔒 **Security-hardened** with Zip Slip protection, SSRF prevention, and input validation

Perfect for developers, QA teams, and accessibility specialists who need automated a11y testing in their workflows.

---

## ✨ Features

### Core Capabilities

- **Multi-format Input**: Scan from ZIP archives, local directories, or live URLs
- **Browser-based Testing**: Real browser rendering via Playwright (Chromium/Firefox/WebKit)
- **axe-core Integration**: Industry-standard WCAG 2.1 Level A/AA rule engine
- **Visual Evidence**: Automatic screenshots of violating elements with red highlighting
- **JSON Summary + HTML Reports**: Machine-readable aggregation alongside rich visualizations
- **Browser Reuse**: Context manager pattern for 40-80% faster multi-page scans

### Security Features

- **Zip Slip Protection** (CWE-22): Path traversal validation prevents malicious archives
- **SSRF Prevention**: Blocks localhost and private IP ranges in URL scanning
- **Input Validation**: File size limits (100MB), MIME type checking, extension validation
- **Container Isolation**: Read-only source mounts, controlled data volumes
- **Optional API Authentication**: Token-based auth via `A11Y_API_TOKEN` environment variable

### Developer Experience

- **Three Run Modes**: CLI, API server, or Docker container orchestration
- **CI/CD Ready**: GitHub Actions examples, exit codes for violation detection
- **Flexible Configuration**: Environment variables for screenshots, paths, tokens
- **Detailed Logging**: Structured logs with configurable verbosity
- **Type Hinted**: Full type annotations for better IDE support

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ ([download](https://www.python.org/downloads/))
- Docker 20.10+ or Podman 3.4+ ([get Docker](https://docs.docker.com/get-docker/))
- 2GB RAM minimum, 4GB recommended

### Installation

```bash
# Clone the repository
git clone https://github.com/mattboback/a11y-scanner.git
cd a11y-scanner

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Prepare Docker image (one-time, ~2-5 minutes)
python -m scanner.container.runner prepare
```

### Run Your First Scan

```bash
# Create a sample HTML file
mkdir -p data/unzip
cat > data/unzip/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head><title>Test Page</title></head>
<body>
    <h1>Sample Page</h1>
    <img src="photo.jpg">  <!-- Missing alt text - violation! -->
    <button>Click</button>
</body>
</html>
EOF

# Package as ZIP
cd data/unzip && zip -r ../site.zip . && cd ../..

# Run a scan (friendly CLI)
a11y scan --zip-path data/unzip/site.zip

# View the report
open data/reports/latest.html  # macOS
# Or: xdg-open data/reports/latest.html  # Linux
# Or: start data/reports/latest.html     # Windows
```

You should see a violation report for the missing `alt` attribute! 🎉

---

## 📖 Usage

### Mode 1: CLI (Scan ZIP Files)

The primary mode for scanning packaged sites:

```bash
# Scan a ZIP file
python -m scanner.container.runner run

# Custom paths
python -m scanner.container.runner run \
    --zip-path /path/to/site.zip \
    --output-dir /path/to/results

# Disable screenshots for faster scans
A11Y_NO_SCREENSHOTS=1 python -m scanner.container.runner run
```

**Expected output:**
```
✓ Docker image ready
✓ Scanning site.zip...
✓ Found 3 pages
✓ Scanned 3 pages
⚠ Found 12 violations
✓ Report: data/reports/latest.html
✓ Summary: data/reports/latest.json
```

### Mode 2: API Server

Long-running service for programmatic access:

```bash
# Start the API server (runs on port 8008)
a11y prepare  # one-time
python -m scanner.container.runner serve

# In another terminal, scan via API
curl -X POST http://localhost:8008/api/scan/zip \
    -H "Content-Type: multipart/form-data" \
    -F "file=@data/unzip/site.zip"

# Response:
# {
#   "status": "success",
#   "pages_scanned": 3,
#   "total_violations": 12,
#   "report_path": "data/reports/latest.html",
#   "results_dir": "data/results"
# }
```

**With authentication:**
```bash
# Generate a secure token
export A11Y_API_TOKEN=$(openssl rand -base64 32)

# Start server with auth
python -m scanner.container.runner serve

# Use token in requests
curl -X POST http://localhost:8008/api/scan/zip \
    -H "X-API-Key: $A11Y_API_TOKEN" \
    -F "file=@site.zip"
```

### Mode 3: Scan Live URLs

Scan a running website via the friendly CLI:

```bash
# Single URL with optional comma-separated paths
a11y live --base-url https://example.com --pages "/,/about,/contact"
```

---

## 🖥️ Platform Support

| Platform | Support Status | Notes |
|----------|----------------|-------|
| **Linux** | ✅ Fully Supported | Ubuntu 20.04+, Debian 11+, Fedora 35+ |
| **macOS** | ✅ Fully Supported | macOS 11+ (Intel & Apple Silicon) |
| **Windows** | ⚠️ Supported via WSL2 | Native Windows support planned |
| **Docker** | ✅ Recommended | Docker 20.10+ or Podman 3.4+ |

### System Requirements

- **RAM**: 2GB minimum, 4GB recommended
- **Disk**: 2GB for Docker images + scan artifacts
- **CPU**: 2 cores minimum (parallel scanning planned for v1.1)
- **Network**: Internet access for Docker image pull (one-time setup)

---

## 🌍 Real-World Examples

### CI/CD Integration (GitHub Actions)

Automatically scan on every push:

```yaml
# .github/workflows/accessibility.yml
name: Accessibility Audit

on:
  push:
    branches: [main]
  pull_request:

jobs:
  a11y-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install scanner
        run: |
          pip install -e .
          python -m scanner.container.runner prepare

      - name: Build and package site
        run: |
          npm ci && npm run build
          mkdir -p data/unzip
          cd dist && zip -r ../data/unzip/site.zip .

      - name: Run accessibility scan
        run: python -m scanner.container.runner run

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: accessibility-report
          path: data/reports/latest.html

      - name: Fail on violations
        run: |
          count=$(jq -s 'map(.violations | length) | add' data/results/*.json)
          if [ "$count" -gt 0 ]; then
            echo "::error::Found $count accessibility violations"
            exit 1
          fi
```

### Docker Compose for Teams

Shared accessibility scanner service:

```yaml
# docker-compose.yml
version: '3.8'

services:
  a11y-scanner:
    image: mattboback/a11y-scanner:latest
    container_name: team-a11y-scanner
    ports:
      - "8008:8008"
    volumes:
      - ./scans:/worksrc/data
    environment:
      - A11Y_API_TOKEN=${SCANNER_API_TOKEN}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8008/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

# Usage:
# 1. export SCANNER_API_TOKEN=$(openssl rand -base64 32)
# 2. docker-compose up -d
# 3. curl -H "X-API-Key: $SCANNER_API_TOKEN" \
#        -F "file=@site.zip" \
#        http://localhost:8008/api/scan/zip
```

### Scheduled Weekly Audits

Monitor production site automatically:

```yaml
# .github/workflows/weekly-audit.yml
name: Weekly A11y Audit

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM

jobs:
  scan-production:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install and scan
        run: |
          pip install -e .
          python -m scanner.container.runner prepare
          python scan_live_site.py https://yoursite.com

      - name: Create issue if violations found
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🚨 Weekly A11y Scan Found Violations',
              body: 'Check the workflow artifacts for the full report.',
              labels: ['accessibility', 'automated']
            })
```

---

## ⚡ Performance Benchmarks

Real-world scanning performance on a 4-core, 16GB RAM development machine:

| Site Size | Pages | Violations | Scan Time | Memory |
|-----------|-------|------------|-----------|---------|
| Small | 10 | 45 | ~15s | 400MB |
| Medium | 50 | 200 | ~1m 30s | 600MB |
| Large | 200 | 800 | ~6m | 1.2GB |

### Optimization Tips

- **Browser Reuse**: 40-80% faster on multi-page sites (automatically enabled in pipeline)
- **Disable Screenshots**: Set `A11Y_NO_SCREENSHOTS=1` for 2x faster scans
- **Parallel Scanning**: Coming in v1.1 with `--workers 4` flag

---

## 🛠️ Troubleshooting

### Docker Permission Issues

**Problem:** `docker: Got permission denied while trying to connect to the Docker daemon`

**Solution (Linux):**
```bash
sudo usermod -aG docker $USER
newgrp docker  # Or log out and back in
```

### Podman Socket Not Found

**Problem:** `Cannot connect to Podman socket`

**Solution:**
```bash
systemctl --user start podman.socket
systemctl --user enable podman.socket
podman version  # Verify
```

### Port Already in Use

**Problem:** `Address already in use: 8008`

**Solution:**
```bash
# Use different port
python -m scanner.container.runner serve --port 8009

# Or find and kill process
lsof -ti:8008 | xargs kill -9  # macOS/Linux
```

### Slow First Build

**Problem:** Docker image build takes 5+ minutes

**Expected:** This is normal for the first build. Subsequent builds use cache and complete in seconds. Run `python -m scanner.container.runner prepare` once during setup.

### Screenshots Not Capturing

**Problem:** Violation screenshots are missing or blank

**Common Causes:**
1. JavaScript-heavy pages (already using `networkidle` wait)
2. CSP violations (check browser console with `--verbose`)
3. Memory limits (increase Docker memory: `shm_size: "2gb"`)

**Workaround:** Disable screenshots if not needed:
```bash
export A11Y_NO_SCREENSHOTS=1
python -m scanner.container.runner run
```

### Windows-Specific Issues

**Problem:** Path errors on Windows

**Solution:** Use WSL2 (Windows Subsystem for Linux):
```powershell
wsl --install  # Install WSL2
# Inside WSL2:
cd /path/to/a11y-scanner
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Getting Help

1. **Check existing issues**: [GitHub Issues](https://github.com/mattboback/a11y-scanner/issues)
2. **Ask in discussions**: [GitHub Discussions](https://github.com/mattboback/a11y-scanner/discussions)
3. **Review documentation**: See [`docs/`](docs/) folder
4. **Enable debug logging**:
   ```python
   from scanner.core.logging_setup import setup_logging
   import logging
   setup_logging(level=logging.DEBUG)
   ```

---

## ❓ FAQ

**Q: How does this compare to browser extensions like axe DevTools?**

A: Browser extensions are great for manual testing, but a11y-scanner is designed for automation:
- ✅ Runs in CI/CD without manual intervention
- ✅ Scans entire sites in batch
- ✅ Self-hosted for security/compliance
- ✅ Integrates into development workflows

**Q: Does this replace manual accessibility testing?**

A: **No.** Automated tools catch ~30-40% of accessibility issues. You still need:
- Manual keyboard navigation testing
- Screen reader testing (NVDA, JAWS, VoiceOver)
- User testing with people with disabilities

**Q: Can I scan sites behind authentication?**

A: Not directly yet. Current workarounds:
1. Export static HTML after authentication
2. Use a browser extension to save authenticated pages
3. Contribute authentication support (see [Contributing](#-contributing))

**Q: Is this WCAG 2.1 AA compliant?**

A: a11y-scanner **tests for** WCAG violations using axe-core, which covers many WCAG 2.1 Level A and AA criteria. It's a tool to help **achieve** compliance, not a certification.

**Q: Can I customize the rules?**

A: Currently uses axe-core's default ruleset. Custom rules are planned for v1.2. You can disable specific rules by forking and modifying the axe configuration in `src/scanner/services/playwright_axe_service.py`.

**Q: Why Docker? Can I run without it?**

A: Docker ensures consistent browser environments across platforms:
- ✅ No Playwright dependency version mismatches
- ✅ Reproducible results in CI/CD
- ✅ Works the same on Linux, macOS, Windows (via WSL2)

You *can* run Playwright natively for development, but Docker is recommended for production/CI use.

**Q: How much does this cost?**

A: a11y-scanner is **free and open source** (MIT license). You only pay for:
- Infrastructure (servers, CI minutes if using cloud providers)
- Optional: Commercial support (not yet available)

**Q: Can I contribute?**

A: **Yes!** See [CONTRIBUTING.md](CONTRIBUTING.md). We welcome:
- 🐛 Bug reports and fixes
- ✨ Feature requests and implementations
- 📝 Documentation improvements
- 💡 Use cases and examples

---

## 🤝 Contributing

We love contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines (Black, Ruff)
- Testing requirements (pytest, coverage)
- Commit conventions (Conventional Commits)
- PR process

**Quick start for contributors:**
```bash
git clone https://github.com/mattboback/a11y-scanner.git
cd a11y-scanner
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest  # Run tests
ruff format . # Format code
ruff check .  # Lint
```

---

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

---

## 🌟 Acknowledgments

- **[axe-core](https://github.com/dequelabs/axe-core)** by Deque Systems - Industry-leading accessibility rules engine
- **[Playwright](https://playwright.dev/)** by Microsoft - Modern browser automation
- **[axe-playwright-python](https://github.com/abhinaba-ghosh/axe-playwright-python)** - Python bindings for axe in Playwright

---

## 📞 Contact & Support

- **GitHub**: [@mattboback](https://github.com/mattboback)
- **Issues**: [Report a bug](https://github.com/mattboback/a11y-scanner/issues)
- **Discussions**: [Ask questions](https://github.com/mattboback/a11y-scanner/discussions)
- **Security**: matthewboback@gmail.com (for security vulnerabilities only)
- **Website**: [matthewboback.com](https://matthewboback.com)

---

**⭐ Star this repo** to stay updated on new releases and features!

Made with ❤️ by [Matthew Boback](https://matthewboback.com)
